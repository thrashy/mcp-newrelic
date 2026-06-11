"""Tests for AlertsClient."""

from unittest.mock import AsyncMock, MagicMock

from newrelic_mcp.client.alerts_client import AlertsClient
from newrelic_mcp.client.base_client import BaseNewRelicClient
from newrelic_mcp.types import ApiError, PaginatedResult


def _make_client() -> AlertsClient:
    base = MagicMock()
    base.execute_graphql = AsyncMock()
    base.paginate_graphql = AsyncMock()
    base.extract_mutation_result = BaseNewRelicClient.extract_mutation_result.__get__(base)
    base.execute_mutation = BaseNewRelicClient.execute_mutation.__get__(base)
    return AlertsClient(base)


class TestCreateAlertPolicy:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"alertsPolicyCreate": {"id": "p1", "name": "Test", "incidentPreference": "PER_POLICY"}}
        }
        result = await client.create_alert_policy("1234567", "Test")
        assert result["id"] == "p1"

    async def test_empty_response(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsPolicyCreate": {}}}
        result = await client.create_alert_policy("1234567", "Test")
        assert isinstance(result, ApiError)

    async def test_exception(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.create_alert_policy("1234567", "Test")
        assert isinstance(result, ApiError)


class TestGetAlertPolicies:
    async def test_success(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"id": "p1", "name": "Prod"}], total_count=1
        )
        result = await client.get_alert_policies("1234567")
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.items[0]["name"] == "Prod"

    async def test_exception(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_alert_policies("1234567")
        assert isinstance(result, ApiError)


class TestGetAlertConditions:
    async def test_with_policy_filter(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"id": "c1", "name": "High CPU"}], total_count=1
        )
        result = await client.get_alert_conditions("1234567", policy_id="p1")
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1

    async def test_exception(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_alert_conditions("1234567")
        assert isinstance(result, ApiError)


class TestDeleteAlertPolicy:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsPolicyDelete": {"id": "p1", "name": "Test"}}}
        result = await client.delete_alert_policy("1234567", "p1")
        assert result["success"] is True

    async def test_empty_response(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsPolicyDelete": {}}}
        result = await client.delete_alert_policy("1234567", "p1")
        assert isinstance(result, ApiError)


class TestUpdateAlertPolicy:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"alertsPolicyUpdate": {"id": "p1", "name": "Updated", "incidentPreference": "PER_CONDITION"}}
        }
        result = await client.update_alert_policy("1234567", "p1", name="Updated")
        assert result["name"] == "Updated"

    async def test_exception(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.update_alert_policy("1234567", "p1")
        assert isinstance(result, ApiError)


class TestCreateNRQLCondition:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {
                "alertsNrqlConditionStaticCreate": {
                    "id": "c1",
                    "name": "High Errors",
                    "enabled": True,
                    "nrql": {"query": "SELECT count(*) FROM TransactionError"},
                    "terms": [{"operator": "ABOVE", "threshold": 5}],
                }
            }
        }
        result = await client.create_nrql_condition(
            "1234567", "p1", "High Errors", "SELECT count(*) FROM TransactionError", 5.0
        )
        assert result["id"] == "c1"

    async def test_empty_response(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsNrqlConditionStaticCreate": {}}}
        result = await client.create_nrql_condition("1234567", "p1", "Test", "SELECT 1", 1.0)
        assert isinstance(result, ApiError)


class TestDeleteNRQLCondition:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsConditionDelete": {"id": "c1"}}}
        result = await client.delete_nrql_condition("1234567", "c1")
        assert result["success"] is True

    async def test_empty_response(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {"data": {"alertsConditionDelete": {}}}
        result = await client.delete_nrql_condition("1234567", "c1")
        assert isinstance(result, ApiError)


class TestGetDestinations:
    async def test_success(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"id": "d1", "name": "Slack", "type": "SLACK"}], total_count=1
        )
        result = await client.get_destinations("1234567")
        query, variables = client._base.paginate_graphql.call_args.args[:2]
        assert "$cursor: String" in query and "destinations(cursor: $cursor)" in query
        assert variables == {"accountId": 1234567}
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1


class TestGetWorkflows:
    async def test_success(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"id": "w1", "name": "Prod Workflow"}], total_count=1
        )
        result = await client.get_workflows("1234567")
        query, _variables = client._base.paginate_graphql.call_args.args[:2]
        assert "workflows(cursor: $cursor)" in query
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 1
        assert result.items[0]["name"] == "Prod Workflow"


class TestDeleteWorkflow:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"aiWorkflowsDeleteWorkflow": {"id": "wf1", "errors": None}}
        }
        result = await client.delete_workflow("1234567", "wf1")
        assert result["success"] is True

    async def test_with_errors(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"aiWorkflowsDeleteWorkflow": {"id": "wf1", "errors": [{"description": "not found"}]}}
        }
        result = await client.delete_workflow("1234567", "wf1")
        assert isinstance(result, ApiError)
