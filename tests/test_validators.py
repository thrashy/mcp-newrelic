"""Tests for InputValidator."""

import pytest

from newrelic_mcp.validators import InputValidator, ValidationError


class TestValidateNrqlQuery:
    def test_valid_select_query(self):
        q = "SELECT count(*) FROM Transaction SINCE 1 hour ago"
        assert InputValidator.validate_nrql_query(q) == q

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="empty"):
            InputValidator.validate_nrql_query("")

    def test_rejects_non_select(self):
        with pytest.raises(ValidationError, match="SELECT"):
            InputValidator.validate_nrql_query("DROP TABLE foo")

    def test_rejects_too_long(self):
        with pytest.raises(ValidationError, match="long"):
            InputValidator.validate_nrql_query("SELECT " + "x" * 10000)

    def test_accepts_from_first_form(self):
        result = InputValidator.validate_nrql_query("FROM Transaction SELECT count(*)")
        assert result == "FROM Transaction SELECT count(*)"

    def test_rejects_non_query_text(self):
        with pytest.raises(ValidationError, match="must start with SELECT or FROM"):
            InputValidator.validate_nrql_query("SHOW EVENT TYPES")

    def test_strips_whitespace(self):
        result = InputValidator.validate_nrql_query("  SELECT 1 FROM Transaction  ")
        assert not result.startswith(" ")
        assert not result.endswith(" ")


class TestValidateGuid:
    def test_valid_guid(self):
        guid = "MTIzNDU2N3xBUE18QVBQTEJDQVRJT058MTIz"
        assert InputValidator.validate_guid(guid) == guid

    def test_rejects_empty(self):
        with pytest.raises(ValidationError, match="empty"):
            InputValidator.validate_guid("")

    def test_rejects_invalid_chars(self):
        with pytest.raises(ValidationError, match="Invalid GUID"):
            InputValidator.validate_guid("not-a-valid!guid$")

    def test_rejects_too_short(self):
        with pytest.raises(ValidationError, match="length"):
            InputValidator.validate_guid("abc")


class TestValidateTimeRange:
    def test_valid_range(self):
        assert InputValidator.validate_time_range(24) == 24

    def test_rejects_zero(self):
        with pytest.raises(ValidationError, match="at least 1"):
            InputValidator.validate_time_range(0)

    def test_rejects_over_year(self):
        with pytest.raises(ValidationError, match="1 year"):
            InputValidator.validate_time_range(9000)

    def test_rejects_non_int(self):
        with pytest.raises(ValidationError, match="integer"):
            InputValidator.validate_time_range(1.5)
