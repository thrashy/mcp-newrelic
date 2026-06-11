"""Tests for ResourceHandlers."""

import pytest

from newrelic_mcp.handlers.resource_handlers import ResourceHandlers
from newrelic_mcp.types import ApiError, PaginatedResult


class TestGetResources:
    def test_returns_six_resources(self, mock_client, config):
        handler = ResourceHandlers(mock_client, config)
        resources = handler.get_resources()
        assert len(resources) == 6

    def test_resource_uris(self, mock_client, config):
        handler = ResourceHandlers(mock_client, config)
        uris = [str(r.uri) for r in handler.get_resources()]
        assert "newrelic://applications" in uris
        assert "newrelic://incidents/recent" in uris
        assert "newrelic://dashboards" in uris
        assert "newrelic://alerts/policies" in uris
        assert "newrelic://alerts/conditions" in uris
        assert "newrelic://alerts/workflows" in uris


class TestReadResource:
    async def test_applications(self, mock_client, config):
        mock_client.monitoring.get_applications.return_value = [{"name": "MyApp", "appId": "123"}]
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://applications")

        assert "MyApp" in result
        assert "1 applications found" in result

    async def test_incidents(self, mock_client, config):
        mock_client.monitoring.get_recent_incidents.return_value = [
            {"title": "CPU Spike", "state": "ACTIVATED", "timestamp": "2026-01-01"}
        ]
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://incidents/recent")

        assert "CPU Spike" in result
        assert "ACTIVATED" in result

    async def test_dashboards(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(
            items=[{"name": "Prod Dash", "guid": "g1", "createdAt": "2026-01-01", "permalink": "https://nr.com"}]
        )
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://dashboards")

        assert "Prod Dash" in result
        assert "g1" in result

    async def test_dashboards_error(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = ApiError("no access")
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://dashboards")

        assert "Error" in result

    async def test_dashboards_empty(self, mock_client, config):
        mock_client.dashboards.get_dashboards.return_value = PaginatedResult(items=[])
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://dashboards")

        assert "No dashboards found" in result

    async def test_alert_policies(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(
            items=[{"name": "CPU Policy", "id": "p1", "incidentPreference": "PER_POLICY", "createdAt": "2026"}],
            total_count=1,
        )
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://alerts/policies")

        assert "CPU Policy" in result

    async def test_alert_policies_empty(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[], total_count=0)
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://alerts/policies")

        assert "No alert policies" in result

    async def test_alert_conditions(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(
            items=[
                {
                    "name": "High Error Rate",
                    "id": "c1",
                    "policyId": "p1",
                    "enabled": True,
                    "nrql": {"query": "SELECT count(*) FROM Error"},
                    "terms": [{"threshold": 5, "operator": "ABOVE", "priority": "CRITICAL", "thresholdDuration": 300}],
                }
            ],
            total_count=1,
        )
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://alerts/conditions")

        assert "High Error Rate" in result
        assert "above 5" in result
        assert "Policy p1" in result

    async def test_alert_workflows(self, mock_client, config):
        mock_client.alerts.get_workflows.return_value = PaginatedResult(
            items=[
                {
                    "name": "Slack Alert",
                    "id": "w1",
                    "enabled": True,
                    "destinationConfigurations": [{"name": "#alerts", "type": "SLACK"}],
                    "issuesFilter": {"name": "critical-filter"},
                }
            ],
            total_count=1,
        )
        handler = ResourceHandlers(mock_client, config)
        result = await handler.read_resource("newrelic://alerts/workflows")

        assert "Slack Alert" in result
        assert "#alerts" in result

    async def test_unknown_uri_raises(self, mock_client, config):
        handler = ResourceHandlers(mock_client, config)
        with pytest.raises(ValueError, match="Unknown resource URI"):
            await handler.read_resource("newrelic://unknown")

    async def test_no_client_raises(self, config):
        handler = ResourceHandlers(None, config)
        with pytest.raises(ValueError, match="not configured"):
            await handler.read_resource("newrelic://applications")
