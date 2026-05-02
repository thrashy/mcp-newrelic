"""Tests for server-side MCP tool safety controls."""

import base64

from newrelic_mcp.handlers.tool_handlers import ToolHandlers
from newrelic_mcp.types import PaginatedResult


def _guid(account_id: str = "1234567") -> str:
    return base64.b64encode(f"{account_id}|APM|APPLICATION|entity-1".encode()).decode()


class TestToolSafetyControls:
    async def test_write_tool_blocked_by_default(self, mock_client, config):
        mock_client.alerts.create_alert_policy.return_value = {"id": "policy-1"}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("create_alert_policy", {"name": "Policy"})

        assert "writes are disabled" in result[0].text
        mock_client.alerts.create_alert_policy.assert_not_called()

    async def test_write_tool_allowed_when_enabled(self, mock_client, config):
        config.enable_writes = True
        mock_client.alerts.create_alert_policy.return_value = {"id": "policy-1"}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("create_alert_policy", {"name": "Policy"})

        assert "created successfully" in result[0].text
        mock_client.alerts.create_alert_policy.assert_called_once_with("1234567", "Policy", "PER_POLICY")

    async def test_destructive_tool_blocked_when_only_writes_enabled(self, mock_client, config):
        config.enable_writes = True
        mock_client.alerts.delete_alert_policy.return_value = {"success": True}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("delete_alert_policy", {"policy_id": "policy-1"})

        assert "destructive operations are disabled" in result[0].text
        mock_client.alerts.delete_alert_policy.assert_not_called()

    async def test_destructive_tool_allowed_when_explicitly_enabled(self, mock_client, config):
        config.enable_writes = True
        config.enable_destructive = True
        mock_client.alerts.delete_alert_policy.return_value = {"success": True, "id": "policy-1"}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("delete_alert_policy", {"policy_id": "policy-1"})

        assert "deleted successfully" in result[0].text
        mock_client.alerts.delete_alert_policy.assert_called_once_with("1234567", "policy-1")

    async def test_account_override_blocked_by_default(self, mock_client, config):
        mock_client.query_nrql.return_value = {"data": {"actor": {"account": {"nrql": {"results": []}}}}}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call(
            "query_nrql", {"account_id": "9999999", "query": "SELECT count(*) FROM Transaction"}
        )

        assert "account_id override is disabled" in result[0].text
        mock_client.query_nrql.assert_not_called()

    async def test_account_override_allowed_when_configured(self, mock_client, config):
        config.allow_account_override = True
        mock_client.query_nrql.return_value = {"data": {"actor": {"account": {"nrql": {"results": []}}}}}
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call(
            "query_nrql", {"account_id": "9999999", "query": "SELECT count(*) FROM Transaction"}
        )

        assert "NRQL Query Results" in result[0].text
        mock_client.query_nrql.assert_called_once_with("9999999", "SELECT count(*) FROM Transaction")

    async def test_guid_account_mismatch_blocked_by_default(self, mock_client, config):
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("get_entity", {"guid": _guid("9999999")})

        assert "belongs to account 9999999" in result[0].text
        mock_client.base.get_entity.assert_not_called()

    async def test_tool_allowlist_blocks_unspecified_tool(self, mock_client, config):
        config.allowed_tools = {"query_nrql"}
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("list_alert_policies", {})

        assert "not in NEW_RELIC_MCP_ALLOWED_TOOLS" in result[0].text
        mock_client.alerts.get_alert_policies.assert_not_called()

    async def test_tool_denylist_blocks_tool(self, mock_client, config):
        config.disabled_tools = {"list_alert_policies"}
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        handler = ToolHandlers(mock_client, config)

        result = await handler.handle_tool_call("list_alert_policies", {})

        assert "disabled by NEW_RELIC_MCP_DISABLED_TOOLS" in result[0].text
        mock_client.alerts.get_alert_policies.assert_not_called()
