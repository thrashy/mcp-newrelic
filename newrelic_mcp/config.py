"""
Configuration management for New Relic MCP Server.

Handles loading configuration from environment variables, JSON files, and command line arguments
with proper priority hierarchy.
"""

import argparse
import json
import os
from pathlib import Path


def _parse_timeout(value: int | str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid New Relic timeout {value!r} — expected an integer number of seconds") from e


def _parse_bool(value: object) -> bool | None:
    """Parse an optional boolean from env/file/CLI. None means unset (for merge)."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _parse_tool_list(value: object) -> set[str] | None:
    """Parse an optional comma-separated string or list into a set of tool names."""
    if value is None:
        return None
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        raise ValueError(f"Invalid tool list value: {value!r}")
    parsed = {item.strip() for item in items if item.strip()}
    return parsed or None


class NewRelicConfig:
    """Configuration for New Relic MCP Server"""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.account_id: str | None = None
        self.region: str | None = None
        self.timeout: int | None = None
        self.enable_writes: bool | None = None
        self.enable_destructive: bool | None = None
        self.allow_account_override: bool | None = None
        self.allowed_tools: set[str] | None = None
        self.disabled_tools: set[str] | None = None

    @property
    def effective_region(self) -> str:
        """Resolved region, defaulting to US if not set"""
        region = (self.region or "US").upper()
        if region not in ("US", "EU"):
            raise ValueError(f"Invalid New Relic region {self.region!r} — expected US or EU")
        return region

    @property
    def effective_timeout(self) -> int:
        """Resolved timeout, defaulting to 30s if not set"""
        return self.timeout if self.timeout is not None else 30

    @property
    def writes_enabled(self) -> bool:
        """Whether MCP tools may perform New Relic write operations."""
        return bool(self.enable_writes)

    @property
    def destructive_enabled(self) -> bool:
        """Whether destructive write tools (update/delete/replace/suppress) may run."""
        return bool(self.enable_destructive)

    @property
    def account_override_enabled(self) -> bool:
        """Whether a tool call may target an account other than the configured one."""
        return bool(self.allow_account_override)

    @property
    def effective_allowed_tools(self) -> set[str] | None:
        """Optional allowlist of MCP tool names; None means all tools are allowed."""
        return self.allowed_tools

    @property
    def effective_disabled_tools(self) -> set[str]:
        """Optional denylist of MCP tool names."""
        return self.disabled_tools or set()

    @classmethod
    def from_file(cls, config_path: str) -> "NewRelicConfig":
        """Load configuration from JSON file"""
        config = cls()
        if not Path(config_path).exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
            config.api_key = data.get("api_key")
            config.account_id = data.get("account_id")
            config.region = data.get("region")
            config.timeout = _parse_timeout(data.get("timeout"))
            config.enable_writes = _parse_bool(data.get("enable_writes"))
            config.enable_destructive = _parse_bool(data.get("enable_destructive"))
            config.allow_account_override = _parse_bool(data.get("allow_account_override"))
            config.allowed_tools = _parse_tool_list(data.get("allowed_tools"))
            config.disabled_tools = _parse_tool_list(data.get("disabled_tools"))
        return config

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "NewRelicConfig":
        """Load configuration from command line arguments.

        Only sets a value if the argument was explicitly provided (not None).
        """
        config = cls()
        config.api_key = args.api_key
        config.account_id = args.account_id
        config.region = args.region  # None when not provided (argparse default=None)
        config.timeout = args.timeout  # None when not provided (argparse default=None)
        config.enable_writes = getattr(args, "enable_writes", None)
        config.enable_destructive = getattr(args, "enable_destructive", None)
        config.allow_account_override = getattr(args, "allow_account_override", None)
        config.allowed_tools = _parse_tool_list(getattr(args, "allowed_tools", None))
        config.disabled_tools = _parse_tool_list(getattr(args, "disabled_tools", None))
        return config

    @classmethod
    def from_env(cls) -> "NewRelicConfig":
        """Load configuration from environment variables"""
        config = cls()
        config.api_key = os.getenv("NEW_RELIC_API_KEY")
        config.account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
        config.region = os.getenv("NEW_RELIC_REGION")
        config.timeout = _parse_timeout(os.getenv("NEW_RELIC_TIMEOUT"))
        config.enable_writes = _parse_bool(os.getenv("NEW_RELIC_MCP_ENABLE_WRITES"))
        config.enable_destructive = _parse_bool(os.getenv("NEW_RELIC_MCP_ENABLE_DESTRUCTIVE"))
        config.allow_account_override = _parse_bool(os.getenv("NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE"))
        config.allowed_tools = _parse_tool_list(os.getenv("NEW_RELIC_MCP_ALLOWED_TOOLS"))
        config.disabled_tools = _parse_tool_list(os.getenv("NEW_RELIC_MCP_DISABLED_TOOLS"))
        return config

    def merge_with(self, other: "NewRelicConfig") -> "NewRelicConfig":
        """Merge with another config, preferring non-None values from other."""
        merged = NewRelicConfig()
        merged.api_key = other.api_key or self.api_key
        merged.account_id = other.account_id or self.account_id
        merged.region = other.region or self.region
        merged.timeout = other.timeout if other.timeout is not None else self.timeout
        merged.enable_writes = other.enable_writes if other.enable_writes is not None else self.enable_writes
        merged.enable_destructive = (
            other.enable_destructive if other.enable_destructive is not None else self.enable_destructive
        )
        merged.allow_account_override = (
            other.allow_account_override if other.allow_account_override is not None else self.allow_account_override
        )
        merged.allowed_tools = other.allowed_tools if other.allowed_tools is not None else self.allowed_tools
        merged.disabled_tools = other.disabled_tools if other.disabled_tools is not None else self.disabled_tools
        return merged

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return bool(self.api_key and self.account_id)

    def __repr__(self) -> str:
        return (
            f"NewRelicConfig(region={self.effective_region}, "
            f"account_id={self.account_id}, timeout={self.effective_timeout})"
        )
