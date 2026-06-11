"""
Command-line entry point for the New Relic MCP Server.

Parses arguments, loads configuration (CLI > config file > environment), and runs the stdio server.
"""

import argparse
import asyncio
import logging

from dotenv import load_dotenv

from .config import NewRelicConfig
from .server import NewRelicMCPServer

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

Example Usage:
  # With command line arguments
  newrelic-mcp --api-key YOUR_KEY --account-id 123456

  # With config file
  newrelic-mcp --config newrelic-config.json

  # With environment variables
  export NEW_RELIC_API_KEY="your_key"
  export NEW_RELIC_ACCOUNT_ID="123456"
  newrelic-mcp
        """,
    )

    parser.add_argument("--api-key", help="New Relic User API key")
    parser.add_argument("--account-id", help="New Relic account ID")
    # Default None so unspecified args don't override env/file config during merge
    parser.add_argument("--region", choices=["US", "EU"], default=None, help="New Relic region (default: US)")
    parser.add_argument("--timeout", type=int, default=None, help="HTTP timeout in seconds (default: 30)")
    parser.add_argument("--config", help="Path to JSON configuration file")
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
        logger.info("Loaded configuration from file: %s", args.config)

    # Override with command line arguments (highest priority)
    args_config = NewRelicConfig.from_args(args)
    config = config.merge_with(args_config)

    # Validate configuration
    if not config.is_valid():
        logger.error("Invalid configuration: Missing API key or account ID")
        logger.error("Provide credentials via --api-key/--account-id, config file, or environment variables")
        raise ValueError("Invalid New Relic configuration")

    logger.info("Configuration loaded - Region: %s, Account: %s", config.effective_region, config.account_id)
    return config


async def run() -> None:
    """Async entry point"""
    try:
        args = parse_args()

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        config = load_config(args)

        server = NewRelicMCPServer(config)
        await server.run()

    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error("Server error: %s", e)
        raise


def main() -> None:
    """Synchronous console-script entry point"""
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
