"""Tests for NewRelicConfig loading and merging."""

import argparse
import json
import os
import tempfile

from newrelic_mcp.config.newrelic_config import NewRelicConfig


class TestFromEnv:
    def test_loads_all_env_vars(self, monkeypatch):
        monkeypatch.setenv("NEW_RELIC_API_KEY", "NRAK-testkey")
        monkeypatch.setenv("NEW_RELIC_ACCOUNT_ID", "1234567")
        monkeypatch.setenv("NEW_RELIC_REGION", "EU")
        monkeypatch.setenv("NEW_RELIC_TIMEOUT", "60")
        monkeypatch.setenv("NEW_RELIC_MCP_ENABLE_WRITES", "true")
        monkeypatch.setenv("NEW_RELIC_MCP_ENABLE_DESTRUCTIVE", "false")
        monkeypatch.setenv("NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE", "yes")
        monkeypatch.setenv("NEW_RELIC_MCP_LOG_PAYLOADS", "0")
        monkeypatch.setenv("NEW_RELIC_MCP_ALLOWED_TOOLS", "query_nrql,list_alert_policies")
        monkeypatch.setenv("NEW_RELIC_MCP_DISABLED_TOOLS", "delete_dashboard")

        cfg = NewRelicConfig.from_env()

        assert cfg.api_key == "NRAK-testkey"
        assert cfg.account_id == "1234567"
        assert cfg.region == "EU"
        assert cfg.timeout == 60
        assert cfg.writes_enabled is True
        assert cfg.destructive_enabled is False
        assert cfg.account_override_enabled is True
        assert cfg.payload_logging_enabled is False
        assert cfg.allowed_tools == {"query_nrql", "list_alert_policies"}
        assert cfg.disabled_tools == {"delete_dashboard"}

    def test_missing_env_vars_produce_none(self, monkeypatch):
        for var in (
            "NEW_RELIC_API_KEY",
            "NEW_RELIC_ACCOUNT_ID",
            "NEW_RELIC_REGION",
            "NEW_RELIC_TIMEOUT",
            "NEW_RELIC_MCP_ENABLE_WRITES",
            "NEW_RELIC_MCP_ENABLE_DESTRUCTIVE",
            "NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE",
            "NEW_RELIC_MCP_LOG_PAYLOADS",
            "NEW_RELIC_MCP_ALLOWED_TOOLS",
            "NEW_RELIC_MCP_DISABLED_TOOLS",
        ):
            monkeypatch.delenv(var, raising=False)

        cfg = NewRelicConfig.from_env()

        assert cfg.api_key is None
        assert cfg.account_id is None
        assert cfg.region is None
        assert cfg.timeout is None
        assert cfg.writes_enabled is False
        assert cfg.destructive_enabled is False
        assert cfg.account_override_enabled is False

    def test_effective_region_defaults_to_us(self, monkeypatch):
        monkeypatch.delenv("NEW_RELIC_REGION", raising=False)
        cfg = NewRelicConfig.from_env()
        assert cfg.effective_region == "US"

    def test_effective_timeout_defaults_to_30(self, monkeypatch):
        monkeypatch.delenv("NEW_RELIC_TIMEOUT", raising=False)
        cfg = NewRelicConfig.from_env()
        assert cfg.effective_timeout == 30


class TestFromFile:
    def test_loads_from_valid_json(self):
        data = {
            "api_key": "NRAK-file",
            "account_id": "9999999",
            "region": "EU",
            "timeout": 45,
            "enable_writes": True,
            "enable_destructive": False,
            "allow_account_override": True,
            "allowed_tools": ["query_nrql"],
            "disabled_tools": "delete_dashboard,delete_workflow",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = NewRelicConfig.from_file(path)
        os.unlink(path)

        assert cfg.api_key == "NRAK-file"
        assert cfg.account_id == "9999999"
        assert cfg.region == "EU"
        assert cfg.timeout == 45
        assert cfg.writes_enabled is True
        assert cfg.destructive_enabled is False
        assert cfg.account_override_enabled is True
        assert cfg.allowed_tools == {"query_nrql"}
        assert cfg.disabled_tools == {"delete_dashboard", "delete_workflow"}

    def test_missing_file_returns_empty_config(self):
        cfg = NewRelicConfig.from_file("/nonexistent/path.json")
        assert cfg.api_key is None
        assert cfg.account_id is None

    def test_partial_file_leaves_missing_as_none(self):
        data = {"api_key": "NRAK-partial"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        cfg = NewRelicConfig.from_file(path)
        os.unlink(path)

        assert cfg.api_key == "NRAK-partial"
        assert cfg.account_id is None
        assert cfg.region is None


class TestFromArgs:
    def _make_args(self, **kwargs):
        defaults = {"api_key": None, "account_id": None, "region": None, "timeout": None}
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_explicit_values_are_set(self):
        args = self._make_args(api_key="NRAK-arg", account_id="1111111", region="EU", timeout=10)
        cfg = NewRelicConfig.from_args(args)
        assert cfg.api_key == "NRAK-arg"
        assert cfg.region == "EU"
        assert cfg.timeout == 10

    def test_none_args_stay_none(self):
        args = self._make_args()
        cfg = NewRelicConfig.from_args(args)
        assert cfg.region is None
        assert cfg.timeout is None


class TestMergeWith:
    def test_other_values_override_self(self):
        base = NewRelicConfig()
        base.api_key = "NRAK-base"
        base.region = "US"

        other = NewRelicConfig()
        other.api_key = "NRAK-other"
        other.region = "EU"

        merged = base.merge_with(other)
        assert merged.api_key == "NRAK-other"
        assert merged.region == "EU"

    def test_none_in_other_keeps_self_value(self):
        base = NewRelicConfig()
        base.api_key = "NRAK-base"
        base.region = "EU"
        base.timeout = 60

        other = NewRelicConfig()  # all None

        merged = base.merge_with(other)
        assert merged.api_key == "NRAK-base"
        assert merged.region == "EU"
        assert merged.timeout == 60

    def test_env_eu_not_overridden_by_unset_cli_region(self):
        """CLI --region not passed (None) must not override env EU region."""
        env_cfg = NewRelicConfig()
        env_cfg.region = "EU"

        cli_cfg = NewRelicConfig()
        cli_cfg.region = None  # not explicitly provided

        merged = env_cfg.merge_with(cli_cfg)
        assert merged.region == "EU"
        assert merged.effective_region == "EU"

    def test_explicit_cli_us_overrides_env_eu(self):
        env_cfg = NewRelicConfig()
        env_cfg.region = "EU"

        cli_cfg = NewRelicConfig()
        cli_cfg.region = "US"  # explicitly provided

        merged = env_cfg.merge_with(cli_cfg)
        assert merged.region == "US"

    def test_zero_timeout_is_preserved(self):
        """timeout=0 in other should not fall back to self (falsy but set)."""
        base = NewRelicConfig()
        base.timeout = 30

        other = NewRelicConfig()
        other.timeout = 0  # explicitly set to 0

        merged = base.merge_with(other)
        assert merged.timeout == 0

    def test_false_boolean_override_is_preserved(self):
        base = NewRelicConfig()
        base.enable_writes = True

        other = NewRelicConfig()
        other.enable_writes = False

        merged = base.merge_with(other)
        assert merged.enable_writes is False
        assert merged.writes_enabled is False


class TestIsValid:
    def test_valid_with_key_and_account(self):
        cfg = NewRelicConfig()
        cfg.api_key = "NRAK-x"
        cfg.account_id = "1234567"
        assert cfg.is_valid()

    def test_invalid_without_key(self):
        cfg = NewRelicConfig()
        cfg.account_id = "1234567"
        assert not cfg.is_valid()

    def test_invalid_without_account(self):
        cfg = NewRelicConfig()
        cfg.api_key = "NRAK-x"
        assert not cfg.is_valid()
