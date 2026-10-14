"""Dashboard tool handlers using Strategy pattern"""

import json
from typing import Any

from mcp.types import TextContent

from ...types import ApiError, ToolError
from ...utils.dashboard_formatters import (
    build_raw_nrql_queries,
    extract_nrql_queries,
    format_dashboard_list,
)
from .base import ToolHandlerStrategy


class GetDashboardsHandler(ToolHandlerStrategy):
    """Handler for dashboard retrieval"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        search = arguments.get("search")
        guid = arguments.get("guid")
        limit = arguments.get("limit", 200)

        result = await self.client.dashboards.get_dashboards(account_id, search=search, guid=guid, limit=limit)

        if isinstance(result, ApiError):
            return self._handle_dashboard_error(result)

        return self._create_success_response(format_dashboard_list(result.items, search, guid, limit_display=50))

    def _handle_dashboard_error(self, error: ApiError) -> list[TextContent]:
        """Handle dashboard retrieval errors"""
        error_msg = (
            f"**Account Access Issue**\n\n"
            f"{error.message}\n\n"
            f"**Possible causes:**\n"
            f"1. **Wrong Account ID** - Double-check your New Relic account ID\n"
            f"2. **API Key Permissions** - Your API key may not have access to this account\n"
            f"3. **User API Key Required** - Ensure you're using a User API key, not an Ingest key\n"
            f"4. **Account Region Mismatch** - Check if your account is in EU region (currently using {self.config.region})"
        )
        return [TextContent(type="text", text=error_msg)]


class CreateDashboardHandler(ToolHandlerStrategy):
    """Handler for dashboard creation"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        dashboard_name = arguments["name"]
        description = arguments.get("description", "")
        permissions = arguments.get("permissions", "PUBLIC_READ_WRITE")

        result = self._unwrap(
            await self.client.dashboards.create_dashboard(
                account_id, dashboard_name, description, permissions=permissions
            ),
            f"creating dashboard '{dashboard_name}'",
        )

        guid = result.get("guid", "Unknown")
        permalink = result.get("permalink", "")

        response_text = f"Dashboard '{dashboard_name}' created successfully!\n"
        response_text += f"GUID: {guid}\n"
        if permalink:
            response_text += f"URL: {permalink}\n"
        response_text += "\nYou can now add widgets to this dashboard using the add_widget_to_dashboard tool."

        return self._create_success_response(response_text)


class UpdateDashboardHandler(ToolHandlerStrategy):
    """Handler for renaming a dashboard, updating its description, or replacing its template variables"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments)
        name = arguments.get("name")
        description = arguments.get("description")
        variables = arguments.get("variables")
        permissions = arguments.get("permissions")

        if name is None and description is None and variables is None and permissions is None:
            raise ToolError("Provide at least one of 'name', 'description', 'variables' or 'permissions' to update.")

        result = self._unwrap(
            await self.client.dashboards.update_dashboard(
                dashboard_guid, name=name, description=description, variables=variables, permissions=permissions
            ),
            f"updating dashboard '{dashboard_guid}'",
        )

        updated_name = result.get("name") or dashboard_guid
        return self._create_success_response(f"Dashboard '{updated_name}' updated successfully.")


class AddWidgetHandler(ToolHandlerStrategy):
    """Handler for adding widgets to dashboards"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")
        page_guid = self._require_guid(arguments, "page_guid") if arguments.get("page_guid") else None
        widget_title = arguments["widget_title"]
        widget_query = arguments.get("widget_query")
        widget_type = arguments.get("widget_type") or "line"
        text = arguments.get("text")
        raw_configuration = dict(arguments.get("raw_configuration") or {})

        if widget_type == "markdown":
            if not text and "text" not in raw_configuration:
                raise ToolError("A markdown widget needs 'text'.")
            if text:
                raw_configuration["text"] = text
        elif not widget_query and "nrqlQueries" not in raw_configuration:
            raise ToolError("Provide 'widget_query' (or nrqlQueries in raw_configuration) for a chart widget.")
        elif widget_query and "nrqlQueries" not in raw_configuration:
            raw_configuration["nrqlQueries"] = build_raw_nrql_queries(account_id, widget_query)

        widget_config: dict[str, Any] = {
            "title": widget_title,
            "visualization": {"id": f"viz.{widget_type}"},
            "rawConfiguration": raw_configuration,
        }
        if arguments.get("layout") is not None:
            widget_config["layout"] = arguments["layout"]
        widget_config.update(_link_fields(arguments))

        result = self._unwrap(
            await self.client.dashboards.add_widget_to_dashboard(dashboard_guid, widget_config, page_guid=page_guid),
            "adding widget to dashboard",
        )

        page_name = result.get("page_name", "")
        return self._create_success_response(
            f"Widget '{widget_title}' ({widget_type}) added to page '{page_name}' successfully!"
        )


class GetWidgetsHandler(ToolHandlerStrategy):
    """Handler for getting dashboard widgets"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")

        result = self._unwrap(
            await self.client.dashboards.get_dashboard_widgets(dashboard_guid),
            "getting dashboard widgets",
        )

        pages = result.get("pages", [])
        dashboard_name = result.get("dashboard_name", "Unknown")
        total_pages = result.get("total_pages", 0)

        # Count total widgets across all pages
        total_widgets = sum(len(page.get("widgets", [])) for page in pages)

        if total_widgets == 0:
            return self._create_success_response(
                f"No widgets found for dashboard '{dashboard_name}' (GUID: {dashboard_guid}).\n"
                f"Dashboard has {total_pages} page(s), but no widgets were found on any page."
            )

        widgets_text = f"Found {total_widgets} widgets across {total_pages} page(s) for dashboard '{dashboard_name}':\n"
        if result.get("permissions"):
            widgets_text += f"Permissions: {result['permissions']}\n"
        for variable in result.get("variables") or []:
            widgets_text += (
                f"Variable: {{{{{variable.get('name')}}}}} ({variable.get('type')}, '{variable.get('title')}')\n"
            )
        widgets_text += "\n"

        for page in pages:
            page_name = page.get("page_name", "Unnamed Page")
            page_guid = page.get("page_guid", "Unknown")
            widgets = page.get("widgets", [])

            if widgets:
                widgets_text += f"**Page: {page_name}** (GUID: {page_guid})\n"

                for widget in widgets:
                    title = widget.get("title") or "Untitled Widget"
                    widget_id = widget.get("widget_id") or "Unknown"
                    viz_type = widget.get("visualization_type") or "Unknown"

                    # Extract NRQL queries if available
                    nrql_queries = extract_nrql_queries(widget.get("configuration") or {}) or [
                        q["query"]
                        for q in (widget.get("rawConfiguration") or {}).get("nrqlQueries") or []
                        if q.get("query")
                    ]

                    widgets_text += f"  - **{title}**\n"
                    widgets_text += f"    Widget ID: {widget_id}\n"
                    widgets_text += f"    Type: {viz_type}\n"
                    layout = widget.get("layout")
                    if layout:
                        widgets_text += (
                            f"    Layout: column {layout.get('column')}, row {layout.get('row')}, "
                            f"width {layout.get('width')}, height {layout.get('height')}\n"
                        )
                    if widget.get("link_url"):
                        widgets_text += f"    Link: {widget['link_url']}\n"
                    if widget.get("linked_entity_guids"):
                        widgets_text += f"    Linked entities: {', '.join(widget['linked_entity_guids'])}\n"

                    if nrql_queries:
                        widgets_text += "    NRQL Queries:\n"
                        for i, query in enumerate(nrql_queries, 1):
                            widgets_text += f"      {i}. {query}\n"

                    raw_config = widget.get("rawConfiguration")
                    if raw_config:
                        widgets_text += f"    rawConfiguration: {raw_config}\n"

                    widgets_text += "\n"

                widgets_text += "\n"

        return self._create_success_response(widgets_text)


class UpdateWidgetHandler(ToolHandlerStrategy):
    """Handler for updating widgets"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        page_guid = self._require_guid(arguments, "page_guid")
        widget_id = arguments["widget_id"]
        widget_title = arguments.get("widget_title")
        widget_query = arguments.get("widget_query")
        widget_type = arguments.get("widget_type")
        raw_configuration = arguments.get("raw_configuration")
        layout = arguments.get("layout")

        # dashboardUpdateWidgetsInPage replaces the whole widget, so start from its current state.
        current = self._unwrap(
            await self.client.dashboards.get_widget(page_guid, widget_id),
            "looking up the widget's current state",
        )

        if raw_configuration is None:
            raw_configuration = current.get("rawConfiguration") or {}
        if widget_query and "nrqlQueries" not in (arguments.get("raw_configuration") or {}):
            raw_configuration = {**raw_configuration, "nrqlQueries": build_raw_nrql_queries(account_id, widget_query)}
        if arguments.get("text") is not None:
            raw_configuration = {**raw_configuration, "text": arguments["text"]}

        visualization = {"id": f"viz.{widget_type}"} if widget_type else current.get("visualization")
        widget_config: dict[str, Any] = {
            "title": widget_title or current.get("title", ""),
            "visualization": visualization,
            "rawConfiguration": raw_configuration,
        }
        if layout is not None or current.get("layout"):
            widget_config["layout"] = layout if layout is not None else current["layout"]
        if (current.get("link") or {}).get("url"):
            widget_config["link"] = {"url": current["link"]["url"]}
        current_linked = [e["guid"] for e in current.get("linkedEntities") or [] if e and e.get("guid")]
        if current_linked:
            widget_config["linkedEntityGuids"] = current_linked
        widget_config.update(_link_fields(arguments))

        self._unwrap(
            await self.client.dashboards.update_widget(page_guid, widget_id, widget_config),
            "updating widget",
        )

        suffix = " (with custom rawConfiguration)" if raw_configuration else ""
        return self._create_success_response(f"Widget {widget_id} updated successfully{suffix}!")


class DeleteWidgetHandler(ToolHandlerStrategy):
    """Handler for deleting widgets"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        page_guid = self._require_guid(arguments, "page_guid")
        widget_id = arguments["widget_id"]

        self._unwrap(
            await self.client.dashboards.delete_widget(page_guid, widget_id),
            "deleting widget",
        )

        return self._create_success_response(f"Widget {widget_id} deleted successfully!")


class DeleteDashboardHandler(ToolHandlerStrategy):
    """Handler for deleting dashboards"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")

        self._unwrap(
            await self.client.dashboards.delete_dashboard(dashboard_guid),
            "deleting dashboard",
        )

        return self._create_success_response(f"Dashboard '{dashboard_guid}' deleted successfully.")


class ExportDashboardHandler(ToolHandlerStrategy):
    """Handler for exporting a dashboard's full definition as JSON"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")
        dashboard_input = self._unwrap(
            await self.client.dashboards.export_dashboard(dashboard_guid),
            f"exporting dashboard '{dashboard_guid}'",
        )
        return self._create_success_response(json.dumps(dashboard_input, indent=2))


class ReplaceDashboardHandler(ToolHandlerStrategy):
    """Handler for replacing a dashboard's whole definition"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")
        dashboard = arguments["dashboard"]
        if isinstance(dashboard, str):
            try:
                dashboard = json.loads(dashboard)
            except json.JSONDecodeError as e:
                raise ToolError(f"'dashboard' is not valid JSON: {e}") from e
        if not isinstance(dashboard, dict) or not dashboard.get("name") or not dashboard.get("pages"):
            raise ToolError("'dashboard' must be a DashboardInput object with at least 'name' and 'pages'.")
        dashboard.setdefault("permissions", "PUBLIC_READ_WRITE")

        result = self._unwrap(
            await self.client.dashboards.replace_dashboard(dashboard_guid, dashboard),
            f"replacing dashboard '{dashboard_guid}'",
        )
        pages = result.get("pages") or []
        return self._create_success_response(
            f"Dashboard '{result.get('name') or dashboard_guid}' replaced ({len(pages)} page(s))."
        )


class AddDashboardPageHandler(ToolHandlerStrategy):
    """Handler for appending a page to a dashboard"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")
        name = arguments["name"]
        result = self._unwrap(
            await self.client.dashboards.add_dashboard_page(dashboard_guid, name, arguments.get("description")),
            f"adding page to dashboard '{dashboard_guid}'",
        )
        return self._create_success_response(
            f"Page '{name}' added. Page GUID: {result.get('page_guid')}\n"
            "Pass it as page_guid to add_widget_to_dashboard to put widgets on this page."
        )


class UndeleteDashboardHandler(ToolHandlerStrategy):
    """Handler for restoring a deleted dashboard"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = self._require_guid(arguments, "dashboard_guid")
        self._unwrap(
            await self.client.dashboards.undelete_dashboard(dashboard_guid),
            f"undeleting dashboard '{dashboard_guid}'",
        )
        return self._create_success_response(f"Dashboard '{dashboard_guid}' restored.")


class CreateDashboardSnapshotHandler(ToolHandlerStrategy):
    """Handler for creating a public static snapshot of a dashboard page"""

    requires_account_id = False

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        page_guid = self._require_guid(arguments, "page_guid")
        image_format = arguments.get("format", "PNG")
        result = self._unwrap(
            await self.client.dashboards.create_dashboard_snapshot_url(
                page_guid, image_format=image_format, variables=arguments.get("variables")
            ),
            f"creating snapshot of page '{page_guid}'",
        )
        return self._create_success_response(
            f"Snapshot ({image_format}): {result['url']}\nAnyone with this link can view it without a New Relic login."
        )


def _link_fields(arguments: dict[str, Any]) -> dict[str, Any]:
    """Widget link fields from tool arguments; only keys the caller passed."""
    fields: dict[str, Any] = {}
    if arguments.get("link_url"):
        fields["link"] = {"url": arguments["link_url"]}
    if arguments.get("linked_entity_guids") is not None:
        fields["linkedEntityGuids"] = list(arguments["linked_entity_guids"])
    return fields
