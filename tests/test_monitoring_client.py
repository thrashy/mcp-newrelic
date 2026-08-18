"""Tests for MonitoringClient."""

from unittest.mock import AsyncMock, MagicMock

from newrelic_mcp.client.monitoring_client import MonitoringClient
from newrelic_mcp.types import ApiError


def _make_client() -> MonitoringClient:
    base = MagicMock()
    base.query_nrql = AsyncMock()
    return MonitoringClient(base)


def _nrql_response(results: list) -> dict:
    return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}


class TestGetApplications:
    async def test_returns_app_list(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"applications": ["App1", "App2"]}])
        apps = await client.get_applications("1234567")
        assert len(apps) == 2
        assert apps[0]["name"] == "App1"
        assert apps[1]["appName"] == "App2"

    async def test_empty_results(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([])
        apps = await client.get_applications("1234567")
        assert apps == []


class TestGetRecentIncidents:
    async def test_returns_incidents(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"title": "Incident 1"}])
        incidents = await client.get_recent_incidents("1234567", 24)
        assert len(incidents) == 1
        assert incidents[0]["title"] == "Incident 1"

    async def test_fallback_on_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(
            side_effect=[ValueError("NrAiIncident fail"), _nrql_response([{"title": "Alert fallback"}])]
        )
        incidents = await client.get_recent_incidents("1234567", 24)
        assert len(incidents) == 1
        assert incidents[0]["title"] == "Alert fallback"

    async def test_both_queries_fail(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_recent_incidents("1234567", 24)
        assert isinstance(result, ApiError)


class TestGetErrorMetrics:
    async def test_returns_metrics(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"error_count": 5, "avg_duration": 0.3}])
        result = await client.get_error_metrics("1234567", "MyApp", 1)
        assert result["error_count"] == 5

    async def test_fallback_query(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=[_nrql_response([]), _nrql_response([{"error_count": 2}])])
        result = await client.get_error_metrics("1234567", "MyApp", 1)
        assert result["error_count"] == 2

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("boom"))
        result = await client.get_error_metrics("1234567", "MyApp", 1)
        assert isinstance(result, ApiError)


class TestGetPerformanceMetrics:
    async def test_returns_metrics(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response(
            [{"avg_duration": 0.5, "p95_duration": 1.2, "throughput": 100}]
        )
        result = await client.get_performance_metrics("1234567", "MyApp", 1)
        assert result["avg_duration"] == 0.5

    async def test_no_data(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([])
        result = await client.get_performance_metrics("1234567", "MyApp", 1)
        assert result["avg_duration"] == "No data"

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("timeout"))
        result = await client.get_performance_metrics("1234567", "MyApp", 1)
        assert isinstance(result, ApiError)


class TestGetInfrastructureHosts:
    async def test_returns_hosts(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"hostname": "host1", "cpu_percent": 55.0}])
        hosts = await client.get_infrastructure_hosts("1234567", 1)
        assert len(hosts) == 1
        assert hosts[0]["hostname"] == "host1"

    async def test_fallback_on_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=[ValueError("fail"), _nrql_response([{"hosts": ["h1"]}])])
        hosts = await client.get_infrastructure_hosts("1234567", 1)
        assert len(hosts) == 1

    async def test_both_fail(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_infrastructure_hosts("1234567", 1)
        assert isinstance(result, ApiError)


class TestGetAlertViolations:
    async def test_returns_violations(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"title": "High CPU", "state": "ACTIVATED"}])
        violations = await client.get_alert_violations("1234567", 24)
        assert len(violations) == 1

    async def test_fallback_on_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(
            side_effect=[ValueError("fail"), _nrql_response([{"title": "Alert event"}])]
        )
        violations = await client.get_alert_violations("1234567", 24)
        assert len(violations) == 1

    async def test_both_fail(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_alert_violations("1234567", 24)
        assert isinstance(result, ApiError)


class TestGetDeployments:
    async def test_returns_deployments(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([{"appName": "MyApp", "revision": "abc123"}])
        deployments = await client.get_deployments("1234567", "MyApp", 168)
        assert len(deployments) == 1

    async def test_without_app_name(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([])
        deployments = await client.get_deployments("1234567", None, 168)
        assert deployments == []

    async def test_matches_change_tracking_entity_name(self):
        client = _make_client()
        client._base.query_nrql.return_value = _nrql_response([])
        await client.get_deployments("1234567", "MyApp", 168)
        nrql = client._base.query_nrql.await_args.args[1]
        assert "entity.name = 'MyApp'" in nrql
        assert "appName = 'MyApp'" in nrql

    async def test_fallback_on_error(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(
            side_effect=[ValueError("fail"), _nrql_response([{"transaction_count": 10}])]
        )
        deployments = await client.get_deployments("1234567", "MyApp", 168)
        assert len(deployments) == 1

    async def test_both_fail(self):
        client = _make_client()
        client._base.query_nrql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_deployments("1234567", None, 168)
        assert isinstance(result, ApiError)
