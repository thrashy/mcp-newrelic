"""Monitoring tool handlers using Strategy pattern"""

import json
from typing import Any

from mcp.types import TextContent

from ...validators import InputValidator
from .base import ToolHandlerStrategy


class QueryNRQLHandler(ToolHandlerStrategy):
    """Handler for NRQL query execution"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        query = InputValidator.validate_nrql_query(arguments["query"])
        result = await self.client.query_nrql(account_id, query)
        return [
            TextContent(
                type="text", text=f"NRQL Query Results:\n```json\n{json.dumps(result, indent=2, default=str)}\n```"
            )
        ]


class AppPerformanceHandler(ToolHandlerStrategy):
    """Handler for application performance metrics"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        app_name = InputValidator.validate_app_name(arguments["app_name"])
        hours = InputValidator.validate_time_range(arguments.get("hours", 1))

        metrics = self._unwrap(
            await self.client.monitoring.get_performance_metrics(account_id, app_name, hours),
            f"getting performance metrics for {app_name}",
        )

        avg_duration = self._format_duration(metrics.get("avg_duration"))
        p95_duration = self._format_duration(metrics.get("p95_duration"))
        throughput = self._format_throughput(metrics.get("throughput"))

        return self._create_success_response(
            f"Performance metrics for '{app_name}' (last {hours}h):\n"
            f"- Average response time: {avg_duration}\n"
            f"- 95th percentile: {p95_duration}\n"
            f"- Throughput: {throughput}"
        )

    @staticmethod
    def _format_throughput(throughput: Any) -> str:
        """Format throughput with proper units"""
        return f"{throughput:.2f} req/min" if isinstance(throughput, int | float) else "N/A"


class AppErrorsHandler(ToolHandlerStrategy):
    """Handler for application error metrics"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        app_name = InputValidator.validate_app_name(arguments["app_name"])
        hours = InputValidator.validate_time_range(arguments.get("hours", 1))

        metrics = self._unwrap(
            await self.client.monitoring.get_error_metrics(account_id, app_name, hours),
            f"getting error metrics for {app_name}",
        )

        error_count = metrics.get("error_count", "N/A")
        avg_duration = self._format_duration(metrics.get("avg_duration"))

        return self._create_success_response(
            f"Error metrics for '{app_name}' (last {hours}h):\n"
            f"- Error count: {error_count}\n"
            f"- Average error duration: {avg_duration}"
        )


class IncidentsHandler(ToolHandlerStrategy):
    """Handler for incidents retrieval"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        hours = InputValidator.validate_time_range(arguments.get("hours", 24))
        result = await self.client.monitoring.get_recent_incidents(account_id, hours)
        return self._handle_list_response(
            result,
            error_context="getting incidents",
            empty_message=f"No incidents found in the last {hours} hours.",
            item_noun=f"incidents in the last {hours} hours",
            format_item=self._format_incident,
        )

    @staticmethod
    def _format_incident(incident: dict[str, Any]) -> str:
        return (
            f"- **{incident.get('title', 'Unknown')}**\n"
            f"  State: {incident.get('state', 'Unknown')}\n"
            f"  Time: {incident.get('timestamp', 'Unknown')}\n\n"
        )


class InfrastructureHandler(ToolHandlerStrategy):
    """Handler for infrastructure hosts"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        hours = InputValidator.validate_time_range(arguments.get("hours", 1))
        result = await self.client.monitoring.get_infrastructure_hosts(account_id, hours)
        return self._handle_list_response(
            result,
            error_context="getting infrastructure hosts",
            empty_message=f"No infrastructure hosts found in the last {hours} hours.",
            item_noun=f"infrastructure hosts (last {hours}h)",
            format_item=self._format_host,
        )

    @staticmethod
    def _format_host(host: dict[str, Any]) -> str:
        text = f"- **{host.get('hostname', 'Unknown')}**\n"
        for label, key in [("CPU", "cpu_percent"), ("Memory", "memory_percent"), ("Disk", "disk_percent")]:
            value = host.get(key, "N/A")
            if value != "N/A":
                text += f"  {label}: {value:.1f}%\n"
        return text + "\n"


class AlertViolationsHandler(ToolHandlerStrategy):
    """Handler for alert violations"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        hours = InputValidator.validate_time_range(arguments.get("hours", 24))
        result = await self.client.monitoring.get_alert_violations(account_id, hours)
        return self._handle_list_response(
            result,
            error_context="getting alert violations",
            empty_message=f"No alert violations found in the last {hours} hours.",
            item_noun=f"alert violations (last {hours}h)",
            format_item=self._format_violation,
        )

    @staticmethod
    def _format_violation(violation: dict[str, Any]) -> str:
        title = violation.get("title", violation.get("name", "Unknown Alert"))
        state = violation.get("state", "Unknown")
        timestamp = violation.get("timestamp", violation.get("createdAt", "Unknown"))
        priority = violation.get("priority", violation.get("priority_level", "Unknown"))
        return f"- **{title}**\n  State: {state}\n  Priority: {priority}\n  Time: {timestamp}\n\n"


class DeploymentsHandler(ToolHandlerStrategy):
    """Handler for deployments"""

    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        app_name = arguments.get("app_name")
        hours = InputValidator.validate_time_range(arguments.get("hours", 168))
        if app_name:
            app_name = InputValidator.validate_app_name(app_name)

        scope = f"for {app_name} " if app_name else ""
        result = await self.client.monitoring.get_deployments(account_id, app_name, hours)
        return self._handle_list_response(
            result,
            error_context="getting deployments",
            empty_message=f"No deployments found {scope}in the last {hours} hours.",
            item_noun=f"deployments {scope}(last {hours}h)",
            format_item=self._format_deployment,
        )

    @staticmethod
    def _format_deployment(deployment: dict[str, Any]) -> str:
        app = deployment.get("appName", "Unknown App")
        timestamp = deployment.get("timestamp", deployment.get("createdAt", "Unknown"))
        revision = deployment.get("revision", "Unknown")
        description = deployment.get("description", "")
        text = f"- **{app}**\n  Time: {timestamp}\n  Revision: {revision}\n"
        if description:
            text += f"  Description: {description}\n"
        return text + "\n"
