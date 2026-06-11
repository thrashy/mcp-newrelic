"""Shared fixtures for the test suite."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from newrelic_mcp.config.newrelic_config import NewRelicConfig


@pytest.fixture
def config() -> NewRelicConfig:
    cfg = NewRelicConfig()
    cfg.api_key = "NRAK-test1234567890123456789012345678"
    cfg.account_id = "1234567"
    cfg.region = "US"
    cfg.timeout = 30
    return cfg


@pytest.fixture
def mock_client():
    """Mock client with composition-based sub-client attributes."""
    client = MagicMock()
    client.query_nrql = AsyncMock()
    client.aclose = AsyncMock()

    client.monitoring = MagicMock()
    client.monitoring.get_applications = AsyncMock()
    client.monitoring.get_performance_metrics = AsyncMock()
    client.monitoring.get_error_metrics = AsyncMock()
    client.monitoring.get_recent_incidents = AsyncMock()
    client.monitoring.get_infrastructure_hosts = AsyncMock()
    client.monitoring.get_alert_violations = AsyncMock()
    client.monitoring.get_deployments = AsyncMock()

    client.alerts = MagicMock()
    client.alerts.get_alert_policies = AsyncMock()
    client.alerts.get_alert_conditions = AsyncMock()
    client.alerts.get_destinations = AsyncMock()
    client.alerts.get_notification_channels = AsyncMock()
    client.alerts.get_workflows = AsyncMock()
    client.alerts.create_alert_policy = AsyncMock()
    client.alerts.update_alert_policy = AsyncMock()
    client.alerts.delete_alert_policy = AsyncMock()
    client.alerts.create_nrql_condition = AsyncMock()
    client.alerts.update_nrql_condition = AsyncMock()
    client.alerts.delete_nrql_condition = AsyncMock()
    client.alerts.create_notification_destination = AsyncMock()
    client.alerts.delete_notification_destination = AsyncMock()
    client.alerts.create_notification_channel = AsyncMock()
    client.alerts.create_workflow = AsyncMock()
    client.alerts.update_workflow = AsyncMock()
    client.alerts.delete_workflow = AsyncMock()
    client.alerts.delete_notification_channel = AsyncMock()
    client.alerts.create_muting_rule = AsyncMock()
    client.alerts.get_muting_rules = AsyncMock()
    client.alerts.update_muting_rule = AsyncMock()
    client.alerts.delete_muting_rule = AsyncMock()

    client.base = MagicMock()
    client.base.get_entity = AsyncMock()

    client.dashboards = MagicMock()
    client.dashboards.get_dashboards = AsyncMock()
    client.dashboards.create_dashboard = AsyncMock()
    client.dashboards.update_dashboard = AsyncMock()
    client.dashboards.add_widget_to_dashboard = AsyncMock()
    client.dashboards.get_dashboard_widgets = AsyncMock()
    client.dashboards.update_widget = AsyncMock()
    client.dashboards.delete_widget = AsyncMock()
    client.dashboards.delete_dashboard = AsyncMock()

    client.entities = MagicMock()
    client.entities.entity_search = AsyncMock()
    client.entities.get_entity_tags = AsyncMock()
    client.entities.add_tags_to_entity = AsyncMock()
    client.entities.replace_tags_on_entity = AsyncMock()
    client.entities.delete_tags_from_entity = AsyncMock()
    client.entities.delete_tag_values = AsyncMock()
    client.entities.list_service_levels = AsyncMock()
    client.entities.list_synthetic_monitors = AsyncMock()
    client.entities.get_synthetic_results = AsyncMock()

    return client
