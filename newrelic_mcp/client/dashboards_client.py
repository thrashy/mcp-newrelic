"""
New Relic Dashboards API client.

Handles dashboard creation, widget management, and dashboard queries.
"""

import logging
from typing import Any

from ..types import ApiError, PaginatedResult
from ..utils.error_handling import API_ERRORS, handle_api_error
from ..utils.graphql_helpers import escape_nrql_string
from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)


class DashboardsClient:
    """Client for New Relic dashboards APIs"""

    def __init__(self, base: BaseNewRelicClient):
        self._base = base

    async def get_dashboards(
        self, account_id: str, search: str | None = None, guid: str | None = None, limit: int = 200
    ) -> PaginatedResult | ApiError:
        """Get list of dashboards using entity search with cursor-based pagination"""

        # Build entity search query string with escaped user input
        acct = int(account_id)
        if guid:
            search_query = f"accountId = {acct} AND type = 'DASHBOARD' AND id = '{escape_nrql_string(guid)}'"
        elif search:
            search_query = f"accountId = {acct} AND type = 'DASHBOARD' AND name LIKE '%{escape_nrql_string(search)}%'"
        else:
            search_query = f"accountId = {acct} AND type = 'DASHBOARD'"

        entity_fragment = """
                  ... on DashboardEntityOutline {
                    name
                    guid
                    permalink
                    createdAt
                    updatedAt
                  }
        """

        try:
            return await self._base.entity_search_paginated(search_query, entity_fragment, limit=limit)
        except API_ERRORS as e:
            return handle_api_error("get dashboards", e)

    async def create_dashboard(
        self, account_id: str, name: str, description: str = "", widgets: list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | ApiError:
        """Create a new dashboard"""
        widgets = widgets or []

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

        extracted = await self._base.execute_mutation(
            mutation,
            {"accountId": int(account_id), "dashboard": dashboard_input},
            "dashboardCreate",
            "create dashboard",
        )
        if isinstance(extracted, ApiError):
            return extracted

        entity_result: dict[str, Any] = extracted.get("entityResult", {})
        return entity_result

    async def update_dashboard(
        self, dashboard_guid: str, name: str | None = None, description: str | None = None
    ) -> dict[str, Any] | ApiError:
        """Rename a dashboard and/or update its description.

        dashboardUpdate replaces the entire dashboard, so the current pages and
        widgets are fetched first and resubmitted with only name/description changed.
        """
        fetch_query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              ... on DashboardEntity {
                name
                description
                permissions
                pages {
                  guid
                  name
                  description
                  widgets {
                    id
                    title
                    layout { column row width height }
                    visualization { id }
                    rawConfiguration
                  }
                }
              }
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(fetch_query, {"guid": dashboard_guid})
        except API_ERRORS as e:
            return handle_api_error("update dashboard", e)

        entity = result.get("data", {}).get("actor", {}).get("entity") or {}
        if not entity or not entity.get("pages"):
            return ApiError(f"Dashboard '{dashboard_guid}' not found")

        pages_input = []
        for page in entity["pages"]:
            widgets_input = []
            for w in page.get("widgets", []) or []:
                widget_input: dict[str, Any] = {
                    "id": w["id"],
                    "title": w.get("title", ""),
                    "visualization": w.get("visualization", {"id": "viz.line"}),
                    "rawConfiguration": w.get("rawConfiguration", {}),
                }
                if w.get("layout"):
                    widget_input["layout"] = w["layout"]
                widgets_input.append(widget_input)
            page_input: dict[str, Any] = {
                "guid": page.get("guid"),
                "name": page.get("name", "Page 1"),
                "widgets": widgets_input,
            }
            if page.get("description"):
                page_input["description"] = page["description"]
            pages_input.append(page_input)

        dashboard_input: dict[str, Any] = {
            "name": name if name is not None else entity.get("name", ""),
            "permissions": entity.get("permissions", "PUBLIC_READ_WRITE"),
            "pages": pages_input,
        }
        new_description = description if description is not None else entity.get("description")
        if new_description:
            dashboard_input["description"] = new_description

        mutation = """
        mutation($guid: EntityGuid!, $dashboard: DashboardInput!) {
          dashboardUpdate(guid: $guid, dashboard: $dashboard) {
            entityResult {
              guid
              name
              description
            }
            errors {
              description
              type
            }
          }
        }
        """

        extracted = await self._base.execute_mutation(
            mutation,
            {"guid": dashboard_guid, "dashboard": dashboard_input},
            "dashboardUpdate",
            "update dashboard",
        )
        if isinstance(extracted, ApiError):
            return extracted

        entity_result: dict[str, Any] = extracted.get("entityResult") or {}
        return {
            "success": True,
            "guid": entity_result.get("guid", dashboard_guid),
            "name": entity_result.get("name"),
            "description": entity_result.get("description"),
        }

    async def add_widget_to_dashboard(
        self, dashboard_guid: str, widget_config: dict[str, Any]
    ) -> dict[str, Any] | ApiError:
        """Add a widget to an existing dashboard - requires page GUID, not dashboard GUID"""

        get_pages_query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              ... on DashboardEntity {
                pages {
                  guid
                  name
                }
              }
            }
          }
        }
        """

        try:
            pages_result = await self._base.execute_graphql(get_pages_query, {"guid": dashboard_guid})
        except API_ERRORS as e:
            return handle_api_error("add widget to dashboard", e)

        entity = pages_result.get("data", {}).get("actor", {}).get("entity", {})
        pages = entity.get("pages", [])

        if not pages:
            return ApiError("No pages found in dashboard")

        page_guid = pages[0]["guid"]
        page_name = pages[0].get("name", "Page 1")

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

        add_result = await self._base.execute_mutation(
            mutation,
            {"guid": page_guid, "widgets": [widget_config]},
            "dashboardAddWidgetsToPage",
            "add widget to dashboard",
        )
        if isinstance(add_result, ApiError):
            return add_result

        return {
            "success": True,
            "message": f"Widget added successfully to page '{page_name}' of dashboard",
            "page_guid": page_guid,
            "page_name": page_name,
        }

    async def get_dashboard_widgets(self, dashboard_guid: str) -> dict[str, Any] | ApiError:
        """Get all widgets from a dashboard with their details"""
        query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              ... on DashboardEntity {
                name
                pages {
                  guid
                  name
                  description
                  widgets {
                    id
                    title
                    visualization {
                      id
                    }
                    rawConfiguration
                    configuration {
                      area {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                      bar {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                      billboard {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                      line {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                      pie {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                      table {
                        nrqlQueries {
                          accountId
                          query
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(query, {"guid": dashboard_guid})

            entity = result.get("data", {}).get("actor", {}).get("entity", {})
            if not entity:
                return ApiError("Dashboard not found")

            dashboard_name = entity.get("name", "Unknown")
            pages = entity.get("pages", [])

            widgets_info: dict[str, Any] = {
                "dashboard_name": dashboard_name,
                "dashboard_guid": dashboard_guid,
                "pages": [],
                "total_pages": len(pages) if pages else 0,
            }

            for page in pages or []:
                page_info: dict[str, Any] = {
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

        except API_ERRORS as e:
            return handle_api_error("get dashboard widgets", e)

    async def update_widget(
        self, page_guid: str, widget_id: str, widget_config: dict[str, Any]
    ) -> dict[str, Any] | ApiError:
        """Update an existing widget on a dashboard page"""
        mutation = """
        mutation($guid: EntityGuid!, $widgets: [DashboardUpdateWidgetInput!]!) {
          dashboardUpdateWidgetsInPage(guid: $guid, widgets: $widgets) {
            errors {
              description
              type
            }
          }
        }
        """

        widget_update_input = {"id": widget_id, **widget_config}

        extracted = await self._base.execute_mutation(
            mutation,
            {"guid": page_guid, "widgets": [widget_update_input]},
            "dashboardUpdateWidgetsInPage",
            "update widget",
        )
        if isinstance(extracted, ApiError):
            return extracted

        return {"success": True, "message": f"Widget '{widget_id}' updated successfully", "widget_id": widget_id}

    async def delete_widget(self, page_guid: str, widget_id: str) -> dict[str, Any] | ApiError:
        """Delete a widget by updating the page with all widgets except the target."""
        # Fetch current page widgets
        fetch_query = """
        query($guid: EntityGuid!) {
          actor {
            entity(guid: $guid) {
              ... on DashboardEntity {
                pages {
                  guid
                  name
                  description
                  widgets {
                    id
                    title
                    layout { column row width height }
                    visualization { id }
                    rawConfiguration
                  }
                }
              }
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(fetch_query, {"guid": page_guid})
        except API_ERRORS as e:
            return handle_api_error("delete widget", e)

        entity = result.get("data", {}).get("actor", {}).get("entity", {})
        if not entity:
            return ApiError(f"Page '{page_guid}' not found")

        # Find the page containing this widget
        target_page = None
        for page in entity.get("pages", []):
            if page.get("guid") == page_guid:
                target_page = page
                break

        if not target_page:
            return ApiError(f"Page with GUID '{page_guid}' not found in dashboard")

        # Filter out the target widget and rebuild the list
        remaining_widgets = []
        found = False
        for w in target_page.get("widgets", []):
            if str(w.get("id")) == str(widget_id):
                found = True
                continue
            widget_input: dict[str, Any] = {
                "id": w["id"],
                "title": w.get("title", ""),
                "visualization": w.get("visualization", {"id": "viz.line"}),
                "rawConfiguration": w.get("rawConfiguration", {}),
            }
            if w.get("layout"):
                widget_input["layout"] = w["layout"]
            remaining_widgets.append(widget_input)

        if not found:
            return ApiError(f"Widget '{widget_id}' not found on page '{page_guid}'")

        if not remaining_widgets:
            return ApiError(
                "Cannot delete the last widget on a page. Use delete_dashboard to remove the entire dashboard instead."
            )

        # dashboardUpdateWidgetsInPage cannot remove widgets — only dashboardUpdatePage
        # replaces the full widget set, dropping any widget omitted from it.
        update_mutation = """
        mutation($guid: EntityGuid!, $page: DashboardUpdatePageInput!) {
          dashboardUpdatePage(guid: $guid, page: $page) {
            errors {
              description
              type
            }
          }
        }
        """
        page_input: dict[str, Any] = {
            "name": target_page.get("name", "Page 1"),
            "widgets": remaining_widgets,
        }
        if target_page.get("description"):
            page_input["description"] = target_page["description"]

        extracted = await self._base.execute_mutation(
            update_mutation, {"guid": page_guid, "page": page_input}, "dashboardUpdatePage", "delete widget"
        )
        if isinstance(extracted, ApiError):
            return extracted

        return {"success": True, "message": f"Widget '{widget_id}' deleted successfully", "widget_id": widget_id}

    async def delete_dashboard(self, dashboard_guid: str) -> dict[str, Any] | ApiError:
        """Delete a dashboard by GUID"""
        mutation = """
        mutation($guid: EntityGuid!) {
          dashboardDelete(guid: $guid) {
            status
            errors {
              description
              type
            }
          }
        }
        """

        delete_result = await self._base.execute_mutation(
            mutation, {"guid": dashboard_guid}, "dashboardDelete", "delete dashboard"
        )
        if isinstance(delete_result, ApiError):
            return delete_result

        return {
            "success": True,
            "message": f"Dashboard '{dashboard_guid}' deleted successfully",
            "status": delete_result.get("status"),
        }
