"""Tests for DashboardsClient."""

from unittest.mock import AsyncMock, MagicMock

from newrelic_mcp.client.base_client import BaseNewRelicClient
from newrelic_mcp.client.dashboards_client import DashboardsClient
from newrelic_mcp.types import ApiError, PaginatedResult


def _make_client() -> DashboardsClient:
    base = MagicMock()
    base.execute_graphql = AsyncMock()
    base.paginate_graphql = AsyncMock()
    base._extract_mutation_result = BaseNewRelicClient._extract_mutation_result.__get__(base)
    return DashboardsClient(base)


class TestGetDashboards:
    async def test_returns_entities(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"name": "My Dashboard", "guid": "abc123"}], total_count=1
        )
        result = await client.get_dashboards("1234567")
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.items[0]["name"] == "My Dashboard"

    async def test_empty_results(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        result = await client.get_dashboards("1234567")
        assert isinstance(result, PaginatedResult)
        assert result.items == []

    async def test_with_search_filter(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        result = await client.get_dashboards("1234567", search="test")
        assert isinstance(result, PaginatedResult)
        assert result.items == []

    async def test_exception(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("timeout"))
        result = await client.get_dashboards("1234567")
        assert isinstance(result, ApiError)


class TestCreateDashboard:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "dashboardCreate": {
                    "entityResult": {"guid": "dash-guid", "name": "New Dashboard"},
                    "errors": None,
                }
            }
        }
        result = await client.create_dashboard("1234567", "New Dashboard")
        assert result["guid"] == "dash-guid"

    async def test_creation_errors(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "dashboardCreate": {
                    "entityResult": None,
                    "errors": [{"description": "bad input", "type": "INVALID"}],
                }
            }
        }
        result = await client.create_dashboard("1234567", "Bad")
        assert isinstance(result, ApiError)

    async def test_exception(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.create_dashboard("1234567", "Test")
        assert isinstance(result, ApiError)


class TestAddWidgetToDashboard:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": {"pages": [{"guid": "page-guid", "name": "Page 1"}]}}}},
                {"data": {"dashboardAddWidgetsToPage": {"errors": None}}},
            ]
        )
        result = await client.add_widget_to_dashboard("dash-guid", {"title": "Widget"})
        assert result["success"] is True
        assert result["page_guid"] == "page-guid"

    async def test_no_pages(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"actor": {"entity": {"pages": []}}}}
        result = await client.add_widget_to_dashboard("dash-guid", {"title": "Widget"})
        assert isinstance(result, ApiError)


class TestGetDashboardWidgets:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "actor": {
                    "entity": {
                        "name": "Dashboard",
                        "pages": [
                            {
                                "guid": "pg1",
                                "name": "Page 1",
                                "widgets": [
                                    {
                                        "id": "w1",
                                        "title": "Widget 1",
                                        "visualization": {"id": "viz.line"},
                                        "configuration": {},
                                        "rawConfiguration": None,
                                    }
                                ],
                            }
                        ],
                    }
                }
            }
        }
        result = await client.get_dashboard_widgets("dash-guid")
        assert result["dashboard_name"] == "Dashboard"
        assert len(result["pages"]) == 1
        assert len(result["pages"][0]["widgets"]) == 1

    async def test_not_found(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"actor": {"entity": None}}}
        result = await client.get_dashboard_widgets("bad-guid")
        assert isinstance(result, ApiError)


class TestUpdateWidget:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"dashboardUpdateWidgetsInPage": {"errors": None}}}
        result = await client.update_widget("pg1", "w1", {"title": "Updated"})
        assert result["success"] is True

    async def test_errors(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"dashboardUpdateWidgetsInPage": {"errors": [{"description": "bad"}]}}
        }
        result = await client.update_widget("pg1", "w1", {})
        assert isinstance(result, ApiError)


class TestDeleteWidget:
    async def test_success(self):
        client = _make_client()
        # First call fetches the page, second call updates without the target widget
        client._base.execute_graphql.side_effect = [
            {
                "data": {
                    "actor": {
                        "entity": {
                            "pages": [
                                {
                                    "guid": "pg1",
                                    "name": "Page 1",
                                    "description": "",
                                    "widgets": [
                                        {
                                            "id": "w1",
                                            "title": "Delete Me",
                                            "layout": None,
                                            "visualization": {"id": "viz.line"},
                                            "rawConfiguration": {},
                                        },
                                        {
                                            "id": "w2",
                                            "title": "Keep Me",
                                            "layout": None,
                                            "visualization": {"id": "viz.bar"},
                                            "rawConfiguration": {},
                                        },
                                    ],
                                }
                            ]
                        }
                    }
                }
            },
            {"data": {"dashboardUpdatePage": {"errors": None}}},
        ]
        result = await client.delete_widget("pg1", "w1")
        assert result["success"] is True
        mutation, variables = client._base.execute_graphql.call_args.args[:2]
        assert "dashboardUpdatePage" in mutation
        assert variables["page"]["name"] == "Page 1"
        assert [w["id"] for w in variables["page"]["widgets"]] == ["w2"]

    async def test_widget_not_found(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "actor": {"entity": {"pages": [{"guid": "pg1", "name": "Page 1", "description": "", "widgets": []}]}}
            }
        }
        result = await client.delete_widget("pg1", "missing")
        assert isinstance(result, ApiError)
        assert "not found" in result.message


class TestDeleteDashboard:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"dashboardDelete": {"status": "SUCCESS", "errors": None}}}
        result = await client.delete_dashboard("dash-guid")
        assert result["success"] is True

    async def test_errors(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"dashboardDelete": {"status": None, "errors": [{"description": "not found"}]}}
        }
        result = await client.delete_dashboard("bad-guid")
        assert isinstance(result, ApiError)
