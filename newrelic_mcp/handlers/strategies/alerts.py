"""Alert tool handlers using Strategy pattern"""

from typing import Any

from mcp.types import TextContent

from ...types import PaginatedResult
from .base import ToolHandlerStrategy


class CreateAlertPolicyHandler(ToolHandlerStrategy):
    """Handler for creating alert policies"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        name = arguments["name"]
        incident_preference = arguments.get("incident_preference", "PER_POLICY")

        result = self._unwrap(
            await self.client.alerts.create_alert_policy(account_id, name, incident_preference),
            f"creating alert policy '{name}'",
        )

        policy_id = result.get("id", "Unknown")
        return self._create_success_response(
            f"Alert policy '{name}' created successfully!\nPolicy ID: {policy_id}\n"
            f"Incident preference: {incident_preference}"
        )


class CreateNRQLConditionHandler(ToolHandlerStrategy):
    """Handler for creating NRQL alert conditions"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        policy_id = arguments["policy_id"]
        name = arguments["name"]
        nrql_query = arguments["nrql_query"]
        threshold = arguments["threshold"]
        threshold_duration = arguments.get("threshold_duration", 300)
        threshold_operator = arguments.get("threshold_operator", "ABOVE")
        priority = arguments.get("priority", "CRITICAL")
        aggregation_window = arguments.get("aggregation_window", 60)
        description = arguments.get("description")

        # Map HIGH/MEDIUM/LOW to WARNING since API only accepts CRITICAL/WARNING
        if priority in ["HIGH", "MEDIUM", "LOW"]:
            priority = "WARNING"

        result = self._unwrap(
            await self.client.alerts.create_nrql_condition(
                account_id,
                policy_id,
                name,
                nrql_query,
                threshold,
                threshold_duration,
                threshold_operator,
                priority,
                aggregation_window,
                description,
            ),
            f"creating NRQL condition '{name}'",
        )

        condition_id = result.get("id", "Unknown")
        return self._create_success_response(
            f"NRQL alert condition '{name}' created successfully!\n"
            f"Condition ID: {condition_id}\nPolicy ID: {policy_id}\n"
            f"Threshold: {threshold_operator} {threshold} for {threshold_duration}s"
        )


class CreateNotificationDestinationHandler(ToolHandlerStrategy):
    """Handler for creating notification destinations"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        name = arguments["name"]
        destination_type = arguments["type"]
        properties = arguments["properties"]

        result = self._unwrap(
            await self.client.alerts.create_notification_destination(account_id, name, destination_type, properties),
            f"creating notification destination '{name}'",
        )

        destination_id = result.get("id", "Unknown")
        return self._create_success_response(
            f"Notification destination '{name}' ({destination_type}) created successfully!\n"
            f"Destination ID: {destination_id}"
        )


class CreateNotificationChannelHandler(ToolHandlerStrategy):
    """Handler for creating notification channels"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        name = arguments["name"]
        destination_id = arguments["destination_id"]
        channel_type = arguments["type"]
        product = arguments.get("product", "IINT")
        properties = arguments.get("properties", {})

        result = self._unwrap(
            await self.client.alerts.create_notification_channel(
                account_id, name, destination_id, channel_type, product, properties
            ),
            f"creating notification channel '{name}'",
        )

        channel_id = result.get("id", "Unknown")
        return self._create_success_response(
            f"Notification channel '{name}' ({channel_type}) created successfully!\n"
            f"Channel ID: {channel_id}\nDestination ID: {destination_id}"
        )


class CreateWorkflowHandler(ToolHandlerStrategy):
    """Handler for creating workflows"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        name = arguments["name"]
        channel_ids = arguments["channel_ids"]
        enabled = arguments.get("enabled", True)
        filter_name = arguments.get("filter_name", "Filter-name")
        filter_predicates = arguments.get("filter_predicates", [])

        result = self._unwrap(
            await self.client.alerts.create_workflow(
                account_id, name, channel_ids, enabled, filter_name, filter_predicates
            ),
            f"creating workflow '{name}'",
        )

        workflow_id = result.get("id", "Unknown")
        return self._create_success_response(
            f"Workflow '{name}' created successfully!\nWorkflow ID: {workflow_id}\n"
            f"Connected to {len(channel_ids)} notification channel(s)"
        )


class ListAlertPoliciesHandler(ToolHandlerStrategy):
    """Handler for listing alert policies"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.alerts.get_alert_policies(account_id)
        return self._handle_list_response(
            result,
            error_context="listing alert policies",
            empty_message="No alert policies found.",
            item_noun="alert policies",
            format_item=self._format_policy,
        )

    @staticmethod
    def _format_policy(policy: dict[str, Any]) -> str:
        name = policy.get("name", "Unknown")
        policy_id = policy.get("id", "Unknown")
        incident_preference = policy.get("incidentPreference", "Unknown")
        return f"- **{name}**\n  ID: {policy_id}\n  Incident Preference: {incident_preference}\n\n"


class DeleteAlertPolicyHandler(ToolHandlerStrategy):
    """Handler for deleting alert policies"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        policy_id = arguments["policy_id"]
        self._unwrap(
            await self.client.alerts.delete_alert_policy(account_id, policy_id),
            f"deleting alert policy '{policy_id}'",
        )
        return self._create_success_response(f"Alert policy '{policy_id}' deleted successfully.")


class UpdateAlertPolicyHandler(ToolHandlerStrategy):
    """Handler for updating alert policies"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        policy_id = arguments["policy_id"]
        name = arguments.get("name")
        incident_preference = arguments.get("incident_preference")

        result = self._unwrap(
            await self.client.alerts.update_alert_policy(account_id, policy_id, name, incident_preference),
            f"updating alert policy '{policy_id}'",
        )

        updated_name = result.get("name", policy_id)
        return self._create_success_response(f"Alert policy '{updated_name}' updated successfully.")


class DeleteNRQLConditionHandler(ToolHandlerStrategy):
    """Handler for deleting NRQL alert conditions"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        condition_id = arguments["condition_id"]
        self._unwrap(
            await self.client.alerts.delete_nrql_condition(account_id, condition_id),
            f"deleting condition '{condition_id}'",
        )
        return self._create_success_response(f"Alert condition '{condition_id}' deleted successfully.")


class UpdateNRQLConditionHandler(ToolHandlerStrategy):
    """Handler for updating NRQL alert conditions"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        condition_id = arguments["condition_id"]
        self._unwrap(
            await self.client.alerts.update_nrql_condition(
                account_id,
                condition_id,
                name=arguments.get("name"),
                nrql_query=arguments.get("nrql_query"),
                enabled=arguments.get("enabled"),
                threshold=arguments.get("threshold"),
                threshold_operator=arguments.get("threshold_operator"),
                threshold_duration=arguments.get("threshold_duration"),
                description=arguments.get("description"),
                priority=arguments.get("priority"),
            ),
            f"updating condition '{condition_id}'",
        )
        return self._create_success_response(f"Alert condition '{condition_id}' updated successfully.")


class DeleteNotificationDestinationHandler(ToolHandlerStrategy):
    """Handler for deleting notification destinations"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        destination_id = arguments["destination_id"]
        self._unwrap(
            await self.client.alerts.delete_notification_destination(account_id, destination_id),
            f"deleting destination '{destination_id}'",
        )
        return self._create_success_response(f"Notification destination '{destination_id}' deleted successfully.")


class DeleteWorkflowHandler(ToolHandlerStrategy):
    """Handler for deleting workflows"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        workflow_id = arguments["workflow_id"]
        delete_channels = arguments.get("delete_channels", True)
        self._unwrap(
            await self.client.alerts.delete_workflow(account_id, workflow_id, delete_channels),
            f"deleting workflow '{workflow_id}'",
        )
        return self._create_success_response(f"Workflow '{workflow_id}' deleted successfully.")


class ListAlertConditionsHandler(ToolHandlerStrategy):
    """Handler for listing alert conditions"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        policy_id = arguments.get("policy_id")
        name = arguments.get("name")
        query = arguments.get("query")

        result = await self.client.alerts.get_alert_conditions(account_id, policy_id, name=name, query=query)

        # Resolve policy IDs to names
        if isinstance(result, PaginatedResult) and result.items:
            policy_ids = {c.get("policyId") for c in result.items if c.get("policyId")}
            if policy_ids:
                policies_result = await self.client.alerts.get_alert_policies(account_id)
                if isinstance(policies_result, PaginatedResult) and policies_result.items:
                    policy_map = {str(p["id"]): p.get("name", "Unknown") for p in policies_result.items}
                    for condition in result.items:
                        pid = str(condition.get("policyId", ""))
                        condition["policyName"] = policy_map.get(pid, f"Policy {pid}")

        scope = f" for policy {policy_id}" if policy_id else ""
        return self._handle_list_response(
            result,
            error_context="listing alert conditions",
            empty_message=f"No alert conditions found{scope}.",
            item_noun=f"alert conditions{scope}",
            format_item=self._format_condition,
        )

    @staticmethod
    def _format_condition(condition: dict[str, Any]) -> str:
        name = condition.get("name", "Unknown")
        condition_id = condition.get("id", "Unknown")
        enabled = condition.get("enabled", "Unknown")
        policy_name = condition.get("policyName", "Unknown")
        description = condition.get("description")

        nrql = condition.get("nrql", {})
        query = nrql.get("query", "") if isinstance(nrql, dict) else ""

        terms = condition.get("terms", [])

        lines = [f"- **{name}**", f"  ID: {condition_id}", f"  Policy: {policy_name}", f"  Enabled: {enabled}"]

        if description:
            lines.append(f"  Description: {description}")

        if query:
            lines.append(f"  NRQL: `{query}`")

        for term in terms:
            priority = term.get("priority", "").capitalize()
            operator = term.get("operator", "").lower()
            threshold = term.get("threshold")
            duration = term.get("thresholdDuration")
            if threshold is not None:
                lines.append(f"  {priority}: {operator} {threshold} for {duration}s")

        lines.append("")
        return "\n".join(lines) + "\n"


class ListNotificationDestinationsHandler(ToolHandlerStrategy):
    """Handler for listing notification destinations"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.alerts.get_destinations(account_id)
        return self._handle_list_response(
            result,
            error_context="listing notification destinations",
            empty_message="No notification destinations found.",
            item_noun="notification destinations",
            format_item=self._format_destination,
        )

    @staticmethod
    def _format_destination(dest: dict[str, Any]) -> str:
        name = dest.get("name", "Unknown")
        dest_id = dest.get("id", "Unknown")
        dest_type = dest.get("type", "Unknown")
        return f"- **{name}**\n  ID: {dest_id}\n  Type: {dest_type}\n\n"


class ListNotificationChannelsHandler(ToolHandlerStrategy):
    """Handler for listing notification channels"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.alerts.get_notification_channels(account_id)
        return self._handle_list_response(
            result,
            error_context="listing notification channels",
            empty_message="No notification channels found.",
            item_noun="notification channels",
            format_item=self._format_channel,
        )

    @staticmethod
    def _format_channel(channel: dict[str, Any]) -> str:
        name = channel.get("name", "Unknown")
        channel_id = channel.get("id", "Unknown")
        channel_type = channel.get("type", "Unknown")
        destination_id = channel.get("destinationId", "Unknown")
        return f"- **{name}**\n  ID: {channel_id}\n  Type: {channel_type}\n  Destination ID: {destination_id}\n\n"


class ListWorkflowsHandler(ToolHandlerStrategy):
    """Handler for listing workflows"""

    async def handle(self, _arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        result = await self.client.alerts.get_workflows(account_id)
        return self._handle_list_response(
            result,
            error_context="listing workflows",
            empty_message="No workflows found.",
            item_noun="workflows",
            format_item=self._format_workflow,
        )

    @staticmethod
    def _format_workflow(workflow: dict[str, Any]) -> str:
        name = workflow.get("name", "Unknown")
        workflow_id = workflow.get("id", "Unknown")
        return f"- **{name}**\n  ID: {workflow_id}\n\n"
