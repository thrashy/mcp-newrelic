"""Tool handlers for New Relic MCP Server."""

import logging
from typing import Any

from mcp.types import TextContent

from ..client import NewRelicClient
from ..client.base_client import BaseNewRelicClient
from ..config import NewRelicConfig
from ..types import ToolError
from ..validators import ValidationError
from .strategies.alerts import (
    CreateAlertPolicyHandler,
    CreateMutingRuleHandler,
    CreateNotificationChannelHandler,
    CreateNotificationDestinationHandler,
    CreateNRQLConditionHandler,
    CreateWorkflowHandler,
    DeleteAlertPolicyHandler,
    DeleteMutingRuleHandler,
    DeleteNotificationDestinationHandler,
    DeleteNRQLConditionHandler,
    DeleteWorkflowHandler,
    ListAlertConditionsHandler,
    ListAlertPoliciesHandler,
    ListMutingRulesHandler,
    ListNotificationChannelsHandler,
    ListNotificationDestinationsHandler,
    ListWorkflowsHandler,
    UpdateAlertPolicyHandler,
    UpdateNRQLConditionHandler,
)
from .strategies.dashboard import (
    AddWidgetHandler,
    CreateDashboardHandler,
    DeleteDashboardHandler,
    DeleteWidgetHandler,
    GetDashboardsHandler,
    GetWidgetsHandler,
    SearchDashboardsHandler,
    UpdateWidgetHandler,
)
from .strategies.entities import (
    AddTagsHandler,
    DecodeEntityGuidHandler,
    DeleteTagsHandler,
    DeleteTagValuesHandler,
    EntitySearchHandler,
    GetEntityHandler,
    GetEntityTagsHandler,
    GetSyntheticResultsHandler,
    ListServiceLevelsHandler,
    ListSyntheticMonitorsHandler,
    ReplaceTagsHandler,
)
from .strategies.monitoring import (
    AlertViolationsHandler,
    AppErrorsHandler,
    AppPerformanceHandler,
    DeploymentsHandler,
    IncidentsHandler,
    InfrastructureHandler,
    QueryNRQLHandler,
)

logger = logging.getLogger(__name__)

WRITE_TOOLS = frozenset(
    {
        "create_dashboard",
        "add_widget_to_dashboard",
        "update_widget",
        "delete_widget",
        "delete_dashboard",
        "create_alert_policy",
        "update_alert_policy",
        "delete_alert_policy",
        "create_nrql_condition",
        "update_nrql_condition",
        "delete_nrql_condition",
        "create_notification_destination",
        "delete_notification_destination",
        "create_notification_channel",
        "create_workflow",
        "delete_workflow",
        "create_muting_rule",
        "delete_muting_rule",
        "add_tags_to_entity",
        "replace_tags_on_entity",
        "delete_tags_from_entity",
        "delete_tag_values",
    }
)

DESTRUCTIVE_TOOLS = frozenset(
    {
        "update_widget",
        "delete_widget",
        "delete_dashboard",
        "update_alert_policy",
        "delete_alert_policy",
        "update_nrql_condition",
        "delete_nrql_condition",
        "delete_notification_destination",
        "delete_workflow",
        "create_muting_rule",
        "delete_muting_rule",
        "replace_tags_on_entity",
        "delete_tags_from_entity",
        "delete_tag_values",
    }
)

ACCOUNT_SCOPED_GUID_ARGUMENTS = ("guid", "dashboard_guid", "page_guid", "monitor_guid")


class ToolHandlers:
    """Handles MCP tool operations using Strategy pattern"""

    def __init__(self, client: NewRelicClient, config: NewRelicConfig):
        self.client = client
        self.config = config
        self._strategies = {
            "query_nrql": QueryNRQLHandler(client, config),
            "get_app_performance": AppPerformanceHandler(client, config),
            "get_app_errors": AppErrorsHandler(client, config),
            "get_incidents": IncidentsHandler(client, config),
            "get_infrastructure_hosts": InfrastructureHandler(client, config),
            "get_alert_violations": AlertViolationsHandler(client, config),
            "get_deployments": DeploymentsHandler(client, config),
            "get_dashboards": GetDashboardsHandler(client, config),
            "create_dashboard": CreateDashboardHandler(client, config),
            "add_widget_to_dashboard": AddWidgetHandler(client, config),
            "search_all_dashboards": SearchDashboardsHandler(client, config),
            "get_dashboard_widgets": GetWidgetsHandler(client, config),
            "update_widget": UpdateWidgetHandler(client, config),
            "delete_widget": DeleteWidgetHandler(client, config),
            "delete_dashboard": DeleteDashboardHandler(client, config),
            "create_alert_policy": CreateAlertPolicyHandler(client, config),
            "update_alert_policy": UpdateAlertPolicyHandler(client, config),
            "delete_alert_policy": DeleteAlertPolicyHandler(client, config),
            "create_nrql_condition": CreateNRQLConditionHandler(client, config),
            "update_nrql_condition": UpdateNRQLConditionHandler(client, config),
            "delete_nrql_condition": DeleteNRQLConditionHandler(client, config),
            "create_notification_destination": CreateNotificationDestinationHandler(client, config),
            "delete_notification_destination": DeleteNotificationDestinationHandler(client, config),
            "create_notification_channel": CreateNotificationChannelHandler(client, config),
            "create_workflow": CreateWorkflowHandler(client, config),
            "delete_workflow": DeleteWorkflowHandler(client, config),
            "create_muting_rule": CreateMutingRuleHandler(client, config),
            "list_muting_rules": ListMutingRulesHandler(client, config),
            "delete_muting_rule": DeleteMutingRuleHandler(client, config),
            "list_alert_policies": ListAlertPoliciesHandler(client, config),
            "list_alert_conditions": ListAlertConditionsHandler(client, config),
            "list_notification_destinations": ListNotificationDestinationsHandler(client, config),
            "list_notification_channels": ListNotificationChannelsHandler(client, config),
            "list_workflows": ListWorkflowsHandler(client, config),
            "entity_search": EntitySearchHandler(client, config),
            "decode_entity_guid": DecodeEntityGuidHandler(client, config),
            "get_entity": GetEntityHandler(client, config),
            "get_entity_tags": GetEntityTagsHandler(client, config),
            "add_tags_to_entity": AddTagsHandler(client, config),
            "replace_tags_on_entity": ReplaceTagsHandler(client, config),
            "delete_tags_from_entity": DeleteTagsHandler(client, config),
            "delete_tag_values": DeleteTagValuesHandler(client, config),
            "list_service_levels": ListServiceLevelsHandler(client, config),
            "list_synthetic_monitors": ListSyntheticMonitorsHandler(client, config),
            "get_synthetic_results": GetSyntheticResultsHandler(client, config),
        }

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            if name not in self._strategies:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

            access_error = self._validate_tool_access(name)
            if access_error:
                return [TextContent(type="text", text=f"Error: {access_error}")]

            account_id, account_error = self._resolve_account_id(arguments)
            if account_error:
                return [TextContent(type="text", text=f"Error: {account_error}")]
            assert account_id is not None

            scope_error = self._validate_guid_account_scope(arguments, account_id)
            if scope_error:
                return [TextContent(type="text", text=f"Error: {scope_error}")]

            return await self._strategies[name].handle(arguments, account_id)

        except (ValidationError, ToolError) as e:
            return [TextContent(type="text", text=f"Error: {e}")]
        except Exception as e:
            logger.error("Error calling tool %s: %s", name, e)
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

    def _validate_tool_access(self, name: str) -> str | None:
        allowed_tools = self.config.effective_allowed_tools
        if allowed_tools is not None and name not in allowed_tools:
            return f"Tool '{name}' is not in NEW_RELIC_MCP_ALLOWED_TOOLS"

        if name in self.config.effective_disabled_tools:
            return f"Tool '{name}' is disabled by NEW_RELIC_MCP_DISABLED_TOOLS"

        if name in WRITE_TOOLS and not self.config.writes_enabled:
            return (
                f"Tool '{name}' is a write operation and writes are disabled. "
                "Set NEW_RELIC_MCP_ENABLE_WRITES=true only for trusted MCP clients."
            )

        if name in DESTRUCTIVE_TOOLS and not self.config.destructive_enabled:
            return (
                f"Tool '{name}' is destructive and destructive operations are disabled. "
                "Set NEW_RELIC_MCP_ENABLE_DESTRUCTIVE=true only when you intentionally need delete/replace/suppress behavior."
            )

        return None

    def _resolve_account_id(self, arguments: dict[str, Any]) -> tuple[str | None, str | None]:
        requested_account_id = arguments.get("account_id")
        configured_account_id = self.config.account_id
        account_id = requested_account_id or configured_account_id

        if not account_id:
            return None, "Account ID not provided. Provide via config file, command line, or account_id parameter."

        if (
            requested_account_id
            and configured_account_id
            and str(requested_account_id) != str(configured_account_id)
            and not self.config.account_override_enabled
        ):
            return (
                None,
                "account_id override is disabled. "
                "Set NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE=true only for intentional multi-account use.",
            )

        return str(account_id), None

    def _validate_guid_account_scope(self, arguments: dict[str, Any], account_id: str | None) -> str | None:
        if self.config.account_override_enabled or not account_id:
            return None

        for key in ACCOUNT_SCOPED_GUID_ARGUMENTS:
            guid = arguments.get(key)
            if not guid:
                continue
            try:
                decoded = BaseNewRelicClient.decode_entity_guid(str(guid))
            except ValueError as e:
                return f"Invalid {key}: {e}"
            if str(decoded.account_id) != str(account_id):
                return (
                    f"{key} belongs to account {decoded.account_id}, but this server is configured for account "
                    f"{account_id}. Set NEW_RELIC_MCP_ALLOW_ACCOUNT_OVERRIDE=true only for intentional multi-account use."
                )

        return None
