"""Tests for entity tool handler strategies."""

from unittest.mock import AsyncMock

import pytest

from newrelic_mcp.handlers.strategies.entities import (
    AddTagsHandler,
    CreateServiceLevelHandler,
    DecodeEntityGuidHandler,
    DeleteServiceLevelHandler,
    DeleteTagsHandler,
    DeleteTagValuesHandler,
    EntitySearchHandler,
    GetEntityHandler,
    GetEntityTagsHandler,
    GetServiceLevelHandler,
    GetSyntheticResultsHandler,
    ListServiceLevelsHandler,
    ListSyntheticMonitorsHandler,
    ReplaceTagsHandler,
    UpdateServiceLevelHandler,
)
from newrelic_mcp.types import ApiError, DecodedEntityGuid, ToolError


class TestEntitySearchHandler:
    async def test_found_entities(self, mock_client, config):
        mock_client.entities.entity_search.return_value = [
            {"name": "my-service", "guid": "MTIzNDU2Nzg5MA==", "domain": "APM", "type": "APPLICATION"}
        ]
        handler = EntitySearchHandler(mock_client, config)
        result = await handler.handle({"name": "my-service"}, "1234567")

        text = result[0].text
        assert "my-service" in text
        assert "MTIzNDU2Nzg5MA==" in text
        assert "APM" in text

    async def test_no_entities(self, mock_client, config):
        mock_client.entities.entity_search.return_value = []
        handler = EntitySearchHandler(mock_client, config)
        result = await handler.handle({"name": "nonexistent"}, "1234567")

        assert "No entities found" in result[0].text

    async def test_entity_with_tags(self, mock_client, config):
        mock_client.entities.entity_search.return_value = [
            {
                "name": "svc",
                "guid": "MTIzNDU2Nzg5MA==",
                "domain": "APM",
                "type": "APPLICATION",
                "tags": [{"key": "env", "values": ["prod"]}],
            }
        ]
        handler = EntitySearchHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "env=prod" in result[0].text

    async def test_entity_with_alert_severity(self, mock_client, config):
        mock_client.entities.entity_search.return_value = [
            {"name": "svc", "guid": "MTIzNDU2Nzg5MA==", "domain": "APM", "type": "APP", "alertSeverity": "CRITICAL"}
        ]
        handler = EntitySearchHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "CRITICAL" in result[0].text

    async def test_error_from_client(self, mock_client, config):
        mock_client.entities.entity_search.return_value = ApiError("search failed")
        handler = EntitySearchHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "Error" in result[0].text


class TestGetEntityTagsHandler:
    async def test_entity_with_tags(self, mock_client, config):
        mock_client.entities.get_entity_tags.return_value = {
            "name": "my-service",
            "entityType": "APM_APPLICATION_ENTITY",
            "tags": [
                {"key": "environment", "values": ["production"]},
                {"key": "team", "values": ["platform"]},
            ],
        }
        handler = GetEntityTagsHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")

        text = result[0].text
        assert "environment" in text
        assert "production" in text
        assert "team" in text

    async def test_entity_not_found(self, mock_client, config):
        mock_client.entities.get_entity_tags.return_value = None
        handler = GetEntityTagsHandler(mock_client, config)
        result = await handler.handle({"guid": "YmFkR3VpZFRlc3Q="}, "1234567")

        assert "Error" in result[0].text

    async def test_entity_no_tags(self, mock_client, config):
        mock_client.entities.get_entity_tags.return_value = {"name": "svc", "entityType": "APM", "tags": []}
        handler = GetEntityTagsHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")

        assert "no tags" in result[0].text

    async def test_api_error(self, mock_client, config):
        mock_client.entities.get_entity_tags.return_value = ApiError("failed")
        handler = GetEntityTagsHandler(mock_client, config)
        with pytest.raises(ToolError, match="failed"):
            await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")


class TestAddTagsHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.add_tags_to_entity.return_value = {"success": True}
        handler = AddTagsHandler(mock_client, config)
        result = await handler.handle(
            {"guid": "MTIzNDU2Nzg5MA==", "tags": [{"key": "env", "value": "prod"}]}, "1234567"
        )

        assert "added successfully" in result[0].text
        assert "env=prod" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.entities.add_tags_to_entity.return_value = ApiError("not found")
        handler = AddTagsHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"guid": "YmFkR3VpZFRlc3Q=", "tags": [{"key": "k", "value": "v"}]}, "1234567")


class TestDeleteTagsHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.delete_tags_from_entity.return_value = {"success": True}
        handler = DeleteTagsHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA==", "tag_keys": ["env", "team"]}, "1234567")

        assert "deleted" in result[0].text.lower()
        assert "env" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.entities.delete_tags_from_entity.return_value = ApiError("permission denied")
        handler = DeleteTagsHandler(mock_client, config)
        with pytest.raises(ToolError, match="permission denied"):
            await handler.handle({"guid": "MTIzNDU2Nzg5MA==", "tag_keys": ["env"]}, "1234567")


class TestListServiceLevelsHandler:
    async def test_found_indicators(self, mock_client, config):
        mock_client.entities.list_service_levels.return_value = [
            {
                "name": "Availability SLI",
                "guid": "sli1",
                "alertSeverity": "WARNING",
                "sliCompliance": 99.5,
                "tags": [
                    {"key": "sli.indicator", "values": ["availability"]},
                    {"key": "nr.sli.objectiveTarget", "values": ["99.9"]},
                ],
            }
        ]
        handler = ListServiceLevelsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        text = result[0].text
        assert "Availability SLI" in text
        assert "99.5%" in text
        assert "99.9" in text

    async def test_no_indicators(self, mock_client, config):
        mock_client.entities.list_service_levels.return_value = []
        handler = ListServiceLevelsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "No service level indicators" in result[0].text

    async def test_error_from_client(self, mock_client, config):
        mock_client.entities.list_service_levels.return_value = ApiError("failed")
        handler = ListServiceLevelsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "Error" in result[0].text


class TestGetServiceLevelHandler:
    async def test_returns_definitions(self, mock_client, config):
        mock_client.entities.get_service_level = AsyncMock(
            return_value=[{"id": "1", "name": "Availability", "events": {}}]
        )
        handler = GetServiceLevelHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")
        assert "Availability" in result[0].text

    async def test_no_indicators(self, mock_client, config):
        mock_client.entities.get_service_level = AsyncMock(return_value=[])
        handler = GetServiceLevelHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")
        assert "No service level indicators" in result[0].text


class TestCreateServiceLevelHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.create_service_level = AsyncMock(return_value={"id": "1", "name": "My SLI"})
        handler = CreateServiceLevelHandler(mock_client, config)
        result = await handler.handle(
            {
                "entity_guid": "MTIzNDU2Nzg5MA==",
                "name": "My SLI",
                "events": {"validEvents": {"from": "Metric"}},
                "objectives": [],
            },
            "1234567",
        )
        assert "My SLI" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.entities.create_service_level = AsyncMock(return_value=ApiError("boom"))
        handler = CreateServiceLevelHandler(mock_client, config)
        with pytest.raises(ToolError):
            await handler.handle(
                {"entity_guid": "MTIzNDU2Nzg5MA==", "name": "x", "events": {}, "objectives": []}, "1234567"
            )


class TestUpdateServiceLevelHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.update_service_level = AsyncMock(return_value={"id": "1", "name": "My SLI"})
        handler = UpdateServiceLevelHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA==", "description": "new"}, "1234567")
        assert "My SLI" in result[0].text


class TestDeleteServiceLevelHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.delete_service_level = AsyncMock(return_value={"id": "1", "name": "My SLI"})
        handler = DeleteServiceLevelHandler(mock_client, config)
        result = await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")
        assert "deleted" in result[0].text.lower()

    async def test_permission_error(self, mock_client, config):
        mock_client.entities.delete_service_level = AsyncMock(return_value=ApiError("Access denied"))
        handler = DeleteServiceLevelHandler(mock_client, config)
        with pytest.raises(ToolError):
            await handler.handle({"guid": "MTIzNDU2Nzg5MA=="}, "1234567")


class TestListSyntheticMonitorsHandler:
    async def test_found_monitors(self, mock_client, config):
        mock_client.entities.list_synthetic_monitors.return_value = [
            {
                "name": "Homepage Check",
                "guid": "syn1",
                "monitorType": "SIMPLE",
                "period": 15,
                "alertSeverity": "NOT_ALERTING",
                "monitorSummary": {
                    "status": "SUCCESS",
                    "successRate": 1.0,
                    "locationsFailing": 0,
                    "locationsRunning": 3,
                },
            }
        ]
        handler = ListSyntheticMonitorsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        text = result[0].text
        assert "Homepage Check" in text
        assert "100.0%" in text
        assert "3/3" in text

    async def test_no_monitors(self, mock_client, config):
        mock_client.entities.list_synthetic_monitors.return_value = []
        handler = ListSyntheticMonitorsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "No synthetic monitors" in result[0].text

    async def test_error_from_client(self, mock_client, config):
        mock_client.entities.list_synthetic_monitors.return_value = ApiError("failed")
        handler = ListSyntheticMonitorsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")

        assert "Error" in result[0].text


class TestReplaceTagsHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.replace_tags_on_entity.return_value = {"success": True}
        handler = ReplaceTagsHandler(mock_client, config)
        result = await handler.handle(
            {"guid": "MTIzNDU2Nzg5MA==", "tags": [{"key": "env", "value": "prod"}, {"key": "team", "value": "sre"}]},
            "1234567",
        )

        text = result[0].text
        assert "replaced" in text.lower()
        assert "env=prod" in text
        assert "team=sre" in text

    async def test_error(self, mock_client, config):
        mock_client.entities.replace_tags_on_entity.return_value = ApiError("permission denied")
        handler = ReplaceTagsHandler(mock_client, config)
        with pytest.raises(ToolError, match="permission denied"):
            await handler.handle({"guid": "YmFkR3VpZFRlc3Q=", "tags": [{"key": "k", "value": "v"}]}, "1234567")


class TestDeleteTagValuesHandler:
    async def test_success(self, mock_client, config):
        mock_client.entities.delete_tag_values.return_value = {"success": True}
        handler = DeleteTagValuesHandler(mock_client, config)
        result = await handler.handle(
            {"guid": "MTIzNDU2Nzg5MA==", "tag_values": [{"key": "env", "value": "staging"}]}, "1234567"
        )

        text = result[0].text
        assert "deleted" in text.lower()
        assert "env=staging" in text

    async def test_error(self, mock_client, config):
        mock_client.entities.delete_tag_values.return_value = ApiError("not found")
        handler = DeleteTagValuesHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"guid": "YmFkR3VpZFRlc3Q=", "tag_values": [{"key": "k", "value": "v"}]}, "1234567")


class TestGetSyntheticResultsHandler:
    async def test_with_results(self, mock_client, config):
        mock_client.entities.get_synthetic_results.return_value = {
            "entity": {
                "name": "API Check",
                "monitorType": "SCRIPT_API",
                "monitorSummary": {
                    "status": "SUCCESS",
                    "successRate": 0.95,
                    "locationsFailing": 1,
                    "locationsRunning": 5,
                },
            },
            "results": [
                {"result": "SUCCESS", "duration": 150, "locationLabel": "US-East"},
                {"result": "FAILED", "duration": 5000, "locationLabel": "EU-West", "error": "Timeout"},
            ],
        }
        handler = GetSyntheticResultsHandler(mock_client, config)
        result = await handler.handle({"monitor_guid": "c3luTW9uaXRvcjE="}, "1234567")

        text = result[0].text
        assert "API Check" in text
        assert "95.0%" in text
        assert "1 passed" in text
        assert "1 failed" in text
        assert "Timeout" in text

    async def test_entity_not_found(self, mock_client, config):
        mock_client.entities.get_synthetic_results.return_value = {"entity": {}, "results": []}
        handler = GetSyntheticResultsHandler(mock_client, config)
        result = await handler.handle({"monitor_guid": "YmFkR3VpZFRlc3Q="}, "1234567")

        assert "Error" in result[0].text

    async def test_no_results(self, mock_client, config):
        mock_client.entities.get_synthetic_results.return_value = {
            "entity": {"name": "Check", "monitorType": "SIMPLE", "monitorSummary": {}},
            "results": [],
        }
        handler = GetSyntheticResultsHandler(mock_client, config)
        result = await handler.handle({"monitor_guid": "c3luTW9uaXRvcjE=", "hours": 1}, "1234567")

        assert "No check results" in result[0].text

    async def test_api_error(self, mock_client, config):
        mock_client.entities.get_synthetic_results.return_value = ApiError("failed")
        handler = GetSyntheticResultsHandler(mock_client, config)
        with pytest.raises(ToolError, match="failed"):
            await handler.handle({"monitor_guid": "c3luTW9uaXRvcjE="}, "1234567")


class TestDecodeEntityGuidHandler:
    async def test_success(self, mock_client, config):
        mock_client.base.decode_entity_guid.return_value = DecodedEntityGuid(
            account_id=9999999, domain="EXT", entity_type="KEY_TRANSACTION", domain_id="123456789"
        )
        handler = DecodeEntityGuidHandler(mock_client, config)
        result = await handler.handle({"guid": "someguid1234"}, "")
        text = result[0].text
        assert "9999999" in text
        assert "EXT" in text
        assert "KEY_TRANSACTION" in text
        assert "123456789" in text

    async def test_invalid_guid_returns_error_text(self, mock_client, config):
        mock_client.base.decode_entity_guid.side_effect = ValueError("not valid base64")
        handler = DecodeEntityGuidHandler(mock_client, config)
        result = await handler.handle({"guid": "bad"}, "")
        assert result[0].text.startswith("Error")
        assert "not valid base64" in result[0].text


class TestGetEntityHandler:
    async def test_success(self, mock_client, config):
        mock_client.base.get_entity.return_value = {
            "guid": "entguid123456",
            "name": "My App",
            "domain": "APM",
            "type": "APPLICATION",
            "account": {"id": 1234567, "name": "My Account"},
            "alertSeverity": "NOT_ALERTING",
            "permalink": "https://one.newrelic.com/redirect",
            "language": "java",
            "tags": [{"key": "env", "values": ["prod"]}],
        }
        handler = GetEntityHandler(mock_client, config)
        result = await handler.handle({"guid": "entguid123456"}, "")
        text = result[0].text
        assert "My App" in text
        assert "APM/APPLICATION" in text
        assert "My Account" in text
        assert "java" in text
        assert "env: prod" in text

    async def test_error_propagated(self, mock_client, config):
        mock_client.base.get_entity.return_value = ApiError("Entity not found")
        handler = GetEntityHandler(mock_client, config)
        with pytest.raises(ToolError, match="Entity not found"):
            await handler.handle({"guid": "entguid123456"}, "")
