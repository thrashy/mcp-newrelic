"""Tests for the ToolHandlers dispatcher."""

import pytest

from newrelic_mcp.config import NewRelicConfig
from newrelic_mcp.handlers.tool_handlers import ToolHandlers
from newrelic_mcp.types import DecodedEntityGuid, PaginatedResult


@pytest.fixture
def config_without_account() -> NewRelicConfig:
    cfg = NewRelicConfig()
    cfg.api_key = "NRAK-test1234567890123456789012345678"
    cfg.region = "US"
    return cfg


class TestIsErrorFlag:
    async def test_successful_call_is_not_flagged(self, mock_client, config):
        mock_client.base.decode_entity_guid.return_value = DecodedEntityGuid(
            account_id=12345, domain="APM", entity_type="APPLICATION", domain_id="67890"
        )
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("decode_entity_guid", {"guid": "someguid1234"})
        assert result.is_error is False

    async def test_unknown_tool_is_flagged(self, mock_client, config):
        handlers = ToolHandlers(mock_client, config)
        assert (await handlers.handle_tool_call("no_such_tool", {})).is_error is True

    async def test_strategy_failure_is_flagged(self, mock_client, config):
        mock_client.alerts.get_alert_policies.side_effect = RuntimeError("boom")
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert result.is_error is True
        assert "boom" in result.content[0].text

    async def test_gated_tool_is_flagged(self, mock_client, config):
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("delete_dashboard", {"dashboard_guid": "MTIzNDU2Nzg5MA=="})
        assert result.is_error is True


class TestDispatch:
    async def test_unknown_tool_returns_error_text(self, mock_client, config):
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("no_such_tool", {})
        assert result.content[0].text == "Unknown tool: no_such_tool"

    async def test_missing_account_id_errors_cleanly(self, mock_client, config_without_account):
        handlers = ToolHandlers(mock_client, config_without_account)
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert "Account ID not provided" in result.content[0].text
        mock_client.alerts.get_alert_policies.assert_not_called()

    async def test_account_id_not_required_strategy_works_without_account(self, mock_client, config_without_account):
        mock_client.base.decode_entity_guid.return_value = DecodedEntityGuid(
            account_id=12345, domain="APM", entity_type="APPLICATION", domain_id="67890"
        )
        handlers = ToolHandlers(mock_client, config_without_account)
        result = await handlers.handle_tool_call("decode_entity_guid", {"guid": "someguid1234"})
        assert "Decoded entity GUID" in result.content[0].text
        assert "12345" in result.content[0].text

    async def test_account_id_override_blocked_by_default(self, mock_client, config):
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("list_alert_policies", {"account_id": "7654321"})
        assert "override is disabled" in result.content[0].text
        mock_client.alerts.get_alert_policies.assert_not_called()

    async def test_argument_account_id_overrides_config_when_enabled(self, mock_client, config):
        config.allow_account_override = True
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        handlers = ToolHandlers(mock_client, config)
        await handlers.handle_tool_call("list_alert_policies", {"account_id": "7654321"})
        mock_client.alerts.get_alert_policies.assert_called_once_with("7654321")

    async def test_config_account_id_used_by_default(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        handlers = ToolHandlers(mock_client, config)
        await handlers.handle_tool_call("list_alert_policies", {})
        mock_client.alerts.get_alert_policies.assert_called_once_with("1234567")

    async def test_unexpected_exception_rendered_as_error(self, mock_client, config):
        mock_client.alerts.get_alert_policies.side_effect = RuntimeError("boom")
        handlers = ToolHandlers(mock_client, config)
        result = await handlers.handle_tool_call("list_alert_policies", {})
        assert "Error executing list_alert_policies" in result.content[0].text
        assert "boom" in result.content[0].text
