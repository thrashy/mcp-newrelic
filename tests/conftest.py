"""Shared fixtures for the test suite."""

from unittest.mock import create_autospec

import pytest

from newrelic_mcp.client.alerts_client import AlertsClient
from newrelic_mcp.client.base_client import BaseNewRelicClient
from newrelic_mcp.client.dashboards_client import DashboardsClient
from newrelic_mcp.client.entities_client import EntitiesClient
from newrelic_mcp.client.monitoring_client import MonitoringClient
from newrelic_mcp.client.unified_client import NewRelicClient
from newrelic_mcp.config import NewRelicConfig


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
    """Client mock autospec'd from the real classes.

    Sub-clients are assigned separately because they are instance attributes set in
    NewRelicClient.__init__, which autospec cannot discover from the class alone.
    """
    client = create_autospec(NewRelicClient, instance=True)
    client.base = create_autospec(BaseNewRelicClient, instance=True)
    client.monitoring = create_autospec(MonitoringClient, instance=True)
    client.alerts = create_autospec(AlertsClient, instance=True)
    client.dashboards = create_autospec(DashboardsClient, instance=True)
    client.entities = create_autospec(EntitiesClient, instance=True)
    return client
