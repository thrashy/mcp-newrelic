"""Tests for dashboard tool handler strategies."""

import json

import pytest

from newrelic_mcp.handlers.strategies.dashboard import (
    AddDashboardPageHandler,
    AddWidgetHandler,
    CreateDashboardHandler,
    CreateDashboardSnapshotHandler,
    DeleteDashboardHandler,
    DeleteWidgetHandler,
    ExportDashboardHandler,
    GetDashboardsHandler,
    GetWidgetsHandler,
    ReplaceDashboardHandler,
    UndeleteDashboardHandler,
    UpdateDashboardHandler,
    UpdateWidgetHandler,
)
from newrelic_mcp.types import ApiError, PaginatedResult, ToolError


class TestGetDashboardsHandler:
    async def test_success_returns_formatted_list(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(
            items=[
                {"name": "My Dashboard", "guid": "abc123", "createdAt": "2026-01-01", "permalink": "https://nr.com/d/1"}
            ]
        )
        handler = GetDashboardsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "My Dashboard" in result[0].text
        assert "abc123" in result[0].text

    async def test_empty_dashboards(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(items=[])
        handler = GetDashboardsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "No dashboards found" in result[0].text

    async def test_error_response(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = ApiError("query failed")
        handler = GetDashboardsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "Error" in result[0].text or "query failed" in result[0].text

    async def test_no_account_access_error(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = ApiError("No entity search data for account 999")
        handler = GetDashboardsHandler(mock_client, config)
        result = await handler.handle({}, "999")

        assert "Account Access" in result[0].text

    async def test_search_filter_passed(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(
            items=[{"name": "Prod Dashboard", "guid": "g1", "createdAt": "2026-01-01"}]
        )
        handler = GetDashboardsHandler(mock_client, config)
        await handler.handle({"search": "Prod"}, "1234567")

        mock_client.dashboards.get_dashboards.assert_called_once_with("1234567", search="Prod", guid=None, limit=200)

    async def test_guid_filter_passed(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(
            items=[{"name": "Specific", "guid": "xyz", "createdAt": "2026-01-01"}]
        )
        handler = GetDashboardsHandler(mock_client, config)
        await handler.handle({"guid": "xyz"}, "1234567")

        mock_client.dashboards.get_dashboards.assert_called_once_with("1234567", search=None, guid="xyz", limit=200)


class TestCreateDashboardHandler:
    async def test_success(self, mock_client, config):
        mock_client.dashboards.create_dashboard.return_value = {"guid": "new-guid", "permalink": "https://nr.com/d/new"}
        handler = CreateDashboardHandler(mock_client, config)
        result = await handler.handle({"name": "My New Dashboard", "description": "Test"}, "1234567")

        assert "created successfully" in result[0].text
        assert "new-guid" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.dashboards.create_dashboard.return_value = ApiError("permission denied")
        handler = CreateDashboardHandler(mock_client, config)
        with pytest.raises(ToolError, match="permission denied"):
            await handler.handle({"name": "Fail"}, "1234567")


class TestAddWidgetHandler:
    async def test_success(self, mock_client, config):
        mock_client.dashboards.add_widget_to_dashboard.return_value = {"success": True}
        handler = AddWidgetHandler(mock_client, config)
        result = await handler.handle(
            {
                "dashboard_guid": "MTIzNDU2Nzg5MA==",
                "widget_title": "My Widget",
                "widget_query": "SELECT count(*) FROM Transaction",
            },
            "1234567",
        )

        assert "added" in result[0].text.lower() and "success" in result[0].text.lower()

    async def test_with_raw_configuration(self, mock_client, config):
        mock_client.dashboards.add_widget_to_dashboard.return_value = {"success": True, "page_name": "P1"}
        handler = AddWidgetHandler(mock_client, config)
        await handler.handle(
            {
                "dashboard_guid": "MTIzNDU2Nzg5MA==",
                "widget_title": "Custom",
                "widget_query": "SELECT 1",
                "widget_type": "stacked-bar",
                "raw_configuration": {"facet": {"showOtherSeries": True}},
            },
            "1234567",
        )

        dashboard_guid, sent = mock_client.dashboards.add_widget_to_dashboard.call_args.args
        assert sent == {
            "title": "Custom",
            "visualization": {"id": "viz.stacked-bar"},
            "rawConfiguration": {
                "facet": {"showOtherSeries": True},
                "nrqlQueries": [{"accountIds": [1234567], "query": "SELECT 1"}],
            },
        }
        assert "configuration" not in sent
        assert mock_client.dashboards.add_widget_to_dashboard.call_args.kwargs == {"page_guid": None}

    async def test_markdown_needs_no_query(self, mock_client, config):
        mock_client.dashboards.add_widget_to_dashboard.return_value = {"success": True, "page_name": "P1"}
        handler = AddWidgetHandler(mock_client, config)
        await handler.handle(
            {
                "dashboard_guid": "MTIzNDU2Nzg5MA==",
                "widget_title": "Notes",
                "widget_type": "markdown",
                "text": "# How it works",
                "page_guid": "cGFnZUd1aWQxMjM=",
                "link_url": "https://example.com",
                "linked_entity_guids": ["ZGFzaA=="],
            },
            "1234567",
        )

        _, sent = mock_client.dashboards.add_widget_to_dashboard.call_args.args
        assert sent["visualization"] == {"id": "viz.markdown"}
        assert sent["rawConfiguration"] == {"text": "# How it works"}
        assert sent["link"] == {"url": "https://example.com"}
        assert sent["linkedEntityGuids"] == ["ZGFzaA=="]
        assert mock_client.dashboards.add_widget_to_dashboard.call_args.kwargs == {"page_guid": "cGFnZUd1aWQxMjM="}

    async def test_markdown_without_text_rejected(self, mock_client, config):
        handler = AddWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="text"):
            await handler.handle(
                {"dashboard_guid": "MTIzNDU2Nzg5MA==", "widget_title": "N", "widget_type": "markdown"}, "1234567"
            )
        mock_client.dashboards.add_widget_to_dashboard.assert_not_called()

    async def test_chart_without_query_rejected(self, mock_client, config):
        handler = AddWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="widget_query"):
            await handler.handle({"dashboard_guid": "MTIzNDU2Nzg5MA==", "widget_title": "C"}, "1234567")
        mock_client.dashboards.add_widget_to_dashboard.assert_not_called()

    async def test_error(self, mock_client, config):
        mock_client.dashboards.add_widget_to_dashboard.return_value = ApiError("dashboard not found")
        handler = AddWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="dashboard not found"):
            await handler.handle(
                {"dashboard_guid": "YmFkR3VpZFRlc3Q=", "widget_title": "W", "widget_query": "SELECT 1"}, "1234567"
            )


class TestGetWidgetsHandler:
    async def test_success_with_widgets(self, mock_client, config):
        mock_client.dashboards.get_dashboard_widgets.return_value = {
            "dashboard_name": "My Dash",
            "total_pages": 1,
            "pages": [
                {
                    "page_name": "Page 1",
                    "page_guid": "pg1",
                    "widgets": [
                        {
                            "title": "Error Count",
                            "widget_id": "w1",
                            "visualization_type": "viz.billboard",
                            "configuration": {"billboard": {"nrqlQueries": [{"query": "SELECT count(*) FROM Error"}]}},
                        }
                    ],
                }
            ],
        }
        handler = GetWidgetsHandler(mock_client, config)
        result = await handler.handle({"dashboard_guid": "MTIzNDU2Nzg5MA=="}, "1234567")

        text = result[0].text
        assert "Error Count" in text
        assert "w1" in text
        assert "SELECT count(*) FROM Error" in text

    async def test_no_widgets(self, mock_client, config):
        mock_client.dashboards.get_dashboard_widgets.return_value = {
            "dashboard_name": "Empty Dash",
            "total_pages": 1,
            "pages": [{"page_name": "Page 1", "page_guid": "pg1", "widgets": []}],
        }
        handler = GetWidgetsHandler(mock_client, config)
        result = await handler.handle({"dashboard_guid": "MTIzNDU2Nzg5MA=="}, "1234567")

        assert "No widgets found" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.dashboards.get_dashboard_widgets.return_value = ApiError("not found")
        handler = GetWidgetsHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"dashboard_guid": "YmFkR3VpZFRlc3Q="}, "1234567")


class TestUpdateWidgetHandler:
    CURRENT = {
        "id": "w1",
        "title": "Current Title",
        "layout": {"column": 5, "row": 4, "width": 4, "height": 3},
        "visualization": {"id": "viz.billboard"},
        "rawConfiguration": {
            "thresholds": [{"alertSeverity": "CRITICAL", "value": 500}],
            "nrqlQueries": [{"accountIds": [1234567], "query": "SELECT 1"}],
        },
    }

    async def _send(self, mock_client, config, **arguments):
        mock_client.dashboards.get_widget.return_value = dict(self.CURRENT)
        mock_client.dashboards.update_widget.return_value = {"success": True}
        result = await UpdateWidgetHandler(mock_client, config).handle(
            {"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1", **arguments}, "1234567"
        )
        return result, mock_client.dashboards.update_widget.call_args.args[2]

    async def test_title_only_keeps_everything_else(self, mock_client, config):
        result, sent = await self._send(mock_client, config, widget_title="Updated Title")

        assert "updated successfully" in result[0].text
        assert sent == {
            "title": "Updated Title",
            "layout": self.CURRENT["layout"],
            "visualization": {"id": "viz.billboard"},
            "rawConfiguration": self.CURRENT["rawConfiguration"],
        }

    async def test_raw_configuration_only_keeps_title_layout_and_visualization(self, mock_client, config):
        raw = {"nrqlQueries": [{"accountIds": [1234567], "query": "SELECT count(*) FROM Transaction"}]}
        _, sent = await self._send(mock_client, config, raw_configuration=raw)

        assert sent["rawConfiguration"] == raw
        assert sent["title"] == "Current Title"
        assert sent["layout"] == self.CURRENT["layout"]
        assert sent["visualization"] == {"id": "viz.billboard"}

    async def test_query_only_swaps_queries_and_keeps_display_settings(self, mock_client, config):
        _, sent = await self._send(mock_client, config, widget_query="SELECT count(*) FROM Transaction")

        assert sent["visualization"] == {"id": "viz.billboard"}
        assert sent["rawConfiguration"]["thresholds"] == self.CURRENT["rawConfiguration"]["thresholds"]
        assert sent["rawConfiguration"]["nrqlQueries"][0]["query"] == "SELECT count(*) FROM Transaction"

    async def test_explicit_type_and_layout_win(self, mock_client, config):
        layout = {"column": 1, "row": 1, "width": 12, "height": 3}
        _, sent = await self._send(mock_client, config, widget_type="area", layout=layout)

        assert sent["visualization"] == {"id": "viz.area"}
        assert sent["layout"] == layout

    async def test_text_merges_into_raw_configuration(self, mock_client, config):
        _, sent = await self._send(mock_client, config, text="new body")
        assert sent["rawConfiguration"]["text"] == "new body"
        assert sent["rawConfiguration"]["thresholds"] == self.CURRENT["rawConfiguration"]["thresholds"]

    async def test_existing_links_kept_unless_replaced(self, mock_client, config):
        mock_client.dashboards.get_widget.return_value = {
            **self.CURRENT,
            "link": {"url": "https://old.example"},
            "linkedEntities": [{"guid": "ZGFzaDE="}],
        }
        mock_client.dashboards.update_widget.return_value = {"success": True}
        handler = UpdateWidgetHandler(mock_client, config)

        await handler.handle({"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1", "widget_title": "T"}, "1234567")
        kept = mock_client.dashboards.update_widget.call_args.args[2]
        assert kept["link"] == {"url": "https://old.example"}
        assert kept["linkedEntityGuids"] == ["ZGFzaDE="]

        await handler.handle(
            {
                "page_guid": "cGFnZUd1aWQxMjM=",
                "widget_id": "w1",
                "link_url": "https://new.example",
                "linked_entity_guids": [],
            },
            "1234567",
        )
        replaced = mock_client.dashboards.update_widget.call_args.args[2]
        assert replaced["link"] == {"url": "https://new.example"}
        assert replaced["linkedEntityGuids"] == []

    async def test_lookup_error_propagated(self, mock_client, config):
        mock_client.dashboards.get_widget.return_value = ApiError("Widget 'w1' not found")
        handler = UpdateWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1", "widget_title": "X"}, "1234567")
        mock_client.dashboards.update_widget.assert_not_called()

    async def test_error(self, mock_client, config):
        mock_client.dashboards.get_widget.return_value = dict(self.CURRENT)
        mock_client.dashboards.update_widget.return_value = ApiError("permission denied")
        handler = UpdateWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="permission denied"):
            await handler.handle({"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1"}, "1234567")


class TestDeleteWidgetHandler:
    async def test_success(self, mock_client, config):
        mock_client.dashboards.delete_widget.return_value = {"success": True}
        handler = DeleteWidgetHandler(mock_client, config)
        result = await handler.handle({"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1"}, "1234567")

        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.dashboards.delete_widget.return_value = ApiError("not found")
        handler = DeleteWidgetHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1"}, "1234567")


class TestDeleteDashboardHandler:
    async def test_success(self, mock_client, config):
        mock_client.dashboards.delete_dashboard.return_value = {"success": True, "status": "SUCCESS"}
        handler = DeleteDashboardHandler(mock_client, config)
        result = await handler.handle({"dashboard_guid": "ZGFzaEd1aWQxMjM="}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.dashboards.delete_dashboard.return_value = ApiError("not found")
        handler = DeleteDashboardHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"dashboard_guid": "YmFkR3VpZFRlc3Q="}, "1234567")


class TestUpdateDashboardHandler:
    async def test_success(self, mock_client, config):
        mock_client.dashboards.update_dashboard.return_value = {
            "success": True,
            "guid": "dashguid123456",
            "name": "New Name",
        }
        handler = UpdateDashboardHandler(mock_client, config)
        result = await handler.handle({"guid": "dashguid123456", "name": "New Name"}, "")
        assert "New Name" in result[0].text
        assert "updated successfully" in result[0].text
        mock_client.dashboards.update_dashboard.assert_called_once_with(
            "dashguid123456", name="New Name", description=None, variables=None, permissions=None
        )

    async def test_description_only(self, mock_client, config):
        mock_client.dashboards.update_dashboard.return_value = {"success": True, "name": "Existing"}
        handler = UpdateDashboardHandler(mock_client, config)
        result = await handler.handle({"guid": "dashguid123456", "description": "New desc"}, "")
        assert "updated successfully" in result[0].text
        mock_client.dashboards.update_dashboard.assert_called_once_with(
            "dashguid123456", name=None, description="New desc", variables=None, permissions=None
        )

    async def test_variables_only(self, mock_client, config):
        mock_client.dashboards.update_dashboard.return_value = {"success": True, "name": "Existing"}
        variables = [{"name": "app", "type": "ENUM", "items": [{"value": "a"}]}]
        handler = UpdateDashboardHandler(mock_client, config)
        result = await handler.handle({"guid": "dashguid123456", "variables": variables}, "")
        assert "updated successfully" in result[0].text
        mock_client.dashboards.update_dashboard.assert_called_once_with(
            "dashguid123456", name=None, description=None, variables=variables, permissions=None
        )

    async def test_permissions_only(self, mock_client, config):
        mock_client.dashboards.update_dashboard.return_value = {"success": True, "name": "Existing"}
        handler = UpdateDashboardHandler(mock_client, config)
        await handler.handle({"guid": "dashguid123456", "permissions": "PUBLIC_READ_ONLY"}, "")
        mock_client.dashboards.update_dashboard.assert_called_once_with(
            "dashguid123456", name=None, description=None, variables=None, permissions="PUBLIC_READ_ONLY"
        )

    async def test_requires_name_or_description(self, mock_client, config):
        handler = UpdateDashboardHandler(mock_client, config)
        with pytest.raises(ToolError, match="name.*description"):
            await handler.handle({"guid": "dashguid123456"}, "")
        mock_client.dashboards.update_dashboard.assert_not_called()

    async def test_error_propagated(self, mock_client, config):
        mock_client.dashboards.update_dashboard.return_value = ApiError("not found")
        handler = UpdateDashboardHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"guid": "dashguid123456", "name": "X"}, "")


class TestNewDashboardTools:
    async def test_export_returns_json(self, mock_client, config):
        mock_client.dashboards.export_dashboard.return_value = {"name": "D", "permissions": "PRIVATE", "pages": []}
        result = await ExportDashboardHandler(mock_client, config).handle({"dashboard_guid": "MTIzNDU2Nzg5MA=="}, "")
        assert json.loads(result[0].text) == {"name": "D", "permissions": "PRIVATE", "pages": []}

    async def test_replace_accepts_json_string_and_defaults_permissions(self, mock_client, config):
        mock_client.dashboards.replace_dashboard.return_value = {"success": True, "name": "D", "pages": [{"guid": "p"}]}
        dashboard = {"name": "D", "pages": [{"name": "P", "widgets": []}]}
        result = await ReplaceDashboardHandler(mock_client, config).handle(
            {"dashboard_guid": "MTIzNDU2Nzg5MA==", "dashboard": json.dumps(dashboard)}, ""
        )
        assert "replaced (1 page(s))" in result[0].text
        sent = mock_client.dashboards.replace_dashboard.call_args.args[1]
        assert sent == {**dashboard, "permissions": "PUBLIC_READ_WRITE"}

    async def test_replace_rejects_incomplete_input(self, mock_client, config):
        with pytest.raises(ToolError, match="name"):
            await ReplaceDashboardHandler(mock_client, config).handle(
                {"dashboard_guid": "MTIzNDU2Nzg5MA==", "dashboard": {"pages": []}}, ""
            )
        mock_client.dashboards.replace_dashboard.assert_not_called()

    async def test_add_page_reports_guid(self, mock_client, config):
        mock_client.dashboards.add_dashboard_page.return_value = {
            "success": True,
            "page_guid": "cGcy",
            "page_name": "Load",
        }
        result = await AddDashboardPageHandler(mock_client, config).handle(
            {"dashboard_guid": "MTIzNDU2Nzg5MA==", "name": "Load"}, ""
        )
        assert "cGcy" in result[0].text
        mock_client.dashboards.add_dashboard_page.assert_called_once_with("MTIzNDU2Nzg5MA==", "Load", None)

    async def test_snapshot_warns_it_is_public(self, mock_client, config):
        mock_client.dashboards.create_dashboard_snapshot_url.return_value = {
            "success": True,
            "url": "https://x",
            "format": "PDF",
        }
        result = await CreateDashboardSnapshotHandler(mock_client, config).handle(
            {"page_guid": "cGFnZUd1aWQxMjM=", "format": "PDF", "variables": {"env": ["prod"]}}, ""
        )
        assert "https://x" in result[0].text and "without a New Relic login" in result[0].text
        mock_client.dashboards.create_dashboard_snapshot_url.assert_called_once_with(
            "cGFnZUd1aWQxMjM=", image_format="PDF", variables={"env": ["prod"]}
        )

    async def test_undelete(self, mock_client, config):
        mock_client.dashboards.undelete_dashboard.return_value = {"success": True}
        result = await UndeleteDashboardHandler(mock_client, config).handle({"dashboard_guid": "MTIzNDU2Nzg5MA=="}, "")
        assert "restored" in result[0].text
