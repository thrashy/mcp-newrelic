"""Tests for utility modules."""

from newrelic_mcp.types import ApiError
from newrelic_mcp.utils.dashboard_formatters import (
    build_raw_nrql_queries,
    build_widget_configuration,
    extract_nrql_queries,
    format_dashboard_list,
)
from newrelic_mcp.utils.error_handling import (
    format_resource_error,
    handle_api_error,
    handle_graphql_notification_errors,
)
from newrelic_mcp.utils.graphql_helpers import escape_nrql_string
from newrelic_mcp.utils.response_formatters import format_create_response


class TestHandleApiError:
    def test_returns_api_error(self):
        result = handle_api_error("test_op", ValueError("boom"))
        assert isinstance(result, ApiError)
        assert result.message == "boom"

    def test_stringifies_exception(self):
        result = handle_api_error("op", RuntimeError("something broke"))
        assert "something broke" in result.message


class TestHandleGraphqlNotificationErrors:
    def test_no_errors_returns_none(self):
        result = handle_graphql_notification_errors({"errors": []}, "test")
        assert result is None

    def test_with_errors_returns_api_error(self):
        result = handle_graphql_notification_errors(
            {"errors": [{"__typename": "ValidationError", "description": "bad input"}]},
            "create_channel",
        )
        assert isinstance(result, ApiError)
        assert "bad input" in result.message

    def test_missing_errors_key_returns_none(self):
        result = handle_graphql_notification_errors({}, "test")
        assert result is None

    def test_fallback_to_type_field(self):
        result = handle_graphql_notification_errors(
            {"errors": [{"__typename": "Foo", "type": "INVALID_PARAMETER"}]},
            "op",
        )
        assert isinstance(result, ApiError)
        assert "INVALID_PARAMETER" in result.message


class TestFormatResourceError:
    def test_formats_error(self):
        result = format_resource_error(ApiError("no access"), "Dashboards")
        assert result == "# Dashboards\n\nError: no access"


class TestEscapeNrqlString:
    def test_escapes_quotes_backslashes_and_backticks(self):
        assert escape_nrql_string("a'b\\c`d") == "a\\'b\\\\c\\`d"


class TestFormatCreateResponse:
    def test_basic_response(self):
        result = format_create_response({"id": "abc123"})
        assert result == {"success": True, "id": "abc123"}

    def test_with_extra_fields(self):
        result = format_create_response(
            {"id": "abc", "name": "test", "enabled": True},
            name="name",
            enabled="enabled",
        )
        assert result["name"] == "test"
        assert result["enabled"] is True

    def test_nested_path(self):
        result = format_create_response(
            {"id": "abc", "nrql": {"query": "SELECT 1"}},
            query=["nrql", "query"],
        )
        assert result["query"] == "SELECT 1"


class TestFormatDashboardList:
    def test_empty_list(self):
        result = format_dashboard_list([])
        assert "No dashboards found" in result

    def test_empty_with_search(self):
        result = format_dashboard_list([], search="prod")
        assert "matching 'prod'" in result

    def test_with_dashboards(self):
        dashboards = [
            {"name": "Dash 1", "guid": "g1", "createdAt": "2026-01-01", "permalink": "https://nr.com/1"},
            {"name": "Dash 2", "guid": "g2", "createdAt": "2026-01-02"},
        ]
        result = format_dashboard_list(dashboards)
        assert "Found 2 dashboards" in result
        assert "Dash 1" in result
        assert "g1" in result
        assert "https://nr.com/1" in result

    def test_limit_display(self):
        dashboards = [{"name": f"D{i}", "guid": f"g{i}", "createdAt": "2026"} for i in range(10)]
        result = format_dashboard_list(dashboards, limit_display=3)
        assert "... and 7 more" in result

    def test_200_cap_note(self):
        dashboards = [{"name": f"D{i}", "guid": f"g{i}", "createdAt": "2026"} for i in range(200)]
        result = format_dashboard_list(dashboards)
        assert "caps results at 200" in result

    def test_guid_header(self):
        result = format_dashboard_list([{"name": "D", "guid": "abc", "createdAt": "2026"}], guid="abc")
        assert "Found dashboard with GUID abc" in result


class TestBuildRawNrqlQueries:
    def test_builds_correct_structure(self):
        result = build_raw_nrql_queries("1234567", "SELECT 1")
        assert result == [{"accountIds": [1234567], "query": "SELECT 1"}]


class TestBuildWidgetConfiguration:
    def test_line_type(self):
        result = build_widget_configuration("line", "123", "SELECT count(*) FROM Transaction")
        assert "line" in result
        assert result["line"]["nrqlQueries"][0]["accountId"] == 123
        assert result["line"]["nrqlQueries"][0]["query"] == "SELECT count(*) FROM Transaction"

    def test_billboard_type(self):
        result = build_widget_configuration("billboard", "123", "SELECT 1")
        assert "billboard" in result

    def test_unknown_type_defaults_to_line(self):
        result = build_widget_configuration("heatmap", "123", "SELECT 1")
        assert "line" in result


class TestExtractNrqlQueries:
    def test_extracts_line_queries(self):
        config = {"line": {"nrqlQueries": [{"query": "SELECT 1"}, {"query": "SELECT 2"}]}}
        result = extract_nrql_queries(config)
        assert result == ["SELECT 1", "SELECT 2"]

    def test_extracts_from_multiple_types(self):
        config = {
            "line": {"nrqlQueries": [{"query": "Q1"}]},
            "bar": {"nrqlQueries": [{"query": "Q2"}]},
        }
        result = extract_nrql_queries(config)
        assert "Q1" in result
        assert "Q2" in result

    def test_empty_config(self):
        assert extract_nrql_queries({}) == []

    def test_null_viz_type(self):
        config = {"line": None, "bar": {"nrqlQueries": [{"query": "Q"}]}}
        result = extract_nrql_queries(config)
        assert result == ["Q"]

    def test_skips_empty_query(self):
        config = {"line": {"nrqlQueries": [{"query": ""}, {"query": "SELECT 1"}]}}
        result = extract_nrql_queries(config)
        assert result == ["SELECT 1"]
