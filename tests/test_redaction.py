"""Tests for secret redaction in error text."""

from newrelic_mcp.utils.redaction import redact_secrets


def test_redacts_nr_api_key():
    assert redact_secrets("failed with key NRAK-abcdef0123456789") == "failed with key NRAK-[REDACTED]"


def test_redacts_license_and_insert_key_families():
    assert "NRII-[REDACTED]" in redact_secrets("token NRII-0123456789abcdef")
    assert "NRAL-[REDACTED]" in redact_secrets("token NRAL-0123456789abcdef")


def test_redacts_bearer_token():
    assert redact_secrets("Authorization: Bearer abcdef0123456789") == "Authorization: Bearer [REDACTED]"


def test_redacts_env_assignment():
    assert redact_secrets("NEW_RELIC_API_KEY=NRAK-secretvalue123").startswith("NEW_RELIC_API_KEY=[REDACTED]")


def test_leaves_ordinary_text_untouched():
    assert redact_secrets("GraphQL query failed: invalid NRQL syntax") == "GraphQL query failed: invalid NRQL syntax"
