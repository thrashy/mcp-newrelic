"""Tests for dashboard tool handler strategies."""

import pytest

from newrelic_mcp.handlers.strategies.dashboard import (
    AddWidgetHandler,
    CreateDashboardHandler,
    DeleteDashboardHandler,
    DeleteWidgetHandler,
    GetDashboardsHandler,
    GetWidgetsHandler,
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
        mock_client.dashboards.add_widget_to_dashboard.return_value = {"success": True}
        handler = AddWidgetHandler(mock_client, config)
        result = await handler.handle(
            {
                "dashboard_guid": "MTIzNDU2Nzg5MA==",
                "widget_title": "Custom",
                "widget_query": "SELECT 1",
                "raw_configuration": {"facet": {"showOtherSeries": True}},
            },
            "1234567",
        )

        assert "rawConfiguration" in result[0].text

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
    async def test_success(self, mock_client, config):
        mock_client.dashboards.update_widget.return_value = {"success": True}
        handler = UpdateWidgetHandler(mock_client, config)
        result = await handler.handle(
            {"page_guid": "cGFnZUd1aWQxMjM=", "widget_id": "w1", "widget_title": "Updated Title"}, "1234567"
        )

        assert "updated successfully" in result[0].text

    async def test_error(self, mock_client, config):
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
