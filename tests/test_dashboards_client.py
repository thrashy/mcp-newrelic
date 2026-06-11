"""Tests for DashboardsClient."""

from unittest.mock import AsyncMock, MagicMock

from newrelic_mcp.client.base_client import BaseNewRelicClient
from newrelic_mcp.client.dashboards_client import DashboardsClient
from newrelic_mcp.types import ApiError, PaginatedResult


def _make_client() -> DashboardsClient:
    base = MagicMock()
    base.execute_graphql = AsyncMock()
    base.paginate_graphql = AsyncMock()
    base.extract_mutation_result = BaseNewRelicClient.extract_mutation_result.__get__(base)
    base.execute_mutation = BaseNewRelicClient.execute_mutation.__get__(base)
    base.entity_search_paginated = BaseNewRelicClient.entity_search_paginated.__get__(base)
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


def _dashboard_entity() -> dict:
    return {
        "name": "Old Name",
        "description": "Old description",
        "permissions": "PRIVATE",
        "pages": [
            {
                "guid": "pg1",
                "name": "Page 1",
                "description": "First page",
                "widgets": [
                    {
                        "id": "w1",
                        "title": "Widget 1",
                        "layout": {"column": 1, "row": 1, "width": 4, "height": 3},
                        "visualization": {"id": "viz.line"},
                        "rawConfiguration": {"nrqlQueries": []},
                    }
                ],
            }
        ],
    }


class TestUpdateDashboard:
    async def test_rename_preserves_pages_and_widgets(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {
                    "data": {
                        "dashboardUpdate": {
                            "entityResult": {"guid": "dash-guid", "name": "New Name", "description": "Old description"},
                            "errors": None,
                        }
                    }
                },
            ]
        )

        result = await client.update_dashboard("dash-guid", name="New Name")

        assert result["success"] is True
        assert result["name"] == "New Name"
        mutation, variables = client._base.execute_graphql.call_args.args[:2]
        assert "dashboardUpdate" in mutation
        dashboard = variables["dashboard"]
        assert dashboard["name"] == "New Name"
        assert dashboard["description"] == "Old description"
        assert dashboard["permissions"] == "PRIVATE"
        page = dashboard["pages"][0]
        assert page["guid"] == "pg1"
        assert page["name"] == "Page 1"
        widget = page["widgets"][0]
        assert widget["id"] == "w1"
        assert widget["layout"] == {"column": 1, "row": 1, "width": 4, "height": 3}
        assert widget["visualization"] == {"id": "viz.line"}

    async def test_description_only_keeps_name(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {
                    "data": {
                        "dashboardUpdate": {
                            "entityResult": {"guid": "dash-guid", "name": "Old Name", "description": "New description"},
                            "errors": None,
                        }
                    }
                },
            ]
        )

        result = await client.update_dashboard("dash-guid", description="New description")

        assert result["success"] is True
        variables = client._base.execute_graphql.call_args.args[1]
        assert variables["dashboard"]["name"] == "Old Name"
        assert variables["dashboard"]["description"] == "New description"

    async def test_dashboard_not_found(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"actor": {"entity": None}}}
        result = await client.update_dashboard("missing-guid", name="X")
        assert isinstance(result, ApiError)
        assert "not found" in result.message

    async def test_mutation_errors(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {"data": {"dashboardUpdate": {"entityResult": None, "errors": [{"description": "denied"}]}}},
            ]
        )
        result = await client.update_dashboard("dash-guid", name="X")
        assert isinstance(result, ApiError)

    async def test_fetch_exception(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("boom"))
        result = await client.update_dashboard("dash-guid", name="X")
        assert isinstance(result, ApiError)
