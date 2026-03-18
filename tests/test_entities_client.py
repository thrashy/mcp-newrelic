"""Tests for EntitiesClient."""

from unittest.mock import AsyncMock, MagicMock

from newrelic_mcp.client.entities_client import EntitiesClient
from newrelic_mcp.types import ApiError, PaginatedResult


def _make_client() -> EntitiesClient:
    base = MagicMock()
    base.execute_graphql = AsyncMock()
    base.query_nrql = AsyncMock()
    base.paginate_graphql = AsyncMock()
    return EntitiesClient(base)


def _nrql_response(results: list) -> dict:
    return {"data": {"actor": {"account": {"nrql": {"results": results}}}}}


class TestEntitySearch:
    async def test_returns_entities(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"guid": "g1", "name": "App1"}], total_count=1
        )
        entities = await client.entity_search(name="App1")
        assert len(entities) == 1
        assert entities[0]["name"] == "App1"

    async def test_with_type_and_domain(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        entities = await client.entity_search(entity_type="APPLICATION", domain="APM")
        assert entities == []

    async def test_with_tags(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"guid": "g1", "name": "Tagged"}], total_count=1
        )
        entities = await client.entity_search(tags=[{"key": "env", "value": "prod"}])
        assert len(entities) == 1

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.entity_search(name="App1")
        assert isinstance(result, ApiError)

    async def test_limit_passed_to_paginate(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"guid": "g1", "name": "App1"}], total_count=1
        )
        await client.entity_search(name="App1", limit=5)
        call_kwargs = client._base.paginate_graphql.call_args
        assert call_kwargs.kwargs.get("limit") == 5

    async def test_limit_capped_at_200(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        await client.entity_search(name="App1", limit=500)
        call_kwargs = client._base.paginate_graphql.call_args
        assert call_kwargs.kwargs.get("limit") == 200

    async def test_minimal_output_omits_tags_in_query(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        await client.entity_search(name="App1", minimal_output=True)
        call_args = client._base.paginate_graphql.call_args
        query = call_args.args[0] if call_args.args else call_args[0][0]
        assert "tags" not in query


class TestGetEntityTags:
    async def test_returns_entity(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"actor": {"entity": {
                "name": "App1",
                "entityType": "APM_APPLICATION_ENTITY",
                "tags": [{"key": "env", "values": ["prod"]}],
            }}}
        }
        entity = await client.get_entity_tags("valid-guid")
        assert entity["name"] == "App1"
        assert len(entity["tags"]) == 1

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_entity_tags("bad-guid")
        assert isinstance(result, ApiError)


class TestAddTagsToEntity:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingAddTagsToEntity": {"errors": []}}
        }
        result = await client.add_tags_to_entity("g1", [{"key": "env", "value": "prod"}])
        assert result["success"] is True

    async def test_api_error(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingAddTagsToEntity": {"errors": [{"message": "invalid", "type": "INVALID"}]}}
        }
        result = await client.add_tags_to_entity("g1", [{"key": "env", "value": "prod"}])
        assert isinstance(result, ApiError)

    async def test_exception(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.add_tags_to_entity("g1", [{"key": "env", "value": "prod"}])
        assert isinstance(result, ApiError)


class TestDeleteTagsFromEntity:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingDeleteTagFromEntity": {"errors": []}}
        }
        result = await client.delete_tags_from_entity("g1", ["env"])
        assert result["success"] is True

    async def test_api_error(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingDeleteTagFromEntity": {"errors": [{"message": "not found", "type": "NOT_FOUND"}]}}
        }
        result = await client.delete_tags_from_entity("g1", ["env"])
        assert isinstance(result, ApiError)


class TestReplaceTagsOnEntity:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingReplaceTagsOnEntity": {"errors": []}}
        }
        result = await client.replace_tags_on_entity("g1", [{"key": "env", "value": "staging"}])
        assert result["success"] is True


class TestDeleteTagValues:
    async def test_success(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"taggingDeleteTagValuesFromEntity": {"errors": []}}
        }
        result = await client.delete_tag_values("g1", [{"key": "env", "value": "old"}])
        assert result["success"] is True


class TestListServiceLevels:
    async def test_returns_service_levels(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"guid": "sli1", "name": "Availability SLI", "tags": []}], total_count=1
        )
        client._base.query_nrql.return_value = _nrql_response([
            {"entity.guid": "sli1", "entity.name": "Availability SLI", "good": 99, "valid": 100, "bad": 1}
        ])
        slis = await client.list_service_levels("1234567")
        assert len(slis) == 1
        assert slis[0]["sliCompliance"] == 99.0

    async def test_empty_results(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(items=[], total_count=0)
        slis = await client.list_service_levels("1234567")
        assert slis == []

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.list_service_levels("1234567")
        assert isinstance(result, ApiError)


class TestListSyntheticMonitors:
    async def test_returns_monitors(self):
        client = _make_client()
        client._base.paginate_graphql.return_value = PaginatedResult(
            items=[{"guid": "m1", "name": "Health Check", "monitorType": "SIMPLE"}], total_count=1
        )
        monitors = await client.list_synthetic_monitors("1234567")
        assert len(monitors) == 1
        assert monitors[0]["monitorType"] == "SIMPLE"

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.paginate_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.list_synthetic_monitors("1234567")
        assert isinstance(result, ApiError)


class TestGetSyntheticResults:
    async def test_returns_entity_and_results(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"actor": {"entity": {
                "name": "Health Check",
                "monitorId": "mon-123",
                "monitorType": "SIMPLE",
                "period": 5,
                "monitorSummary": {"status": "SUCCESS", "successRate": 0.99},
            }}}
        }
        client._base.query_nrql.return_value = _nrql_response([
            {"result": "SUCCESS", "duration": 150, "locationLabel": "US-East"}
        ])
        result = await client.get_synthetic_results("1234567", "m1-guid", 24)
        assert result["entity"]["name"] == "Health Check"
        assert len(result["results"]) == 1

    async def test_no_monitor_id(self):
        client = _make_client()
        client._base.execute_graphql.return_value = {
            "data": {"actor": {"entity": {"name": "Monitor", "monitorId": None}}}
        }
        result = await client.get_synthetic_results("1234567", "m1-guid", 24)
        assert result["results"] == []

    async def test_exception_returns_error(self):
        client = _make_client()
        client._base.execute_graphql = AsyncMock(side_effect=ValueError("fail"))
        result = await client.get_synthetic_results("1234567", "m1-guid", 24)
        assert isinstance(result, ApiError)
