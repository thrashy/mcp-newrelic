"""
Base New Relic API client.

Provides common HTTP client functionality and NRQL query capabilities.
"""

import base64
import logging
from typing import Any

import httpx

from ..config import NewRelicConfig
from ..types import ApiError, DecodedEntityGuid, PaginatedResult
from ..utils.graphql_helpers import extract_nested_data

logger = logging.getLogger(__name__)

# Maps NR error codes to actionable hints (mirrors Go client error classification)
_NRQL_ERROR_HINTS: dict[str, str] = {
    "NRDB:1109": "Query timed out. Try a shorter time range (e.g. SINCE 1 hour ago), add LIMIT, or narrow with WHERE clauses.",
    "NRDB:1107005": "Query syntax or function error. Check function names (e.g. use uniqueCount() instead of uniques() for high-cardinality attributes) and attribute types.",
    "NRDB:1107001": "Invalid NRQL syntax. Verify your SELECT, FROM, WHERE, and FACET clauses.",
    "NRDB:1107002": "Invalid event type. Check that the FROM clause references a valid event type (e.g. Transaction, Span, Log, Metric).",
    "NRDB:1107003": "Invalid attribute. The attribute in your query does not exist for this event type.",
    "NRDB:1107004": "Invalid function. Check the NRQL function name and argument types.",
}


class BaseNewRelicClient:
    """Base client for interacting with New Relic APIs"""

    def __init__(self, config: NewRelicConfig):
        self.config = config
        self.base_url = (
            "https://api.newrelic.com" if config.effective_region == "US" else "https://api.eu.newrelic.com"
        )
        self.headers: dict[str, str] = {"Api-Key": config.api_key or "", "Content-Type": "application/json"}
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=config.effective_timeout,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()

    async def _execute_http_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute HTTP request with common error handling"""
        response = await self._http_client.post("/graphql", json=payload)
        response.raise_for_status()
        result: dict[str, Any] = response.json()

        if "errors" in result:
            errors = result["errors"]
            logger.error("GraphQL errors: %s", errors)
            hint = ""
            if errors and isinstance(errors, list):
                error_code = errors[0].get("extensions", {}).get("errorCode", "")
                hint = _NRQL_ERROR_HINTS.get(error_code, "")
            msg = f"GraphQL query failed: {errors}"
            if hint:
                msg += f"\nHint: {hint}"
            raise ValueError(msg)

        return result

    def _extract_mutation_result(
        self, result: dict[str, Any], mutation_key: str, *, error_message: str = "Mutation failed"
    ) -> dict[str, Any] | ApiError:
        """Extract mutation result, returning ApiError if empty or if errors are present."""
        mutation_result: dict[str, Any] = result.get("data", {}).get(mutation_key, {})
        errors = mutation_result.get("errors")
        if errors:
            return ApiError(f"{error_message}: {errors}")
        if not mutation_result:
            return ApiError(error_message)
        return mutation_result

    async def query_nrql(self, account_id: str, query: str) -> dict[str, Any]:
        """Execute a NRQL query using GraphQL variables to prevent injection"""
        graphql_query = {
            "query": """
            query($accountId: Int!, $nrqlQuery: Nrql!) {
                actor {
                    account(id: $accountId) {
                        nrql(query: $nrqlQuery) {
                            results
                        }
                    }
                }
            }
            """,
            "variables": {
                "accountId": int(account_id),
                "nrqlQuery": query,
            },
        }

        logger.debug("Executing NRQL query: %s", query)
        result = await self._execute_http_request(graphql_query)
        logger.debug("Query result: %s", result)
        return result

    @staticmethod
    def decode_entity_guid(guid: str) -> DecodedEntityGuid:
        """Decode a NR entity GUID (base64) into its components.

        Follows the same format as the Go client (newrelic-client-go):
        base64(accountId|domain|entityType|domainId)
        Handles both padded and unpadded (RawStdEncoding) base64.
        """
        try:
            # Normalize padding — handles both padded and unpadded input
            padded = guid + "=" * (-len(guid) % 4)
            decoded = base64.b64decode(padded).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Invalid entity GUID — not valid base64: {e}") from e

        parts = decoded.split("|")
        if len(parts) < 4:
            raise ValueError(
                f"Invalid entity GUID — expected at least 4 parts delimited by '|', got {len(parts)}: {decoded}"
            )

        try:
            account_id = int(parts[0])
        except ValueError as e:
            raise ValueError(f"Invalid account ID in entity GUID: {parts[0]}") from e

        return DecodedEntityGuid(
            account_id=account_id,
            domain=parts[1],
            entity_type=parts[2],
            domain_id=parts[3],
        )

    async def get_entity(self, guid: str) -> dict[str, Any] | ApiError:
        """Look up a single entity by GUID, returning key details."""
        query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              guid
              name
              entityType
              domain
              type
              alertSeverity
              reporting
              permalink
              account { id name }
              tags { key values }
              ... on ApmApplicationEntity {
                language
                applicationId
                runningAgentVersions { minVersion maxVersion }
              }
              ... on SyntheticMonitorEntity {
                monitorType
                monitorId
                period
              }
              ... on InfrastructureHostEntity {
                hostSummary { cpuUtilizationPercent memoryUsedPercent }
              }
            }
          }
        }
        """
        try:
            result = await self.execute_graphql(query, {"guid": guid})
            entity: dict[str, Any] | None = result.get("data", {}).get("actor", {}).get("entity")
            if not entity:
                return ApiError(f"Entity not found for GUID: {guid}")
            return entity
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
            return ApiError(f"Failed to get entity: {e}")

    async def execute_graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query with optional variables"""
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        return await self._execute_http_request(payload)

    async def paginate_graphql(
        self,
        query: str,
        variables: dict[str, Any],
        data_path: list[str],
        items_key: str,
        *,
        max_pages: int = 10,
        limit: int | None = None,
    ) -> PaginatedResult:
        """Execute a paginated GraphQL query using cursor-based pagination.

        Follows nextCursor through up to max_pages pages, collecting items from
        the given data_path and items_key.
        """
        all_items: list[dict[str, Any]] = []
        cursor: str | None = None
        total_count: int | None = None

        for _ in range(max_pages):
            result = await self.execute_graphql(query, {**variables, "cursor": cursor})
            page_data = extract_nested_data(result, data_path)
            all_items.extend(page_data.get(items_key, []))
            total_count = page_data.get("totalCount", total_count)
            cursor = page_data.get("nextCursor")
            if not cursor or (limit is not None and len(all_items) >= limit):
                break

        if limit is not None:
            all_items = all_items[:limit]

        return PaginatedResult(items=all_items, total_count=total_count)
