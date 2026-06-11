"""Tests for GraphQL utility functions."""

from newrelic_mcp.utils.graphql_helpers import (
    escape_nrql_string,
    extract_nested_data,
    extract_nrql_results,
)


class TestExtractNestedData:
    def test_extracts_nested_path(self):
        data = {"a": {"b": {"c": "value"}}}
        assert extract_nested_data(data, ["a", "b", "c"]) == "value"

    def test_returns_empty_dict_on_missing_key(self):
        data = {"a": {}}
        assert extract_nested_data(data, ["a", "b", "c"]) == {}

    def test_empty_path_returns_input(self):
        data = {"key": "val"}
        assert extract_nested_data(data, []) == data


class TestExtractNrqlResults:
    def _make_response(self, rows):
        return {"data": {"actor": {"account": {"nrql": {"results": rows}}}}}

    def test_extracts_rows(self):
        rows = [{"count": 5}, {"count": 10}]
        assert extract_nrql_results(self._make_response(rows)) == rows

    def test_returns_empty_list_on_missing_data(self):
        assert extract_nrql_results({}) == []

    def test_returns_empty_list_when_results_not_a_list(self):
        result = {"data": {"actor": {"account": {"nrql": {"results": None}}}}}
        assert extract_nrql_results(result) == []


class TestEscapeNrqlString:
    def test_escapes_single_quotes(self):
        assert escape_nrql_string("O'Brien") == "O\\'Brien"

    def test_escapes_backslashes(self):
        assert escape_nrql_string("path\\file") == "path\\\\file"

    def test_plain_string_unchanged(self):
        assert escape_nrql_string("MyApp") == "MyApp"

    def test_empty_string(self):
        assert escape_nrql_string("") == ""
