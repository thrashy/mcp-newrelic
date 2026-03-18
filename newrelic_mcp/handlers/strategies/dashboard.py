"""Dashboard tool handlers using Strategy pattern"""

from typing import Any

from mcp.types import TextContent

from ...utils.dashboard_formatters import (
    build_raw_nrql_queries,
    build_widget_configuration,
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

        result = await self.client.get_dashboards(account_id, search=search, guid=guid, limit=limit)

        if "error" in result:
            return self._handle_dashboard_error(result, account_id)

        dashboards = result.get("entities", [])
        return self._format_dashboard_list(dashboards, search, guid)

    def _handle_dashboard_error(self, result: dict[str, Any], _account_id: str) -> list[TextContent]:
        """Handle dashboard retrieval errors"""
        error_info = result
        error_type = error_info.get("type", "unknown")

        if error_type == "no_account_access":
            error_msg = (
                f"**Account Access Issue**\n\n"
                f"{error_info['error']}\n\n"
                f"**Possible causes:**\n"
                f"1. **Wrong Account ID** - Double-check your New Relic account ID\n"
                f"2. **API Key Permissions** - Your API key may not have access to this account\n"
                f"3. **User API Key Required** - Ensure you're using a User API key, not an Ingest key\n"
                f"4. **Account Region Mismatch** - Check if your account is in EU region (currently using {self.config.region})"
            )
        else:
            error_msg = f"Error retrieving dashboards: {error_info['error']}"

        return [TextContent(type="text", text=error_msg)]

    def _format_dashboard_list(self, dashboards: list[dict], search: str, guid: str) -> list[TextContent]:
        """Format dashboard list for display"""
        dashboard_text = format_dashboard_list(dashboards, search, guid, limit_display=50)
        return self._create_success_response(dashboard_text)


class CreateDashboardHandler(ToolHandlerStrategy):
    """Handler for dashboard creation"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        dashboard_name = arguments["name"]
        description = arguments.get("description", "")

        result = await self.client.create_dashboard(account_id, dashboard_name, description)

        if "error" in result:
            return self._create_error_response(f"creating dashboard '{dashboard_name}': {result['error']}")

        guid = result.get("guid", "Unknown")
        permalink = result.get("permalink", "")

        response_text = f"Dashboard '{dashboard_name}' created successfully!\n"
        response_text += f"GUID: {guid}\n"
        if permalink:
            response_text += f"URL: {permalink}\n"
        response_text += "\nYou can now add widgets to this dashboard using the add_widget_to_dashboard tool."

        return self._create_success_response(response_text)


class AddWidgetHandler(ToolHandlerStrategy):
    """Handler for adding widgets to dashboards"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        dashboard_guid = arguments["dashboard_guid"]
        widget_title = arguments["widget_title"]
        widget_query = arguments["widget_query"]
        widget_type = arguments.get("widget_type", "line")
        raw_configuration = arguments.get("raw_configuration")

        # Create widget configuration
        widget_config = {
            "title": widget_title,
            "configuration": build_widget_configuration(widget_type, account_id, widget_query),
            "visualization": {"id": f"viz.{widget_type}"},
        }

        if raw_configuration is not None:
            if "nrqlQueries" not in raw_configuration:
                raw_configuration["nrqlQueries"] = build_raw_nrql_queries(account_id, widget_query)
            widget_config["rawConfiguration"] = raw_configuration

        result = await self.client.add_widget_to_dashboard(dashboard_guid, widget_config)

        if "error" in result:
            return self._create_error_response(f"adding widget to dashboard: {result['error']}")

        suffix = " (with custom rawConfiguration)" if raw_configuration else ""
        return self._create_success_response(
            f"Widget '{widget_title}' ({widget_type}) added to dashboard successfully{suffix}!"
        )


class SearchDashboardsHandler(ToolHandlerStrategy):
    """Handler for dashboard search"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        search = arguments.get("search")
        guid = arguments.get("guid")

        # Use get_dashboards method with search functionality
        result = await self.client.get_dashboards(account_id, search=search, guid=guid, limit=200)

        if "error" in result:
            return self._create_error_response(f"searching dashboards: {result['error']}")

        dashboards = result.get("entities", [])

        # Format and return dashboard list
        dashboard_text = format_dashboard_list(dashboards, search, guid, limit_display=25)
        return self._create_success_response(dashboard_text)


class GetWidgetsHandler(ToolHandlerStrategy):
    """Handler for getting dashboard widgets"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        dashboard_guid = arguments["dashboard_guid"]
        result = await self.client.get_dashboard_widgets(dashboard_guid)

        if "error" in result:
            return self._create_error_response(f"getting dashboard widgets: {result['error']}")

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

        widgets_text = (
            f"Found {total_widgets} widgets across {total_pages} page(s) for dashboard '{dashboard_name}':\n\n"
        )

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
                    nrql_queries = extract_nrql_queries(widget.get("configuration", {}))

                    widgets_text += f"  - **{title}**\n"
                    widgets_text += f"    Widget ID: {widget_id}\n"
                    widgets_text += f"    Type: {viz_type}\n"

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
        page_guid = arguments["page_guid"]
        widget_id = arguments["widget_id"]
        widget_title = arguments.get("widget_title")
        widget_query = arguments.get("widget_query")
        widget_type = arguments.get("widget_type", "line")
        raw_configuration = arguments.get("raw_configuration")

        # Build widget update configuration
        widget_config = {"id": widget_id}

        if widget_title:
            widget_config["title"] = widget_title

        if widget_query:
            widget_config["configuration"] = build_widget_configuration(widget_type, account_id, widget_query)
            widget_config["visualization"] = {"id": f"viz.{widget_type}"}

        if raw_configuration is not None:
            if "nrqlQueries" not in raw_configuration and widget_query:
                raw_configuration["nrqlQueries"] = build_raw_nrql_queries(account_id, widget_query)
            widget_config["rawConfiguration"] = raw_configuration
            if "visualization" not in widget_config:
                widget_config["visualization"] = {"id": f"viz.{widget_type}"}

        result = await self.client.update_widget(page_guid, widget_id, widget_config)

        if "error" in result:
            return self._create_error_response(f"updating widget: {result['error']}")

        suffix = " (with custom rawConfiguration)" if raw_configuration else ""
        return self._create_success_response(f"Widget {widget_id} updated successfully{suffix}!")


class DeleteWidgetHandler(ToolHandlerStrategy):
    """Handler for deleting widgets"""

    async def handle(self, arguments: dict[str, Any], _account_id: str) -> list[TextContent]:
        page_guid = arguments["page_guid"]
        widget_id = arguments["widget_id"]

        result = await self.client.delete_widget(page_guid, widget_id)

        if "error" in result:
            return self._create_error_response(f"deleting widget: {result['error']}")

        return self._create_success_response(f"Widget {widget_id} deleted successfully!")
