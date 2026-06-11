"""Resource handlers for New Relic MCP Server."""

import logging

from mcp.types import Resource
from pydantic import AnyUrl

from ..client import NewRelicClient
from ..config import NewRelicConfig
from ..types import ApiError
from ..utils.alert_formatters import format_alert_condition, format_alert_policy
from ..utils.error_handling import format_resource_error

logger = logging.getLogger(__name__)


class ResourceHandlers:
    """Handles MCP resource operations"""

    def __init__(self, client: NewRelicClient, config: NewRelicConfig):
        self.client = client
        self.config = config

    @staticmethod
    def get_resources() -> list[Resource]:
        return [
            Resource(
                uri=AnyUrl("newrelic://applications"),
                name="New Relic Applications",
                description="List of applications monitored by New Relic",
                mimeType="application/json",
            ),
            Resource(
                uri=AnyUrl("newrelic://incidents/recent"),
                name="Recent Incidents",
                description="Recent incidents from New Relic",
                mimeType="application/json",
            ),
            Resource(
                uri=AnyUrl("newrelic://dashboards"),
                name="New Relic Dashboards",
                description="List of available dashboards",
                mimeType="application/json",
            ),
            Resource(
                uri=AnyUrl("newrelic://alerts/policies"),
                name="Alert Policies",
                description="List of alert policies and their configurations",
                mimeType="application/json",
            ),
            Resource(
                uri=AnyUrl("newrelic://alerts/conditions"),
                name="Alert Conditions",
                description="List of all alert conditions across policies",
                mimeType="application/json",
            ),
            Resource(
                uri=AnyUrl("newrelic://alerts/workflows"),
                name="Alert Workflows",
                description="List of alert workflows and notification configurations",
                mimeType="application/json",
            ),
        ]

    async def read_resource(self, uri: str) -> str:
        if not self.client or not self.config.account_id:
            raise ValueError(
                "New Relic client not configured. Provide credentials via config file, command line, or environment variables."
            )

        account_id: str = self.config.account_id

        if uri == "newrelic://applications":
            return await self._read_applications(account_id)
        if uri == "newrelic://incidents/recent":
            return await self._read_incidents(account_id)
        if uri == "newrelic://dashboards":
            return await self._read_dashboards(account_id)
        if uri == "newrelic://alerts/policies":
            return await self._read_alert_policies(account_id)
        if uri == "newrelic://alerts/conditions":
            return await self._read_alert_conditions(account_id)
        if uri == "newrelic://alerts/workflows":
            return await self._read_alert_workflows(account_id)
        raise ValueError(f"Unknown resource URI: {uri}")

    async def _read_applications(self, account_id: str) -> str:
        result = await self.client.monitoring.get_applications(account_id)
        if isinstance(result, ApiError):
            return format_resource_error(result, "New Relic Applications")
        return f"# New Relic Applications\n\n{len(result)} applications found:\n\n" + "\n".join(
            [f"- **{app.get('name', 'Unknown')}** (ID: {app.get('appId', 'N/A')})" for app in result]
        )

    async def _read_incidents(self, account_id: str) -> str:
        result = await self.client.monitoring.get_recent_incidents(account_id)
        if isinstance(result, ApiError):
            return format_resource_error(result, "Recent Incidents")
        return f"# Recent Incidents\n\n{len(result)} incidents found:\n\n" + "\n".join(
            [
                f"- **{inc.get('title', 'Unknown')}** - {inc.get('state', 'Unknown')} - {inc.get('timestamp', 'Unknown')}"
                for inc in result
            ]
        )

    async def _read_dashboards(self, account_id: str) -> str:
        result = await self.client.dashboards.get_dashboards(account_id, limit=200)

        if isinstance(result, ApiError):
            return format_resource_error(result, "New Relic Dashboards")

        if not result.items:
            return "# New Relic Dashboards\n\nNo dashboards found."

        dashboard_list = f"# New Relic Dashboards\n\n{len(result.items)} dashboards found:\n\n"
        for dashboard in result.items:
            name = dashboard.get("name", "Unknown")
            guid = dashboard.get("guid", "Unknown")
            created = dashboard.get("createdAt", "Unknown")
            permalink = dashboard.get("permalink", "")

            dashboard_list += f"## {name}\n"
            dashboard_list += f"- **GUID**: {guid}\n"
            dashboard_list += f"- **Created**: {created}\n"
            if permalink:
                dashboard_list += f"- **URL**: {permalink}\n"
            dashboard_list += "\n"

        return dashboard_list

    async def _read_alert_policies(self, account_id: str) -> str:
        result = await self.client.alerts.get_alert_policies(account_id)

        if isinstance(result, ApiError):
            return format_resource_error(result, "Alert Policies")

        if not result.items:
            return "# Alert Policies\n\nNo alert policies found."

        policies_list = f"# Alert Policies\n\n{result.total_count or len(result.items)} alert policies found:\n\n"
        for policy in result.items:
            policies_list += format_alert_policy(policy)

        return policies_list

    async def _read_alert_conditions(self, account_id: str) -> str:
        result = await self.client.alerts.get_alert_conditions(account_id)

        if isinstance(result, ApiError):
            return format_resource_error(result, "Alert Conditions")

        if not result.items:
            return "# Alert Conditions\n\nNo alert conditions found."

        conditions_list = f"# Alert Conditions\n\n{result.total_count or len(result.items)} alert conditions found:\n\n"
        for condition in result.items:
            condition.setdefault("policyName", f"Policy {condition.get('policyId', 'Unknown')}")
            conditions_list += format_alert_condition(condition)

        return conditions_list

    async def _read_alert_workflows(self, account_id: str) -> str:
        result = await self.client.alerts.get_workflows(account_id)

        if isinstance(result, ApiError):
            return format_resource_error(result, "Alert Workflows")

        if not result.items:
            return "# Alert Workflows\n\nNo alert workflows found."

        workflows_list = f"# Alert Workflows\n\n{result.total_count or len(result.items)} alert workflows found:\n\n"
        for workflow in result.items:
            workflows_list += self._format_workflow_info(workflow)

        return workflows_list

    @staticmethod
    def _format_workflow_info(workflow: dict) -> str:
        name = workflow.get("name", "Unknown")
        workflow_id = workflow.get("id", "Unknown")
        enabled = workflow.get("enabled", False)
        destinations = workflow.get("destinationConfigurations", [])
        issues_filter = workflow.get("issuesFilter", {})

        result = f"## {name}\n"
        result += f"- **Workflow ID**: {workflow_id}\n"
        result += f"- **Enabled**: {enabled}\n"
        result += f"- **Destinations**: {len(destinations)} configured\n"

        if destinations:
            result += "- **Destination Details**:\n"
            for dest in destinations[:3]:
                dest_name = dest.get("name", "Unknown")
                dest_type = dest.get("type", "Unknown")
                result += f"  - {dest_name} ({dest_type})\n"
            if len(destinations) > 3:
                result += f"  - ... and {len(destinations) - 3} more\n"

        filter_name = issues_filter.get("name", "No filter")
        result += f"- **Filter**: {filter_name}\n\n"
        return result
