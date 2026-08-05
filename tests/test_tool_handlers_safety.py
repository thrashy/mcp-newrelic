"""Tests for read-only-by-default gating in ToolHandlers."""

import pytest

from newrelic_mcp.handlers.tool_handlers import DESTRUCTIVE_TOOLS, WRITE_TOOLS, ToolHandlers


@pytest.fixture
def handlers(mock_client, config):
    return ToolHandlers(mock_client, config)


class TestWriteGating:
    async def test_write_tool_blocked_by_default(self, handlers, mock_client):
        result = await handlers.handle_tool_call("delete_dashboard", {"dashboard_guid": "MTIzNDU2Nzg5MA=="})
        assert "writes are disabled" in result.content[0].text
        mock_client.dashboards.delete_dashboard.assert_not_called()

    async def test_pure_create_allowed_when_writes_enabled(self, mock_client, config):
        config.enable_writes = True
        mock_client.dashboards.create_dashboard.return_value = {"guid": "g1"}
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("create_dashboard", {"name": "D"})
        assert "disabled" not in result.content[0].text

    async def test_destructive_blocked_even_with_writes_enabled(self, mock_client, config):
        config.enable_writes = True
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("delete_dashboard", {"dashboard_guid": "MTIzNDU2Nzg5MA=="})
        assert "destructive" in result.content[0].text
        mock_client.dashboards.delete_dashboard.assert_not_called()

    async def test_destructive_allowed_when_both_enabled(self, mock_client, config):
        config.enable_writes = True
        config.enable_destructive = True
        mock_client.dashboards.delete_dashboard.return_value = {"guid": "g1"}
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("delete_dashboard", {"dashboard_guid": "MTIzNDU2Nzg5MA=="})
        assert "disabled" not in result.content[0].text

    async def test_read_tool_never_gated(self, handlers, mock_client):
        from newrelic_mcp.types import PaginatedResult

        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert "disabled" not in result.content[0].text


class TestAllowDenyLists:
    async def test_allowlist_blocks_unlisted_tool(self, mock_client, config):
        config.allowed_tools = {"query_nrql"}
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert "not in the configured allowlist" in result.content[0].text

    async def test_denylist_blocks_listed_tool(self, mock_client, config):
        config.disabled_tools = {"list_alert_policies"}
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert "disabled by configuration" in result.content[0].text


class TestToolListIntegrity:
    def test_write_and_destructive_lists_reference_real_tools(self, handlers):
        strategy_names = set(handlers._strategies)
        assert WRITE_TOOLS <= strategy_names
        assert DESTRUCTIVE_TOOLS <= WRITE_TOOLS
