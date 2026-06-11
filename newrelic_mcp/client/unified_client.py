"""
Unified New Relic client using composition.
"""

from typing import Any

from ..config import NewRelicConfig
from .alerts_client import AlertsClient
from .base_client import BaseNewRelicClient
from .dashboards_client import DashboardsClient
from .entities_client import EntitiesClient
from .monitoring_client import MonitoringClient


class NewRelicClient:
    """Unified New Relic client using composition instead of multiple inheritance.

    Sub-clients are accessed via attributes: monitoring, alerts, dashboards, entities.
    The query_nrql convenience method is exposed at the top level for direct NRQL queries.
    """

    def __init__(self, config: NewRelicConfig):
        self.base = BaseNewRelicClient(config)
        self.monitoring = MonitoringClient(self.base)
        self.alerts = AlertsClient(self.base)
        self.dashboards = DashboardsClient(self.base)
        self.entities = EntitiesClient(self.base)

    async def query_nrql(self, account_id: str, query: str) -> dict[str, Any]:
        """Convenience method for direct NRQL queries."""
        return await self.base.query_nrql(account_id, query)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self.base.aclose()
