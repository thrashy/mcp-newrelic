"""
New Relic Entities API client.

Handles entity search, tagging, service levels, and synthetic monitors.
"""

import logging
from typing import Any

from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)


class EntitiesClient(BaseNewRelicClient):
    """Client for New Relic entity, tagging, service level, and synthetics APIs"""

    async def entity_search(
        self,
        name: str | None = None,
        entity_type: str | None = None,
        domain: str | None = None,
        tags: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for entities using NerdGraph entitySearch.

        Note: NerdGraph returns a maximum of 200 results per page. Pagination
        via nextCursor is not currently implemented, so results are capped at 200.
        """
        # Build query fragment
        parts = []
        if name:
            parts.append(f"name LIKE '%{name}%'")
        if entity_type:
            parts.append(f"type = '{entity_type.upper()}'")
        if domain:
            parts.append(f"domain = '{domain.upper()}'")
        if tags:
            for tag in tags:
                parts.append(f"tags.`{tag['key']}` = '{tag['value']}'")

        query_string = " AND ".join(parts) if parts else "domain IN ('APM', 'INFRA', 'SYNTH', 'BROWSER')"

        # entitySearch returns Outline types — use only common fields plus Outline-specific fragments
        query = """
        {
          actor {
            entitySearch(query: "%s") {
              results {
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
        """ % query_string.replace('"', '\\"')

        result = await self.execute_graphql(query)
        search = result.get("data", {}).get("actor", {}).get("entitySearch", {})
        entities = search.get("results", {}).get("entities", [])
        return entities

    async def get_entity_tags(self, guid: str) -> dict[str, Any]:
        """Get all tags for an entity by GUID"""
        query = """
        {
          actor {
            entity(guid: "%s") {
              name
              entityType
              tags {
                key
                values
              }
            }
          }
        }
        """ % guid

        result = await self.execute_graphql(query)
        entity = result.get("data", {}).get("actor", {}).get("entity", {})
        return entity

    async def add_tags_to_entity(self, guid: str, tags: list[dict[str, str]]) -> dict[str, Any]:
        """Add tags to an entity"""
        tags_input = ", ".join([f'{{key: "{t["key"]}", values: ["{t["value"]}"]}}' for t in tags])
        mutation = """
        mutation {
          taggingAddTagsToEntity(guid: "%s", tags: [%s]) {
            errors {
              message
              type
            }
          }
        }
        """ % (guid, tags_input)

        result = await self.execute_graphql(mutation)
        errors = result.get("data", {}).get("taggingAddTagsToEntity", {}).get("errors", [])
        if errors:
            return {"error": errors[0].get("message", "Unknown error")}
        return {"success": True}

    async def delete_tags_from_entity(self, guid: str, tag_keys: list[str]) -> dict[str, Any]:
        """Delete tag keys from an entity"""
        keys_input = ", ".join([f'"{k}"' for k in tag_keys])
        mutation = """
        mutation {
          taggingDeleteTagFromEntity(guid: "%s", tagKeys: [%s]) {
            errors {
              message
              type
            }
          }
        }
        """ % (guid, keys_input)

        result = await self.execute_graphql(mutation)
        errors = result.get("data", {}).get("taggingDeleteTagFromEntity", {}).get("errors", [])
        if errors:
            return {"error": errors[0].get("message", "Unknown error")}
        return {"success": True}

    async def list_service_levels(self, account_id: str) -> list[dict[str, Any]]:
        """List service level indicators (SLIs) for the account"""
        # Service levels are entities with domain EXT and type SERVICE_LEVEL
        query = """
        {
          actor {
            entitySearch(query: "accountId = %s AND domain = 'EXT' AND type = 'SERVICE_LEVEL'") {
              results {
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
              }
              count
            }
          }
        }
        """ % account_id

        entities = (
            (await self.execute_graphql(query))
            .get("data", {})
            .get("actor", {})
            .get("entitySearch", {})
            .get("results", {})
            .get("entities", [])
        )

        # Enrich with SLI compliance data from NRQL
        if entities:
            nrql_result = await self.query_nrql(
                account_id,
                "SELECT latest(`newrelic.sli.good`) as good, latest(`newrelic.sli.valid`) as valid, "
                "latest(`newrelic.sli.bad`) as bad "
                "FROM Metric WHERE entity.type = 'SERVICE_LEVEL' "
                "FACET entity.guid, entity.name SINCE 1 hour ago LIMIT 200"
            )
            sli_rows = (
                nrql_result.get("data", {})
                .get("actor", {})
                .get("account", {})
                .get("nrql", {})
                .get("results", [])
            )
            sli_by_guid = {r.get("entity.guid"): r for r in sli_rows if r.get("entity.guid")}
            enriched = []
            for e in entities:
                sli_data = sli_by_guid.get(e.get("guid"), {})
                compliance = None
                if sli_data:
                    good = sli_data.get("good", 0) or 0
                    valid = sli_data.get("valid", 0) or 0
                    compliance = round((good / valid * 100), 2) if valid > 0 else None
                enriched.append({**e, "sliCompliance": compliance})
            entities = enriched

        return entities or []

    async def list_synthetic_monitors(self, account_id: str) -> list[dict[str, Any]]:
        """List synthetic monitors via entity search"""
        query = """
        {
          actor {
            entitySearch(query: "domain = 'SYNTH' AND type = 'MONITOR' AND accountId = %s") {
              results {
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
              }
              count
            }
          }
        }
        """ % account_id

        result = await self.execute_graphql(query)
        entities = (
            result.get("data", {})
            .get("actor", {})
            .get("entitySearch", {})
            .get("results", {})
            .get("entities", [])
        )
        return entities or []

    async def get_synthetic_results(self, account_id: str, monitor_guid: str, hours: int = 24) -> dict[str, Any]:
        """Get recent results for a synthetic monitor"""
        # Get monitor name from entity
        entity_query = """
        {
          actor {
            entity(guid: "%s") {
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
        """ % monitor_guid

        entity_result = await self.execute_graphql(entity_query)
        entity = entity_result.get("data", {}).get("actor", {}).get("entity", {})
        monitor_id = entity.get("monitorId")

        results: dict[str, Any] = {"entity": entity, "results": []}

        if monitor_id:
            nrql_query = (
                f"SELECT result, duration, locationLabel, error "
                f"FROM SyntheticCheck "
                f"WHERE monitorId = '{monitor_id}' "
                f"SINCE {hours} hours ago "
                f"ORDER BY timestamp DESC LIMIT 50"
            )
            nrql_result = await self.query_nrql(account_id, nrql_query)
            checks = (
                nrql_result.get("data", {})
                .get("actor", {})
                .get("account", {})
                .get("nrql", {})
                .get("results", [])
            )
            results["results"] = checks

        return results
