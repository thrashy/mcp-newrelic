"""Tests for alert tool handler strategies."""

import pytest

from newrelic_mcp.handlers.strategies.alerts import (
    CreateAlertPolicyHandler,
    CreateMutingRuleHandler,
    CreateNotificationChannelHandler,
    CreateNotificationDestinationHandler,
    CreateNRQLConditionHandler,
    CreateWorkflowHandler,
    DeleteAlertPolicyHandler,
    DeleteMutingRuleHandler,
    DeleteNotificationChannelHandler,
    DeleteNotificationDestinationHandler,
    DeleteNRQLConditionHandler,
    DeleteWorkflowHandler,
    ListAlertConditionsHandler,
    ListAlertPoliciesHandler,
    ListMutingRulesHandler,
    ListNotificationChannelsHandler,
    ListNotificationDestinationsHandler,
    ListWorkflowsHandler,
    UpdateAlertPolicyHandler,
    UpdateMutingRuleHandler,
    UpdateNRQLConditionHandler,
    UpdateWorkflowHandler,
)
from newrelic_mcp.types import ApiError, PaginatedResult, ToolError


class TestCreateAlertPolicyHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_alert_policy.return_value = {"success": True, "id": "policy-1", "name": "My Policy"}
        handler = CreateAlertPolicyHandler(mock_client, config)
        result = await handler.handle({"name": "My Policy"}, "1234567")
        assert "My Policy" in result[0].text
        assert "policy-1" in result[0].text

    async def test_error_propagated(self, mock_client, config):
        mock_client.alerts.create_alert_policy.return_value = ApiError("name taken")
        handler = CreateAlertPolicyHandler(mock_client, config)
        with pytest.raises(ToolError, match="name taken"):
            await handler.handle({"name": "My Policy"}, "1234567")

    async def test_default_incident_preference(self, mock_client, config):
        mock_client.alerts.create_alert_policy.return_value = {"id": "p1"}
        handler = CreateAlertPolicyHandler(mock_client, config)
        await handler.handle({"name": "Policy"}, "1234567")
        mock_client.alerts.create_alert_policy.assert_called_once_with("1234567", "Policy", "PER_POLICY")


class TestCreateNRQLConditionHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_nrql_condition.return_value = {"id": "cond-1"}
        handler = CreateNRQLConditionHandler(mock_client, config)
        result = await handler.handle(
            {
                "policy_id": "p1",
                "name": "High Error Rate",
                "nrql_query": "SELECT count(*) FROM TransactionError",
                "threshold": 5.0,
            },
            "1234567",
        )
        assert "cond-1" in result[0].text

    async def test_priority_passed_through_unmapped(self, mock_client, config):
        mock_client.alerts.create_nrql_condition.return_value = {"id": "c1"}
        handler = CreateNRQLConditionHandler(mock_client, config)
        await handler.handle(
            {
                "policy_id": "p1",
                "name": "cond",
                "nrql_query": "SELECT count(*) FROM Transaction",
                "threshold": 1.0,
                "priority": "WARNING",
            },
            "1234567",
        )
        call_args = mock_client.alerts.create_nrql_condition.call_args[0]
        assert call_args[7] == "WARNING"


class TestListAlertPoliciesHandler:
    async def test_no_policies(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(items=[])
        handler = ListAlertPoliciesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No alert policies" in result[0].text

    async def test_policies_listed(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = PaginatedResult(
            items=[{"name": "Prod Policy", "id": "p1", "incidentPreference": "PER_POLICY"}]
        )
        handler = ListAlertPoliciesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "Prod Policy" in result[0].text
        assert "p1" in result[0].text

    async def test_error_from_client(self, mock_client, config):
        mock_client.alerts.get_alert_policies.return_value = ApiError("unauthorized")
        handler = ListAlertPoliciesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert result[0].text.startswith("Error")


class TestListAlertConditionsHandler:
    async def test_no_conditions(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(items=[])
        handler = ListAlertConditionsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No alert conditions" in result[0].text

    async def test_conditions_with_policy_filter(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(
            items=[{"name": "Cond A", "id": "c1", "enabled": True, "policyName": "My Policy"}]
        )
        handler = ListAlertConditionsHandler(mock_client, config)
        result = await handler.handle({"policy_id": "p1"}, "1234567")
        assert "Cond A" in result[0].text
        mock_client.alerts.get_alert_conditions.assert_called_once_with("1234567", "p1", name=None, query=None)

    async def test_calls_get_alert_conditions_without_policy_id(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(items=[])
        handler = ListAlertConditionsHandler(mock_client, config)
        await handler.handle({}, "1234567")
        mock_client.alerts.get_alert_conditions.assert_called_once_with("1234567", None, name=None, query=None)


class TestListNotificationDestinationsHandler:
    async def test_no_destinations(self, mock_client, config):
        mock_client.alerts.get_destinations.return_value = PaginatedResult(items=[])
        handler = ListNotificationDestinationsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No notification destinations" in result[0].text

    async def test_destinations_listed(self, mock_client, config):
        mock_client.alerts.get_destinations.return_value = PaginatedResult(
            items=[{"name": "Slack", "id": "d1", "type": "SLACK"}]
        )
        handler = ListNotificationDestinationsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "Slack" in result[0].text
        assert "SLACK" in result[0].text


class TestListNotificationChannelsHandler:
    async def test_channels_listed(self, mock_client, config):
        mock_client.alerts.get_notification_channels.return_value = PaginatedResult(
            items=[{"name": "Alert Chan", "id": "ch1", "type": "SLACK", "destinationId": "d1"}]
        )
        handler = ListNotificationChannelsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "Alert Chan" in result[0].text


class TestListWorkflowsHandler:
    async def test_no_workflows(self, mock_client, config):
        mock_client.alerts.get_workflows.return_value = PaginatedResult(items=[])
        handler = ListWorkflowsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No workflows" in result[0].text

    async def test_workflows_listed(self, mock_client, config):
        mock_client.alerts.get_workflows.return_value = PaginatedResult(items=[{"name": "Prod Alerts", "id": "wf1"}])
        handler = ListWorkflowsHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "Prod Alerts" in result[0].text
        assert "wf1" in result[0].text


class TestCreateWorkflowHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_workflow.return_value = {"id": "wf-new", "success": True}
        handler = CreateWorkflowHandler(mock_client, config)
        result = await handler.handle({"name": "My Workflow", "channel_ids": ["ch1", "ch2"]}, "1234567")
        assert "wf-new" in result[0].text
        assert "2 notification channel" in result[0].text


class TestDeleteAlertPolicyHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_alert_policy.return_value = {"success": True, "id": "123"}
        handler = DeleteAlertPolicyHandler(mock_client, config)
        result = await handler.handle({"policy_id": "123"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_alert_policy.return_value = ApiError("not found")
        handler = DeleteAlertPolicyHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"policy_id": "999"}, "1234567")


class TestUpdateAlertPolicyHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.update_alert_policy.return_value = {"success": True, "name": "Updated Policy"}
        handler = UpdateAlertPolicyHandler(mock_client, config)
        result = await handler.handle({"policy_id": "123", "name": "Updated Policy"}, "1234567")
        assert "updated successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.update_alert_policy.return_value = ApiError("bad input")
        handler = UpdateAlertPolicyHandler(mock_client, config)
        with pytest.raises(ToolError, match="bad input"):
            await handler.handle({"policy_id": "123"}, "1234567")


class TestDeleteNRQLConditionHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_nrql_condition.return_value = {"success": True, "id": "456"}
        handler = DeleteNRQLConditionHandler(mock_client, config)
        result = await handler.handle({"condition_id": "456"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_nrql_condition.return_value = ApiError("not found")
        handler = DeleteNRQLConditionHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"condition_id": "999"}, "1234567")


class TestUpdateNRQLConditionHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.update_nrql_condition.return_value = {"success": True, "id": "456"}
        handler = UpdateNRQLConditionHandler(mock_client, config)
        result = await handler.handle({"condition_id": "456", "name": "New Name"}, "1234567")
        assert "updated successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.update_nrql_condition.return_value = ApiError("invalid")
        handler = UpdateNRQLConditionHandler(mock_client, config)
        with pytest.raises(ToolError, match="invalid"):
            await handler.handle({"condition_id": "456"}, "1234567")


class TestDeleteNotificationDestinationHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_notification_destination.return_value = {"success": True, "id": "d1"}
        handler = DeleteNotificationDestinationHandler(mock_client, config)
        result = await handler.handle({"destination_id": "d1"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_notification_destination.return_value = ApiError("in use")
        handler = DeleteNotificationDestinationHandler(mock_client, config)
        with pytest.raises(ToolError, match="in use"):
            await handler.handle({"destination_id": "d1"}, "1234567")


class TestDeleteWorkflowHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_workflow.return_value = {"success": True, "id": "wf1"}
        handler = DeleteWorkflowHandler(mock_client, config)
        result = await handler.handle({"workflow_id": "wf1"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_workflow.return_value = ApiError("not found")
        handler = DeleteWorkflowHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"workflow_id": "wf1"}, "1234567")

    async def test_default_delete_channels(self, mock_client, config):
        mock_client.alerts.delete_workflow.return_value = {"success": True, "id": "wf1"}
        handler = DeleteWorkflowHandler(mock_client, config)
        await handler.handle({"workflow_id": "wf1"}, "1234567")
        mock_client.alerts.delete_workflow.assert_called_once_with("1234567", "wf1", True)


class TestListAlertConditionsSearchFilters:
    async def test_name_filter_passed(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(items=[], total_count=0)
        handler = ListAlertConditionsHandler(mock_client, config)
        await handler.handle({"name": "CPU"}, "1234567")
        mock_client.alerts.get_alert_conditions.assert_called_once_with("1234567", None, name="CPU", query=None)

    async def test_query_filter_passed(self, mock_client, config):
        mock_client.alerts.get_alert_conditions.return_value = PaginatedResult(items=[], total_count=0)
        handler = ListAlertConditionsHandler(mock_client, config)
        await handler.handle({"query": "Transaction"}, "1234567")
        mock_client.alerts.get_alert_conditions.assert_called_once_with("1234567", None, name=None, query="Transaction")


class TestCreateMutingRuleHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_muting_rule.return_value = {
            "success": True,
            "id": "mr1",
            "schedule": {"repeat": "WEEKLY", "timeZone": "UTC", "startTime": "T1", "endTime": "T2"},
        }
        handler = CreateMutingRuleHandler(mock_client, config)
        conditions = [{"attribute": "policyName", "operator": "EQUALS", "values": ["Prod"]}]
        result = await handler.handle({"name": "Maintenance", "conditions": conditions}, "1234567")
        assert "Maintenance" in result[0].text
        assert "mr1" in result[0].text
        assert "WEEKLY" in result[0].text
        mock_client.alerts.create_muting_rule.assert_called_once_with(
            "1234567", "Maintenance", None, True, "AND", conditions, None
        )

    async def test_error_propagated(self, mock_client, config):
        mock_client.alerts.create_muting_rule.return_value = ApiError("bad schedule")
        handler = CreateMutingRuleHandler(mock_client, config)
        with pytest.raises(ToolError, match="bad schedule"):
            await handler.handle({"name": "Maintenance", "conditions": []}, "1234567")


class TestListMutingRulesHandler:
    async def test_no_rules(self, mock_client, config):
        mock_client.alerts.get_muting_rules.return_value = PaginatedResult(items=[])
        handler = ListMutingRulesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert "No muting rules" in result[0].text

    async def test_rules_listed(self, mock_client, config):
        mock_client.alerts.get_muting_rules.return_value = PaginatedResult(
            items=[
                {
                    "id": "mr1",
                    "name": "Weekend Mute",
                    "enabled": True,
                    "description": "Mute on weekends",
                    "condition": {
                        "operator": "AND",
                        "conditions": [{"attribute": "policyName", "operator": "EQUALS", "values": ["Prod"]}],
                    },
                    "schedule": {
                        "repeat": "WEEKLY",
                        "timeZone": "UTC",
                        "startTime": "T1",
                        "endTime": "T2",
                        "weeklyRepeatDays": ["SATURDAY", "SUNDAY"],
                    },
                }
            ]
        )
        handler = ListMutingRulesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        text = result[0].text
        assert "Weekend Mute" in text
        assert "mr1" in text
        assert "policyName EQUALS ['Prod']" in text
        assert "SATURDAY" in text

    async def test_error_from_client(self, mock_client, config):
        mock_client.alerts.get_muting_rules.return_value = ApiError("unauthorized")
        handler = ListMutingRulesHandler(mock_client, config)
        result = await handler.handle({}, "1234567")
        assert result[0].text.startswith("Error")


class TestDeleteMutingRuleHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_muting_rule.return_value = {"success": True, "id": "mr1"}
        handler = DeleteMutingRuleHandler(mock_client, config)
        result = await handler.handle({"rule_id": "mr1"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_muting_rule.return_value = ApiError("not found")
        handler = DeleteMutingRuleHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"rule_id": "mr1"}, "1234567")


class TestUpdateMutingRuleHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.update_muting_rule.return_value = {"success": True, "id": "mr1"}
        handler = UpdateMutingRuleHandler(mock_client, config)
        result = await handler.handle({"rule_id": "mr1", "name": "Renamed"}, "1234567")
        assert "mr1" in result[0].text
        assert "updated successfully" in result[0].text
        mock_client.alerts.update_muting_rule.assert_called_once_with(
            "1234567",
            "mr1",
            name="Renamed",
            description=None,
            enabled=None,
            condition_operator=None,
            conditions=None,
            schedule=None,
        )

    async def test_error(self, mock_client, config):
        mock_client.alerts.update_muting_rule.return_value = ApiError("not found")
        handler = UpdateMutingRuleHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"rule_id": "mr1", "enabled": False}, "1234567")


class TestUpdateWorkflowHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.update_workflow.return_value = {"success": True, "id": "wf1"}
        handler = UpdateWorkflowHandler(mock_client, config)
        result = await handler.handle({"workflow_id": "wf1", "name": "Renamed", "enabled": False}, "1234567")
        assert "wf1" in result[0].text
        assert "updated successfully" in result[0].text
        mock_client.alerts.update_workflow.assert_called_once_with(
            "1234567",
            "wf1",
            name="Renamed",
            enabled=False,
            destination_configurations=None,
            issues_filter=None,
        )

    async def test_error(self, mock_client, config):
        mock_client.alerts.update_workflow.return_value = ApiError("not found")
        handler = UpdateWorkflowHandler(mock_client, config)
        with pytest.raises(ToolError, match="not found"):
            await handler.handle({"workflow_id": "wf1", "name": "X"}, "1234567")


class TestDeleteNotificationChannelHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.delete_notification_channel.return_value = {"success": True, "id": "ch1"}
        handler = DeleteNotificationChannelHandler(mock_client, config)
        result = await handler.handle({"channel_id": "ch1"}, "1234567")
        assert "deleted successfully" in result[0].text

    async def test_error(self, mock_client, config):
        mock_client.alerts.delete_notification_channel.return_value = ApiError("in use")
        handler = DeleteNotificationChannelHandler(mock_client, config)
        with pytest.raises(ToolError, match="in use"):
            await handler.handle({"channel_id": "ch1"}, "1234567")


class TestCreateNotificationDestinationHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_notification_destination.return_value = {"success": True, "id": "d1"}
        handler = CreateNotificationDestinationHandler(mock_client, config)
        result = await handler.handle(
            {"name": "Team Email", "type": "EMAIL", "properties": {"email": "team@example.com"}}, "1234567"
        )
        assert "Team Email" in result[0].text
        assert "d1" in result[0].text
        mock_client.alerts.create_notification_destination.assert_called_once_with(
            "1234567", "Team Email", "EMAIL", {"email": "team@example.com"}
        )

    async def test_error_propagated(self, mock_client, config):
        mock_client.alerts.create_notification_destination.return_value = ApiError("invalid properties")
        handler = CreateNotificationDestinationHandler(mock_client, config)
        with pytest.raises(ToolError, match="invalid properties"):
            await handler.handle({"name": "X", "type": "EMAIL", "properties": {}}, "1234567")


class TestCreateNotificationChannelHandler:
    async def test_success(self, mock_client, config):
        mock_client.alerts.create_notification_channel.return_value = {"success": True, "id": "ch1"}
        handler = CreateNotificationChannelHandler(mock_client, config)
        result = await handler.handle({"name": "Alert Chan", "destination_id": "d1", "type": "EMAIL"}, "1234567")
        assert "Alert Chan" in result[0].text
        assert "ch1" in result[0].text
        mock_client.alerts.create_notification_channel.assert_called_once_with(
            "1234567", "Alert Chan", "d1", "EMAIL", "IINT", {}
        )

    async def test_error_propagated(self, mock_client, config):
        mock_client.alerts.create_notification_channel.return_value = ApiError("destination missing")
        handler = CreateNotificationChannelHandler(mock_client, config)
        with pytest.raises(ToolError, match="destination missing"):
            await handler.handle({"name": "X", "destination_id": "d1", "type": "EMAIL"}, "1234567")


class TestUpdateNRQLConditionAggregationWindowPassthrough:
    async def test_aggregation_window_passed(self, mock_client, config):
        mock_client.alerts.update_nrql_condition.return_value = {"success": True, "id": "c1"}
        handler = UpdateNRQLConditionHandler(mock_client, config)
        await handler.handle({"condition_id": "c1", "aggregation_window": 120}, "1234567")
        assert mock_client.alerts.update_nrql_condition.call_args.kwargs["aggregation_window"] == 120
