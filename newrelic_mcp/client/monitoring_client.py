"""
New Relic Monitoring API client.

Handles applications, performance metrics, error tracking, and infrastructure monitoring.
"""

import logging
from typing import Any

from ..types import ApiError
from ..utils.error_handling import API_ERRORS, handle_api_error
from ..utils.graphql_helpers import escape_nrql_string, extract_nrql_results
from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)


class MonitoringClient:
    """Client for New Relic monitoring APIs"""

    def __init__(self, base: BaseNewRelicClient):
        self._base = base

    async def _query_nrql_with_fallback(
        self, account_id: str, primary: str, fallback: str, operation: str
    ) -> list[dict[str, Any]] | ApiError:
        """Try a NRQL query; on failure, try a fallback query."""
        try:
            result = await self._base.query_nrql(account_id, primary)
            return extract_nrql_results(result) or []
        except API_ERRORS as e:
            logger.warning("%s primary query failed, trying fallback: %s", operation, e)
            try:
                result = await self._base.query_nrql(account_id, fallback)
                return extract_nrql_results(result) or []
            except API_ERRORS as e2:
                return handle_api_error(operation, e2)

    async def get_applications(self, account_id: str) -> list[dict[str, Any]] | ApiError:
        """Get list of applications"""
        query = "SELECT uniques(appName) as 'applications' FROM Transaction SINCE 1 day ago LIMIT 100"
        try:
            result = await self._base.query_nrql(account_id, query)
            nrql_results = extract_nrql_results(result)
            if not nrql_results:
                logger.warning("No applications found in NRQL results")
                return []

            apps = []
            for item in nrql_results:
                if "applications" in item and item["applications"]:
                    for app_name in item["applications"]:
                        apps.append({"name": app_name, "appName": app_name})

            return apps
        except API_ERRORS as e:
            return handle_api_error("get applications", e)

    async def get_recent_incidents(self, account_id: str, hours: int = 24) -> list[dict[str, Any]] | ApiError:
        """Get recent incidents"""
        return await self._query_nrql_with_fallback(
            account_id,
            f"SELECT * FROM NrAiIncident SINCE {hours} hours ago LIMIT 50",
            f"SELECT * FROM Alert SINCE {hours} hours ago LIMIT 50",
            "get incidents",
        )

    async def get_error_metrics(self, account_id: str, app_name: str, hours: int = 1) -> dict[str, Any] | ApiError:
        """Get error metrics for an application"""
        safe_name = escape_nrql_string(app_name)
        query = (
            f"SELECT count(*) as error_count, average(duration) as avg_duration "
            f"FROM TransactionError WHERE appName = '{safe_name}' SINCE {hours} hours ago"
        )
        try:
            result = await self._base.query_nrql(account_id, query)
            nrql_results = extract_nrql_results(result)

            if nrql_results:
                return nrql_results[0]

            # Fallback query
            query = (
                f"SELECT count(*) as error_count FROM Transaction "
                f"WHERE appName = '{safe_name}' AND error IS TRUE SINCE {hours} hours ago"
            )
            result = await self._base.query_nrql(account_id, query)
            nrql_results = extract_nrql_results(result)
            return nrql_results[0] if nrql_results else {"error_count": 0, "avg_duration": None}

        except API_ERRORS as e:
            return handle_api_error("get error metrics", e)

    async def get_performance_metrics(
        self, account_id: str, app_name: str, hours: int = 1
    ) -> dict[str, Any] | ApiError:
        """Get performance metrics for an application"""
        safe_name = escape_nrql_string(app_name)
        query = (
            f"SELECT average(duration) as avg_duration, percentile(duration, 95) as p95_duration, "
            f"rate(count(*), 1 minute) as throughput FROM Transaction "
            f"WHERE appName = '{safe_name}' SINCE {hours} hours ago"
        )
        try:
            result = await self._base.query_nrql(account_id, query)
            nrql_results = extract_nrql_results(result)

            if nrql_results:
                return nrql_results[0]

            logger.warning("No performance data found for app: %s", app_name)
            return {"avg_duration": "No data", "p95_duration": "No data", "throughput": "No data"}

        except API_ERRORS as e:
            return handle_api_error("get performance metrics", e)

    async def get_infrastructure_hosts(self, account_id: str, hours: int = 1) -> list[dict[str, Any]] | ApiError:
        """Get infrastructure hosts and their metrics"""
        return await self._query_nrql_with_fallback(
            account_id,
            (
                f"SELECT latest(cpuPercent) as cpu_percent, latest(memoryUsedPercent) as memory_percent, "
                f"latest(diskUsedPercent) as disk_percent FROM SystemSample "
                f"FACET hostname SINCE {hours} hours ago LIMIT 50"
            ),
            f"SELECT uniques(hostname) as hosts FROM SystemSample SINCE {hours} hours ago LIMIT 50",
            "get infrastructure hosts",
        )

    async def get_alert_violations(self, account_id: str, hours: int = 24) -> list[dict[str, Any]] | ApiError:
        """Get recent alert violations"""
        return await self._query_nrql_with_fallback(
            account_id,
            (f"SELECT * FROM NrAiIncident WHERE state IN ('ACTIVATED', 'CLOSED') SINCE {hours} hours ago LIMIT 50"),
            f"SELECT * FROM AlertEvent SINCE {hours} hours ago LIMIT 50",
            "get alert violations",
        )

    async def get_deployments(
        self, account_id: str, app_name: str | None = None, hours: int = 168
    ) -> list[dict[str, Any]] | ApiError:
        """Get deployment markers and their impact"""
        if app_name:
            safe_name = escape_nrql_string(app_name)
            primary = (
                f"SELECT * FROM Deployment "
                f"WHERE entity.name = '{safe_name}' OR appName = '{safe_name}' "
                f"SINCE {hours} hours ago LIMIT 20"
            )
            fallback = (
                f"SELECT count(*) as transaction_count, average(duration) as avg_duration "
                f"FROM Transaction WHERE appName = '{safe_name}' "
                f"FACET timestamp SINCE {hours} hours ago LIMIT 20"
            )
        else:
            primary = f"SELECT * FROM Deployment SINCE {hours} hours ago LIMIT 50"
            fallback = (
                f"SELECT count(*) as transaction_count, average(duration) as avg_duration "
                f"FROM Transaction FACET appName SINCE {hours} hours ago LIMIT 20"
            )

        return await self._query_nrql_with_fallback(account_id, primary, fallback, "get deployments")
