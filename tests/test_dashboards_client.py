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

    async def test_rename_preserves_variables(self):
        client = _make_client()
        entity = _dashboard_entity()
        entity["variables"] = [
            {
                "name": "app",
                "title": "Environment",
                "type": "ENUM",
                "isMultiSelection": False,
                "replacementStrategy": "STRING",
                "defaultValues": [{"value": {"string": "prod"}}],
                "items": [{"title": "prod", "value": "prod"}, {"title": None, "value": "stage"}],
                "nrqlQuery": None,
                "options": {
                    "excluded": False,
                    "hiddenOnVariablesBar": None,
                    "ignoreTimeRange": None,
                    "showApplyAction": None,
                },
            }
        ]
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": entity}}},
                {"data": {"dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "X"}, "errors": None}}},
            ]
        )

        result = await client.update_dashboard("dash-guid", name="X")

        assert result["success"] is True
        fetch_query = client._base.execute_graphql.call_args_list[0].args[0]
        assert "variables" in fetch_query
        sent = client._base.execute_graphql.call_args.args[1]["dashboard"]["variables"]
        assert sent == [
            {
                "name": "app",
                "title": "Environment",
                "type": "ENUM",
                "isMultiSelection": False,
                "replacementStrategy": "STRING",
                "defaultValues": [{"value": {"string": "prod"}}],
                "items": [{"title": "prod", "value": "prod"}, {"value": "stage"}],
                "options": {"excluded": False},
            }
        ]

    async def test_variables_replace_existing(self):
        client = _make_client()
        entity = _dashboard_entity()
        entity["variables"] = [{"name": "old", "type": "STRING"}]
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": entity}}},
                {
                    "data": {
                        "dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "Old Name"}, "errors": None}
                    }
                },
            ]
        )
        new_variables = [{"name": "app", "type": "ENUM", "items": [{"value": "prod"}]}]

        result = await client.update_dashboard("dash-guid", variables=new_variables)

        assert result["success"] is True
        dashboard = client._base.execute_graphql.call_args.args[1]["dashboard"]
        assert dashboard["variables"] == new_variables
        assert dashboard["name"] == "Old Name"

    async def test_empty_variables_removes_them(self):
        client = _make_client()
        entity = _dashboard_entity()
        entity["variables"] = [{"name": "old", "type": "STRING"}]
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": entity}}},
                {
                    "data": {
                        "dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "Old Name"}, "errors": None}
                    }
                },
            ]
        )

        await client.update_dashboard("dash-guid", variables=[])

        assert "variables" not in client._base.execute_graphql.call_args.args[1]["dashboard"]

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


class TestGetWidget:
    async def test_finds_widget_on_page(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "actor": {
                    "entity": {
                        "pages": [
                            {"guid": "other", "widgets": [{"id": "w1", "visualization": {"id": "viz.line"}}]},
                            {
                                "guid": "pg1",
                                "widgets": [{"id": 101, "title": "T", "visualization": {"id": "viz.billboard"}}],
                            },
                        ]
                    }
                }
            }
        }
        widget = await client.get_widget("pg1", "101")
        assert widget["title"] == "T"
        assert widget["visualization"] == {"id": "viz.billboard"}

    async def test_missing_widget(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"actor": {"entity": {"pages": [{"guid": "pg1", "widgets": []}]}}}
        }
        result = await client.get_widget("pg1", "w9")
        assert isinstance(result, ApiError)
        assert "not found" in result.message


class TestExportDashboard:
    async def test_converts_widgets_to_input_shape(self):
        client = _make_client()
        entity = _dashboard_entity()
        entity["pages"][0]["widgets"][0]["link"] = {"url": "https://example.com"}
        entity["pages"][0]["widgets"][0]["linkedEntities"] = [{"guid": "ZGFzaDE="}]
        entity["variables"] = [{"name": "env", "type": "ENUM", "title": None}]
        client._base.execute_graphql.return_value = {"data": {"actor": {"entity": entity}}}

        exported = await client.export_dashboard("dash-guid")

        assert exported["name"] == "Old Name"
        assert exported["permissions"] == "PRIVATE"
        assert exported["variables"] == [{"name": "env", "type": "ENUM"}]
        widget = exported["pages"][0]["widgets"][0]
        assert widget["link"] == {"url": "https://example.com"}
        assert widget["linkedEntityGuids"] == ["ZGFzaDE="]
        assert "linkedEntities" not in widget

    async def test_update_keeps_widget_links(self):
        client = _make_client()
        entity = _dashboard_entity()
        entity["pages"][0]["widgets"][0]["link"] = {"url": "https://example.com"}
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": entity}}},
                {"data": {"dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "X"}, "errors": None}}},
                {"data": {"actor": {"entity": {"permissions": "PUBLIC_READ_ONLY"}}}},
            ]
        )
        await client.update_dashboard("dash-guid", permissions="PUBLIC_READ_ONLY")
        sent = client._base.execute_graphql.call_args_list[1].args[1]["dashboard"]
        assert sent["permissions"] == "PUBLIC_READ_ONLY"
        assert sent["pages"][0]["widgets"][0]["link"] == {"url": "https://example.com"}


class TestAddDashboardPage:
    async def test_returns_new_page_guid(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {
                    "data": {
                        "dashboardUpdate": {
                            "entityResult": {
                                "guid": "dash-guid",
                                "name": "Old Name",
                                "pages": [{"guid": "pg1"}, {"guid": "pg2"}],
                            },
                            "errors": None,
                        }
                    }
                },
            ]
        )

        result = await client.add_dashboard_page("dash-guid", "Load test", "k6 runs")

        assert result == {"success": True, "page_guid": "pg2", "page_name": "Load test"}
        pages = client._base.execute_graphql.call_args.args[1]["dashboard"]["pages"]
        assert pages[-1] == {"name": "Load test", "widgets": [], "description": "k6 runs"}
        assert pages[0]["guid"] == "pg1"


class TestAddWidgetPageTarget:
    async def test_unknown_page_rejected(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"actor": {"entity": {"pages": [{"guid": "pg1", "name": "P1"}]}}}
        }
        result = await client.add_widget_to_dashboard("dash-guid", {"title": "W"}, page_guid="nope")
        assert isinstance(result, ApiError)
        assert "nope" in result.message

    async def test_named_page_used(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {
                    "data": {
                        "actor": {"entity": {"pages": [{"guid": "pg1", "name": "P1"}, {"guid": "pg2", "name": "P2"}]}}
                    }
                },
                {"data": {"dashboardAddWidgetsToPage": {"errors": None}}},
            ]
        )
        result = await client.add_widget_to_dashboard("dash-guid", {"title": "W"}, page_guid="pg2")
        assert result["page_guid"] == "pg2" and result["page_name"] == "P2"
        assert client._base.execute_graphql.call_args.args[1]["guid"] == "pg2"


class TestSnapshotAndUndelete:
    async def test_snapshot_passes_format_and_variables(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"dashboardCreateSnapshotUrl": "https://snap"}}
        result = await client.create_dashboard_snapshot_url("pg1", "PDF", {"env": ["prod"]})
        assert result == {"success": True, "url": "https://snap", "format": "PDF"}
        params = client._base.execute_graphql.call_args.args[1]["params"]
        assert params == {"format": "PDF", "variables": [{"name": "env", "values": ["prod"]}]}

    async def test_snapshot_graphql_error(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"dashboardCreateSnapshotUrl": None},
            "errors": [{"message": "Unsupported operation on dashboard"}],
        }
        result = await client.create_dashboard_snapshot_url("dash-guid")
        assert isinstance(result, ApiError)
        assert "Unsupported" in result.message

    async def test_undelete(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"dashboardUndelete": {"errors": None}}}
        assert (await client.undelete_dashboard("dash-guid"))["success"] is True


class TestPageIndexLag:
    async def test_get_widget_waits_for_new_page(self):
        client = _make_client()
        client.page_index_retry_seconds = 0
        found = {"data": {"actor": {"entity": {"pages": [{"guid": "pg2", "widgets": [{"id": "w1", "title": "T"}]}]}}}}
        client._base.execute_graphql = AsyncMock(side_effect=[{"data": {"actor": {"entity": None}}}, found])

        widget = await client.get_widget("pg2", "w1")

        assert widget["title"] == "T"
        assert client._base.execute_graphql.call_count == 2

    async def test_gives_up_after_retries(self):
        client = _make_client()
        client.page_index_retry_seconds = 0
        client._base.execute_graphql.return_value = {"data": {"actor": {"entity": None}}}

        result = await client.get_widget("missing", "w1")

        assert isinstance(result, ApiError)
        assert client._base.execute_graphql.call_count == client.page_index_retries + 1


class TestPermissionsReadLag:
    async def test_waits_until_reads_show_new_permissions(self):
        client = _make_client()
        client.page_index_retry_seconds = 0
        stale = {"data": {"actor": {"entity": {"permissions": "PRIVATE"}}}}
        fresh = {"data": {"actor": {"entity": {"permissions": "PUBLIC_READ_ONLY"}}}}
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {
                    "data": {
                        "dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "Old Name"}, "errors": None}
                    }
                },
                stale,
                fresh,
            ]
        )

        result = await client.update_dashboard("dash-guid", permissions="PUBLIC_READ_ONLY")

        assert result["success"] is True
        assert client._base.execute_graphql.call_count == 4

    async def test_no_wait_without_permission_change(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(
            side_effect=[
                {"data": {"actor": {"entity": _dashboard_entity()}}},
                {"data": {"dashboardUpdate": {"entityResult": {"guid": "dash-guid", "name": "X"}, "errors": None}}},
            ]
        )
        await client.update_dashboard("dash-guid", name="X")
        assert client._base.execute_graphql.call_count == 2
