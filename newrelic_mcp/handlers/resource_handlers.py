"""Resource handlers for New Relic MCP Server."""

import logging
from collections.abc import Callable
from typing import Any

from mcp.types import Resource

from ..client import NewRelicClient
from ..config import NewRelicConfig
from ..types import ApiError, PaginatedResult
from ..utils.alert_formatters import format_alert_condition, format_alert_policy
from ..utils.dashboard_formatters import format_dashboard_list
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
                uri="newrelic://applications",
                name="New Relic Applications",
                description="List of applications monitored by New Relic",
                mime_type="application/json",
            ),
            Resource(
                uri="newrelic://incidents/recent",
                name="Recent Incidents",
                description="Recent incidents from New Relic",
                mime_type="application/json",
            ),
            Resource(
                uri="newrelic://dashboards",
                name="New Relic Dashboards",
                description="List of available dashboards",
                mime_type="application/json",
            ),
            Resource(
                uri="newrelic://alerts/policies",
                name="Alert Policies",
                description="List of alert policies and their configurations",
                mime_type="application/json",
            ),
            Resource(
                uri="newrelic://alerts/conditions",
                name="Alert Conditions",
                description="List of all alert conditions across policies",
                mime_type="application/json",
            ),
            Resource(
                uri="newrelic://alerts/workflows",
                name="Alert Workflows",
                description="List of alert workflows and notification configurations",
                mime_type="application/json",
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

        return "# New Relic Dashboards\n\n" + format_dashboard_list(result.items)

    @staticmethod
    def _render_list(
        result: PaginatedResult | ApiError,
        *,
        title: str,
        noun: str,
        format_item: Callable[[dict[str, Any]], str],
    ) -> str:
        if isinstance(result, ApiError):
            return format_resource_error(result, title)
        if not result.items:
            return f"# {title}\n\nNo {noun} found."
        header = f"# {title}\n\n{result.total_count or len(result.items)} {noun} found:\n\n"
        return header + "".join(format_item(item) for item in result.items)

    async def _read_alert_policies(self, account_id: str) -> str:
        return self._render_list(
            await self.client.alerts.get_alert_policies(account_id),
            title="Alert Policies",
            noun="alert policies",
            format_item=format_alert_policy,
        )

    async def _read_alert_conditions(self, account_id: str) -> str:
        def format_with_policy_name(condition: dict[str, Any]) -> str:
            condition.setdefault("policyName", f"Policy {condition.get('policyId', 'Unknown')}")
            return format_alert_condition(condition)

        return self._render_list(
            await self.client.alerts.get_alert_conditions(account_id),
            title="Alert Conditions",
            noun="alert conditions",
            format_item=format_with_policy_name,
        )

    async def _read_alert_workflows(self, account_id: str) -> str:
        return self._render_list(
            await self.client.alerts.get_workflows(account_id),
            title="Alert Workflows",
            noun="alert workflows",
            format_item=self._format_workflow_info,
        )

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
