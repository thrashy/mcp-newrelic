"""Contract test: every advertised tool has a handler strategy and vice versa."""

from unittest.mock import MagicMock

from newrelic_mcp.config import NewRelicConfig
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


def test_workflow_predicate_operators_match_nerdgraph():
    tools = {tool.name: tool for tool in get_all_tools()}
    create_ops = tools["create_workflow"].input_schema["properties"]["filter_predicates"]["items"]["properties"]
    update_ops = tools["update_workflow"].input_schema["properties"]["issues_filter"]["properties"]["predicates"]
    for operator_schema in (create_ops["operator"], update_ops["items"]["properties"]["operator"]):
        assert "EXACTLY_MATCHES" in operator_schema["enum"]
        assert not {"NOT_EQUAL", "IN", "NOT_IN"} & set(operator_schema["enum"])
