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


class NewRelicConfig:
    """Configuration for New Relic MCP Server"""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.account_id: str | None = None
        self.region: str | None = None
        self.timeout: int | None = None

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
        return config

    @classmethod
    def from_env(cls) -> "NewRelicConfig":
        """Load configuration from environment variables"""
        config = cls()
        config.api_key = os.getenv("NEW_RELIC_API_KEY")
        config.account_id = os.getenv("NEW_RELIC_ACCOUNT_ID")
        config.region = os.getenv("NEW_RELIC_REGION")
        config.timeout = _parse_timeout(os.getenv("NEW_RELIC_TIMEOUT"))
        return config

    def merge_with(self, other: "NewRelicConfig") -> "NewRelicConfig":
        """Merge with another config, preferring non-None values from other."""
        merged = NewRelicConfig()
        merged.api_key = other.api_key or self.api_key
        merged.account_id = other.account_id or self.account_id
        merged.region = other.region or self.region
        merged.timeout = other.timeout if other.timeout is not None else self.timeout
        return merged

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        return bool(self.api_key and self.account_id)

    def __repr__(self) -> str:
        return (
            f"NewRelicConfig(region={self.effective_region}, "
            f"account_id={self.account_id}, timeout={self.effective_timeout})"
        )
