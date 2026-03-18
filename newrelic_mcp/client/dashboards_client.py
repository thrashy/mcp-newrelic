"""
New Relic Dashboards API client.

Handles dashboard creation, widget management, and dashboard queries.
"""

import logging
from typing import Any

from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)


class DashboardsClient(BaseNewRelicClient):
    """Client for New Relic dashboards APIs"""

    async def get_dashboards(
        self, account_id: str, search: str = None, guid: str = None, limit: int = 200
    ) -> dict[str, Any]:
        """Get list of dashboards using entity search with search filtering"""

        # If searching for a specific GUID, modify the query
        if guid:
            search_query = f"accountId = {account_id} AND type = 'DASHBOARD' AND id = '{guid}'"
        elif search:
            # Search in dashboard names - New Relic supports name filtering
            search_query = f"accountId = {account_id} AND type = 'DASHBOARD' AND name LIKE '%{search}%'"
        else:
            search_query = f"accountId = {account_id} AND type = 'DASHBOARD'"

        # API effectively caps at 200 dashboards regardless of limit
        limit = min(limit, 200)

        query = f"""
        query {{
          actor {{
            entitySearch(query: "{search_query}", options: {{limit: {limit}}}) {{
              results {{
                entities {{
                  ... on DashboardEntityOutline {{
                    name
                    guid
                    permalink
                    createdAt
                    updatedAt
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        try:
            result = await self.execute_graphql(query)

            logger.debug(f"Dashboard query response: {result}")

            # Check if we got a valid response structure
            data = result.get("data", {})
            actor = data.get("actor", {})
            entity_search = actor.get("entitySearch", {})

            if not entity_search:
                logger.warning(f"No entity search data returned for account ID {account_id}")
                return {
                    "error": f"No entity search data for account {account_id}. Check account ID and permissions.",
                    "type": "no_account_access",
                }

            results = entity_search.get("results", {})
            entities = results.get("entities", [])
            next_cursor = results.get("nextCursor")

            logger.info(f"Found {len(entities)} dashboards for account {account_id}, nextCursor: {next_cursor}")

            return {"entities": entities, "nextCursor": next_cursor, "hasMore": bool(next_cursor)}

        except Exception as e:
            logger.error(f"Dashboard query failed: {e}")
            # Return error info for better debugging
            return {"error": str(e), "type": "query_failed"}

    async def create_dashboard(
        self, account_id: str, name: str, description: str = "", widgets: list[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Create a new dashboard"""
        widgets = widgets or []

        # Basic dashboard structure
        dashboard_input = {
            "name": name,
            "description": description,
            "permissions": "PUBLIC_READ_WRITE",
            "pages": [{"name": name, "description": description, "widgets": widgets}],
        }

        mutation = """
        mutation($accountId: Int!, $dashboard: DashboardInput!) {
          dashboardCreate(accountId: $accountId, dashboard: $dashboard) {
            entityResult {
              guid
              name
            }
            errors {
              description
              type
            }
          }
        }
        """

        try:
            result = await self.execute_graphql(mutation, {"accountId": int(account_id), "dashboard": dashboard_input})

            create_result = result.get("data", {}).get("dashboardCreate", {})
            if create_result.get("errors"):
                return {"error": f"Dashboard creation failed: {create_result['errors']}"}

            return create_result.get("entityResult", {})

        except Exception as e:
            logger.error(f"Dashboard creation failed: {e}")
            return {"error": str(e)}

    async def add_widget_to_dashboard(self, dashboard_guid: str, widget_config: dict[str, Any]) -> dict[str, Any]:
        """Add a widget to an existing dashboard - requires page GUID, not dashboard GUID"""

        # First, get the dashboard pages to find the page GUID
        get_pages_query = f"""
        query {{
          actor {{
            entity(guid: "{dashboard_guid}") {{
              ... on DashboardEntity {{
                pages {{
                  guid
                  name
                }}
              }}
            }}
          }}
        }}
        """

        try:
            # Get dashboard pages
            pages_result = await self.execute_graphql(get_pages_query)

            entity = pages_result.get("data", {}).get("actor", {}).get("entity", {})
            pages = entity.get("pages", [])

            if not pages:
                return {"error": "No pages found in dashboard"}

            # Use the first page GUID (most dashboards have one page)
            page_guid = pages[0]["guid"]
            page_name = pages[0].get("name", "Page 1")

            # Now add widget to the page
            mutation = """
            mutation($guid: EntityGuid!, $widgets: [DashboardWidgetInput!]!) {
              dashboardAddWidgetsToPage(guid: $guid, widgets: $widgets) {
                errors {
                  description
                  type
                }
              }
            }
            """

            # Add widget using the page GUID
            result = await self.execute_graphql(
                mutation,
                {
                    "guid": page_guid,  # Use page GUID, not dashboard GUID
                    "widgets": [widget_config],
                },
            )

            add_result = result.get("data", {}).get("dashboardAddWidgetsToPage", {})
            if add_result.get("errors"):
                return {"error": f"Widget addition failed: {add_result['errors']}"}

            return {
                "success": True,
                "message": f"Widget added successfully to page '{page_name}' of dashboard",
                "page_guid": page_guid,
                "page_name": page_name,
            }

        except Exception as e:
            logger.error(f"Widget addition failed: {e}")
            return {"error": str(e)}

    async def get_dashboard_widgets(self, dashboard_guid: str) -> dict[str, Any]:
        """Get all widgets from a dashboard with their details"""
        query = f"""
        query {{
          actor {{
            entity(guid: "{dashboard_guid}") {{
              ... on DashboardEntity {{
                name
                pages {{
                  guid
                  name
                  description
                  widgets {{
                    id
                    title
                    visualization {{
                      id
                    }}
                    rawConfiguration
                    configuration {{
                      area {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                      bar {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                      billboard {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                      line {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                      pie {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                      table {{
                        nrqlQueries {{
                          accountId
                          query
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        try:
            result = await self.execute_graphql(query)

            entity = result.get("data", {}).get("actor", {}).get("entity", {})
            if not entity:
                return {"error": "Dashboard not found"}

            dashboard_name = entity.get("name", "Unknown")
            pages = entity.get("pages", [])

            widgets_info = {
                "dashboard_name": dashboard_name,
                "dashboard_guid": dashboard_guid,
                "pages": [],
                "total_pages": len(pages) if pages else 0,
            }

            for page in pages or []:
                page_info = {
                    "page_guid": page.get("guid"),
                    "page_name": page.get("name", "Unnamed Page"),
                    "widgets": [],
                }

                for widget in page.get("widgets", []):
                    if not widget:
                        continue

                    viz_obj = widget.get("visualization") or {}
                    config_obj = widget.get("configuration") or {}

                    widget_info = {
                        "widget_id": widget.get("id"),
                        "title": widget.get("title") or "Untitled Widget",
                        "visualization_type": viz_obj.get("id") or "unknown",
                        "configuration": config_obj,
                        "rawConfiguration": widget.get("rawConfiguration"),
                    }
                    page_info["widgets"].append(widget_info)

                widgets_info["pages"].append(page_info)

            return widgets_info

        except Exception as e:
            logger.error(f"Failed to get dashboard widgets: {e}")
            return {"error": str(e)}

    async def update_widget(self, page_guid: str, widget_id: str, widget_config: dict[str, Any]) -> dict[str, Any]:
        """Update an existing widget on a dashboard page"""
        mutation = """
        mutation($guid: EntityGuid!, $widgets: [DashboardWidgetUpdateInput!]!) {
          dashboardUpdateWidgetsInPage(guid: $guid, widgets: $widgets) {
            errors {
              description
              type
            }
          }
        }
        """

        # Create update input with widget ID
        widget_update_input = {"id": widget_id, **widget_config}

        try:
            result = await self.execute_graphql(mutation, {"guid": page_guid, "widgets": [widget_update_input]})

            update_result = result.get("data", {}).get("dashboardUpdateWidgetsInPage", {})
            if update_result.get("errors"):
                return {"error": f"Widget update failed: {update_result['errors']}"}

            return {"success": True, "message": f"Widget '{widget_id}' updated successfully", "widget_id": widget_id}

        except Exception as e:
            logger.error(f"Widget update failed: {e}")
            return {"error": str(e)}

    async def delete_widget(self, page_guid: str, widget_id: str) -> dict[str, Any]:
        """Delete a widget from a dashboard page"""
        mutation = """
        mutation($guid: EntityGuid!, $widgetIds: [String!]!) {
          dashboardDeleteWidgetsFromPage(guid: $guid, widgetIds: $widgetIds) {
            errors {
              description
              type
            }
          }
        }
        """

        try:
            result = await self.execute_graphql(mutation, {"guid": page_guid, "widgetIds": [widget_id]})

            delete_result = result.get("data", {}).get("dashboardDeleteWidgetsFromPage", {})
            if delete_result.get("errors"):
                return {"error": f"Widget deletion failed: {delete_result['errors']}"}

            return {"success": True, "message": f"Widget '{widget_id}' deleted successfully", "widget_id": widget_id}

        except Exception as e:
            logger.error(f"Widget deletion failed: {e}")
            return {"error": str(e)}
