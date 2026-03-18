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
        self._base = BaseNewRelicClient(config)
        self.base = self._base
        self.monitoring = MonitoringClient(self._base)
        self.alerts = AlertsClient(self._base)
        self.dashboards = DashboardsClient(self._base)
        self.entities = EntitiesClient(self._base)

    async def query_nrql(self, account_id: str, query: str) -> dict[str, Any]:
        """Convenience method for direct NRQL queries."""
        return await self._base.query_nrql(account_id, query)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._base.aclose()
