#!/usr/bin/env python3
"""
New Relic MCP Server

A Model Context Protocol server that provides tools and resources for interacting with New Relic.
Supports querying applications, metrics, incidents, dashboards, and managing alerts.
"""

import argparse
import asyncio
import logging

from dotenv import load_dotenv

from newrelic_mcp.config import NewRelicConfig
from newrelic_mcp.server import NewRelicMCPServer

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("newrelic-mcp")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="New Relic MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Configuration Priority (highest to lowest):
1. Command line arguments
2. Configuration file (--config)
3. Environment variables

Environment Variables:
  NEW_RELIC_API_KEY     New Relic User API key
  NEW_RELIC_ACCOUNT_ID  New Relic account ID
  NEW_RELIC_REGION      New Relic region (US or EU, default: US)
  NEW_RELIC_TIMEOUT     HTTP timeout in seconds (default: 30)
  NEW_RELIC_MCP_ENABLE_WRITES       Enable write tools (default: false)
  NEW_RELIC_MCP_ENABLE_DESTRUCTIVE  Enable destructive tools (default: false)
  NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE  Allow per-tool account_id override (default: false)

Example Usage:
  # With command line arguments
  python server.py --api-key YOUR_KEY --account-id 123456

  # With config file
  python server.py --config newrelic-config.json

  # With environment variables
  export NEW_RELIC_API_KEY="your_key"
  export NEW_RELIC_ACCOUNT_ID="123456"
  python server.py
        """,
    )

    parser.add_argument("--api-key", help="New Relic User API key")
    parser.add_argument("--account-id", help="New Relic account ID")
    # Default None so unspecified args don't override env/file config during merge
    parser.add_argument("--region", choices=["US", "EU"], default=None, help="New Relic region (default: US)")
    parser.add_argument("--timeout", type=int, default=None, help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument(
        "--enable-writes",
        action="store_true",
        default=None,
        help="Allow MCP tools that create or modify New Relic resources (default: disabled)",
    )
    parser.add_argument(
        "--enable-destructive",
        action="store_true",
        default=None,
        help="Allow destructive tools such as delete, replace, muting, and disabling alerts (default: disabled)",
    )
    parser.add_argument(
        "--allow-account-override",
        action="store_true",
        default=None,
        help="Allow tool arguments to override the configured New Relic account ID (default: disabled)",
    )
    parser.add_argument(
        "--log-payloads",
        action="store_true",
        default=None,
        help="Allow DEBUG logs to include NRQL queries and API results (default: disabled)",
    )
    parser.add_argument(
        "--allowed-tools",
        help="Comma-separated MCP tool allowlist. If set, all other tools are blocked.",
    )
    parser.add_argument("--disabled-tools", help="Comma-separated MCP tool denylist")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def load_config(args: argparse.Namespace) -> NewRelicConfig:
    """Load configuration from various sources"""
    # Start with environment variables as base
    config = NewRelicConfig.from_env()

    # Override with config file if provided
    if args.config:
        file_config = NewRelicConfig.from_file(args.config)
        config = config.merge_with(file_config)
        logger.info(f"Loaded configuration from file: {args.config}")

    # Override with command line arguments (highest priority)
    args_config = NewRelicConfig.from_args(args)
    config = config.merge_with(args_config)

    # Validate configuration
    if not config.is_valid():
        logger.error("Invalid configuration: Missing API key or account ID")
        logger.error("Provide credentials via --api-key/--account-id, config file, or environment variables")
        raise ValueError("Invalid New Relic configuration")

    logger.info(
        "Configuration loaded - Region: %s, Account: %s, Writes: %s, Destructive: %s",
        config.effective_region,
        config.account_id,
        config.writes_enabled,
        config.destructive_enabled,
    )
    return config


async def main():
    """Main entry point"""
    try:
        args = parse_args()

        # Configure logging
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Load configuration
        config = load_config(args)

        # Create and run server
        server = NewRelicMCPServer(config)
        await server.run()

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
