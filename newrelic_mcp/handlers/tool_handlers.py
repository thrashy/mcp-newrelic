"""Tool handlers for New Relic MCP Server."""

import logging
from typing import Any

from mcp.types import TextContent

from ..client import NewRelicClient
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
            account_id = arguments.get("account_id", self.config.account_id)
            if not account_id:
                return [
                    TextContent(
                        type="text",
                        text="Error: Account ID not provided. Provide via config file, command line, or account_id parameter.",
                    )
                ]

            if name in self._strategies:
                return await self._strategies[name].handle(arguments, account_id)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except (ValidationError, ToolError) as e:
            return [TextContent(type="text", text=f"Error: {e}")]
        except Exception as e:
            logger.error("Error calling tool %s: %s", name, e)
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]
