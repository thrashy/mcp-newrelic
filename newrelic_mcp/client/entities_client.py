"""
New Relic Entities API client.

Handles entity search, tagging, service levels, and synthetic monitors.
"""

import logging
from typing import Any

from ..types import ApiError
from ..utils.error_handling import API_ERRORS, handle_api_error
from ..utils.graphql_helpers import escape_nrql_string, extract_nrql_results
from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)

# Shared data path for entitySearch pagination
_ENTITY_SEARCH_PATH = ["data", "actor", "entitySearch", "results"]


class EntitiesClient:
    """Client for New Relic entity, tagging, service level, and synthetics APIs"""

    def __init__(self, base: BaseNewRelicClient):
        self._base = base

    async def _execute_tag_mutation(
        self, mutation: str, variables: dict[str, Any], mutation_key: str, operation: str
    ) -> dict[str, Any] | ApiError:
        """Execute a tagging mutation and check for errors."""
        try:
            result = await self._base.execute_graphql(mutation, variables)
            errors = result.get("data", {}).get(mutation_key, {}).get("errors", [])
            if errors:
                return ApiError(errors[0].get("message", "Unknown error"))
            return {"success": True}
        except API_ERRORS as e:
            return handle_api_error(operation, e)

    async def entity_search(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        domain: str | None = None,
        tags: list[dict[str, str]] | None = None,
        limit: int = 25,
        minimal_output: bool = False,
    ) -> list[dict[str, Any]] | ApiError:
        """Search for entities using NerdGraph entitySearch with cursor-based pagination.

        Args:
            name: Partial name match (LIKE).
            entity_type: Entity type filter (APPLICATION, HOST, MONITOR, etc.).
            domain: Domain filter (APM, INFRA, SYNTH, BROWSER, MOBILE, EXT).
            tags: Tag filters as [{"key": ..., "value": ...}].
            limit: Maximum entities to return (default 25, max 200).
            minimal_output: If True, omit tags and extra metadata from results.
        """
        parts = []
        if name:
            parts.append(f"name LIKE '%{escape_nrql_string(name)}%'")
        if entity_type:
            parts.append(f"type = '{escape_nrql_string(entity_type.upper())}'")
        if domain:
            parts.append(f"domain = '{escape_nrql_string(domain.upper())}'")
        if tags:
            for tag in tags:
                parts.append(f"tags.`{escape_nrql_string(tag['key'])}` = '{escape_nrql_string(tag['value'])}'")

        query_string = " AND ".join(parts) if parts else "domain IN ('APM', 'INFRA', 'SYNTH', 'BROWSER')"

        # Use a lighter query when minimal_output is requested
        if minimal_output:
            query = """
            query($searchQuery: String!, $cursor: String) {
              actor {
                entitySearch(query: $searchQuery) {
                  results(cursor: $cursor) {
                    entities {
                      guid
                      name
                      entityType
                      domain
                      type
                      alertSeverity
                      reporting
                    }
                    nextCursor
                  }
                  count
                }
              }
            }
            """
        else:
            query = """
            query($searchQuery: String!, $cursor: String) {
              actor {
                entitySearch(query: $searchQuery) {
                  results(cursor: $cursor) {
                    entities {
                      guid
                      name
                      entityType
                      domain
                      type
                      alertSeverity
                      reporting
                      tags {
                        key
                        values
                      }
                      ... on ApmApplicationEntityOutline {
                        language
                        applicationId
                      }
                      ... on SyntheticMonitorEntityOutline {
                        monitorType
                        monitorId
                        period
                      }
                      ... on InfrastructureHostEntityOutline {
                        hostSummary {
                          cpuUtilizationPercent
                          memoryUsedPercent
                        }
                      }
                    }
                    nextCursor
                  }
                  count
                }
              }
            }
            """

        effective_limit = min(limit, 200)

        try:
            result = await self._base.paginate_graphql(
                query,
                {"searchQuery": query_string},
                _ENTITY_SEARCH_PATH,
                "entities",
                limit=effective_limit,
            )
            return result.items
        except API_ERRORS as e:
            return handle_api_error("entity search", e)

    async def get_entity_tags(self, guid: str) -> dict[str, Any] | ApiError:
        """Get all tags for an entity by GUID"""
        query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              name
              entityType
              tags {
                key
                values
              }
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(query, {"guid": guid})
            entity: dict[str, Any] = result.get("data", {}).get("actor", {}).get("entity", {})
            return entity
        except API_ERRORS as e:
            return handle_api_error("get entity tags", e)

    async def add_tags_to_entity(self, guid: str, tags: list[dict[str, str]]) -> dict[str, Any] | ApiError:
        """Add tags to an entity"""
        mutation = """
        mutation($guid: EntityGuid!, $tags: [TaggingTagInput!]!) {
          taggingAddTagsToEntity(guid: $guid, tags: $tags) {
            errors { message type }
          }
        }
        """
        tags_input = [{"key": t["key"], "values": [t["value"]]} for t in tags]
        return await self._execute_tag_mutation(
            mutation, {"guid": guid, "tags": tags_input}, "taggingAddTagsToEntity", "add tags to entity"
        )

    async def delete_tags_from_entity(self, guid: str, tag_keys: list[str]) -> dict[str, Any] | ApiError:
        """Delete tag keys from an entity"""
        mutation = """
        mutation($guid: EntityGuid!, $tagKeys: [String!]!) {
          taggingDeleteTagFromEntity(guid: $guid, tagKeys: $tagKeys) {
            errors { message type }
          }
        }
        """
        return await self._execute_tag_mutation(
            mutation, {"guid": guid, "tagKeys": tag_keys}, "taggingDeleteTagFromEntity", "delete tags from entity"
        )

    async def replace_tags_on_entity(self, guid: str, tags: list[dict[str, str]]) -> dict[str, Any] | ApiError:
        """Replace all tags on an entity (overwrites existing tags)"""
        mutation = """
        mutation($guid: EntityGuid!, $tags: [TaggingTagInput!]!) {
          taggingReplaceTagsOnEntity(guid: $guid, tags: $tags) {
            errors { message type }
          }
        }
        """
        tags_input = [{"key": t["key"], "values": [t["value"]]} for t in tags]
        return await self._execute_tag_mutation(
            mutation, {"guid": guid, "tags": tags_input}, "taggingReplaceTagsOnEntity", "replace tags on entity"
        )

    async def delete_tag_values(self, guid: str, tag_values: list[dict[str, str]]) -> dict[str, Any] | ApiError:
        """Delete specific tag values from an entity (keeps the key if other values remain)"""
        mutation = """
        mutation($guid: EntityGuid!, $tagValues: [TaggingTagValueInput!]!) {
          taggingDeleteTagValuesFromEntity(guid: $guid, tagValues: $tagValues) {
            errors { message type }
          }
        }
        """
        tag_values_input = [{"key": t["key"], "value": t["value"]} for t in tag_values]
        return await self._execute_tag_mutation(
            mutation, {"guid": guid, "tagValues": tag_values_input},
            "taggingDeleteTagValuesFromEntity", "delete tag values"
        )

    async def list_service_levels(self, account_id: str) -> list[dict[str, Any]] | ApiError:
        """List service level indicators (SLIs) for the account"""
        query = """
        query($searchQuery: String!, $cursor: String) {
          actor {
            entitySearch(query: $searchQuery) {
              results(cursor: $cursor) {
                entities {
                  guid
                  name
                  entityType
                  alertSeverity
                  reporting
                  tags {
                    key
                    values
                  }
                }
                nextCursor
              }
              count
            }
          }
        }
        """

        search_query = f"accountId = {int(account_id)} AND domain = 'EXT' AND type = 'SERVICE_LEVEL'"

        try:
            result = await self._base.paginate_graphql(
                query,
                {"searchQuery": search_query},
                _ENTITY_SEARCH_PATH,
                "entities",
            )
            all_entities = result.items

            # Enrich with SLI compliance data from NRQL
            if all_entities:
                nrql_result = await self._base.query_nrql(
                    account_id,
                    "SELECT latest(`newrelic.sli.good`) as good, latest(`newrelic.sli.valid`) as valid, "
                    "latest(`newrelic.sli.bad`) as bad "
                    "FROM Metric WHERE entity.type = 'SERVICE_LEVEL' "
                    "FACET entity.guid, entity.name SINCE 1 hour ago LIMIT 200",
                )
                sli_rows = extract_nrql_results(nrql_result)
                sli_by_guid = {r.get("entity.guid"): r for r in sli_rows if r.get("entity.guid")}
                enriched = []
                for e in all_entities:
                    sli_data = sli_by_guid.get(e.get("guid"), {})
                    compliance = None
                    if sli_data:
                        good = sli_data.get("good", 0) or 0
                        valid = sli_data.get("valid", 0) or 0
                        compliance = round((good / valid * 100), 2) if valid > 0 else None
                    enriched.append({**e, "sliCompliance": compliance})
                all_entities = enriched

            return all_entities
        except API_ERRORS as e:
            return handle_api_error("list service levels", e)

    async def list_synthetic_monitors(self, account_id: str) -> list[dict[str, Any]] | ApiError:
        """List synthetic monitors via entity search with cursor-based pagination"""
        query = """
        query($searchQuery: String!, $cursor: String) {
          actor {
            entitySearch(query: $searchQuery) {
              results(cursor: $cursor) {
                entities {
                  guid
                  name
                  alertSeverity
                  reporting
                  ... on SyntheticMonitorEntityOutline {
                    monitorType
                    monitorId
                    period
                    monitorSummary {
                      status
                      successRate
                      locationsFailing
                      locationsRunning
                    }
                  }
                  tags {
                    key
                    values
                  }
                }
                nextCursor
              }
              count
            }
          }
        }
        """

        search_query = f"domain = 'SYNTH' AND type = 'MONITOR' AND accountId = {int(account_id)}"
        try:
            result = await self._base.paginate_graphql(
                query,
                {"searchQuery": search_query},
                _ENTITY_SEARCH_PATH,
                "entities",
            )
            return result.items
        except API_ERRORS as e:
            return handle_api_error("list synthetic monitors", e)

    async def get_synthetic_results(self, account_id: str, monitor_guid: str, hours: int = 24) -> dict[str, Any] | ApiError:
        """Get recent results for a synthetic monitor"""
        entity_query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              name
              ... on SyntheticMonitorEntity {
                monitorId
                monitorType
                period
                monitorSummary {
                  status
                  successRate
                  locationsFailing
                  locationsRunning
                }
              }
            }
          }
        }
        """

        try:
            entity_result = await self._base.execute_graphql(entity_query, {"guid": monitor_guid})
            entity = entity_result.get("data", {}).get("actor", {}).get("entity", {})
            monitor_id = entity.get("monitorId")

            results: dict[str, Any] = {"entity": entity, "results": []}

            if monitor_id:
                nrql_query = (
                    f"SELECT result, duration, locationLabel, error "
                    f"FROM SyntheticCheck "
                    f"WHERE monitorId = '{escape_nrql_string(monitor_id)}' "
                    f"SINCE {hours} hours ago "
                    f"ORDER BY timestamp DESC LIMIT 50"
                )
                nrql_result = await self._base.query_nrql(account_id, nrql_query)
                results["results"] = extract_nrql_results(nrql_result)

            return results
        except API_ERRORS as e:
            return handle_api_error("get synthetic results", e)
