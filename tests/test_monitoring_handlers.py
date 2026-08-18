"""Tests for monitoring tool handler strategies."""

import pytest

from newrelic_mcp.handlers.strategies.monitoring import (
    AlertViolationsHandler,
    AppErrorsHandler,
    AppPerformanceHandler,
    DeploymentsHandler,
    IncidentsHandler,
    InfrastructureHandler,
    QueryNRQLHandler,
)
from newrelic_mcp.types import ApiError, ToolError
from newrelic_mcp.validators import ValidationError


class TestQueryNRQLHandler:
    async def test_valid_query_returns_result(self, mock_client, config):
        mock_client.query_nrql.return_value = {"data": {"result": "ok"}}
        handler = QueryNRQLHandler(mock_client, config)

        result = await handler.handle({"query": "SELECT count(*) FROM Transaction SINCE 1 hour ago"}, "1234567")

        assert len(result) == 1
        assert "NRQL Query Results" in result[0].text
        mock_client.query_nrql.assert_called_once()

    async def test_invalid_query_returns_error(self, mock_client, config):
        handler = QueryNRQLHandler(mock_client, config)
        with pytest.raises(ValidationError):
            await handler.handle({"query": "DROP TABLE evil"}, "1234567")
        mock_client.query_nrql.assert_not_called()

    async def test_empty_query_returns_error(self, mock_client, config):
        handler = QueryNRQLHandler(mock_client, config)
        with pytest.raises(ValidationError):
            await handler.handle({"query": ""}, "1234567")


class TestAppPerformanceHandler:
    async def test_success_formats_metrics(self, mock_client, config):
        mock_client.monitoring.get_performance_metrics.return_value = {
            "avg_duration": 0.1205,
            "p95_duration": {"95": 0.45},
            "throughput": 35.2,
        }
        handler = AppPerformanceHandler(mock_client, config)
        result = await handler.handle({"app_name": "MyApp", "hours": 1}, "1234567")

        text = result[0].text
        assert "MyApp" in text
        assert "120.50ms" in text
        assert "450.00ms" in text
        assert "35.20 req/min" in text

    async def test_error_in_metrics_raises_tool_error(self, mock_client, config):
        mock_client.monitoring.get_performance_metrics.return_value = ApiError("query failed")
        handler = AppPerformanceHandler(mock_client, config)
        with pytest.raises(ToolError, match="query failed"):
            await handler.handle({"app_name": "MyApp"}, "1234567")

    async def test_missing_metric_values_show_na(self, mock_client, config):
        mock_client.monitoring.get_performance_metrics.return_value = {}
        handler = AppPerformanceHandler(mock_client, config)
        result = await handler.handle({"app_name": "MyApp"}, "1234567")
        assert "N/A" in result[0].text


class TestAppErrorsHandler:
    async def test_success_formats_error_count(self, mock_client, config):
        mock_client.monitoring.get_error_metrics.return_value = {"error_count": 42, "avg_duration": 0.2}
        handler = AppErrorsHandler(mock_client, config)
        result = await handler.handle({"app_name": "MyApp", "hours": 2}, "1234567")

        text = result[0].text
        assert "42" in text
        assert "200.00ms" in text

    async def test_error_response_raises_tool_error(self, mock_client, config):
        mock_client.monitoring.get_error_metrics.return_value = ApiError("timeout")
        handler = AppErrorsHandler(mock_client, config)
        with pytest.raises(ToolError, match="timeout"):
            await handler.handle({"app_name": "MyApp"}, "1234567")


class TestIncidentsHandler:
    async def test_no_incidents_returns_message(self, mock_client, config):
        mock_client.monitoring.get_recent_incidents.return_value = []
        handler = IncidentsHandler(mock_client, config)
        result = await handler.handle({"hours": 24}, "1234567")
        assert "No incidents" in result[0].text

    async def test_incidents_listed(self, mock_client, config):
        mock_client.monitoring.get_recent_incidents.return_value = [
            {"title": "CPU spike", "state": "ACTIVATED", "timestamp": "2026-01-01T00:00:00Z"},
        ]
        handler = IncidentsHandler(mock_client, config)
        result = await handler.handle({"hours": 24}, "1234567")
        assert "CPU spike" in result[0].text
        assert "ACTIVATED" in result[0].text


class TestInfrastructureHandler:
    async def test_no_hosts_returns_message(self, mock_client, config):
        mock_client.monitoring.get_infrastructure_hosts.return_value = []
        handler = InfrastructureHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No infrastructure" in result[0].text

    async def test_hosts_formatted(self, mock_client, config):
        mock_client.monitoring.get_infrastructure_hosts.return_value = [
            {"hostname": "web-01", "cpu_percent": 75.3, "memory_percent": 60.0, "disk_percent": 40.0}
        ]
        handler = InfrastructureHandler(mock_client, config)
        result = await handler.handle({"hours": 1}, "1234567")
        assert "web-01" in result[0].text
        assert "75.3%" in result[0].text


class TestAlertViolationsHandler:
    async def test_no_violations(self, mock_client, config):
        mock_client.monitoring.get_alert_violations.return_value = []
        handler = AlertViolationsHandler(mock_client, config)
        result = await handler.handle({"hours": 24}, "1234567")
        assert "No alert violations" in result[0].text

    async def test_violations_listed(self, mock_client, config):
        mock_client.monitoring.get_alert_violations.return_value = [
            {"title": "High CPU", "state": "ACTIVATED", "timestamp": "t1", "priority": "CRITICAL"}
        ]
        handler = AlertViolationsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "High CPU" in result[0].text
        assert "CRITICAL" in result[0].text


class TestDeploymentsHandler:
    async def test_no_deployments_with_app_name(self, mock_client, config):
        mock_client.monitoring.get_deployments.return_value = []
        handler = DeploymentsHandler(mock_client, config)
        result = await handler.handle({"app_name": "MyApp"}, "1234567")
        assert "No deployments" in result[0].text
        assert "MyApp" in result[0].text

    async def test_deployments_listed(self, mock_client, config):
        mock_client.monitoring.get_deployments.return_value = [
            {"appName": "MyApp", "timestamp": "2026-01-01", "revision": "abc123", "description": "v2 release"}
        ]
        handler = DeploymentsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "MyApp" in result[0].text
        assert "abc123" in result[0].text
        assert "v2 release" in result[0].text

    async def test_change_tracking_deployment_rendered(self, mock_client, config):
        mock_client.monitoring.get_deployments.return_value = [
            {
                "entity.name": "example-api_prod",
                "timestamp": 1700000000000,
                "version": "origin/prod-release",
                "user": "thrashy",
                "description": "prod release",
            }
        ]
        handler = DeploymentsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "example-api_prod" in result[0].text
        assert "origin/prod-release" in result[0].text
        assert "thrashy" in result[0].text
        assert "Unknown App" not in result[0].text
