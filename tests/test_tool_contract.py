"""Contract test: every advertised tool has a handler strategy and vice versa."""

from unittest.mock import MagicMock

from newrelic_mcp.config.newrelic_config import NewRelicConfig
from newrelic_mcp.handlers.tool_definitions import get_all_tools
from newrelic_mcp.handlers.tool_handlers import ToolHandlers


def test_tool_definitions_match_handler_strategies():
    handlers = ToolHandlers(MagicMock(), NewRelicConfig())

    tool_names = {tool.name for tool in get_all_tools()}
    strategy_names = set(handlers._strategies)

    assert tool_names == strategy_names, (
        f"Tools without a strategy: {sorted(tool_names - strategy_names)}; "
        f"strategies without a tool definition: {sorted(strategy_names - tool_names)}"
    )
