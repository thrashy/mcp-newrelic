"""
New Relic Alerts API client.

Handles alert policies, conditions, destinations, channels, and workflows.
"""

import logging
from typing import Any

from ..types import ApiError, PaginatedResult
from ..utils.error_handling import API_ERRORS, handle_api_error, handle_graphql_notification_errors
from ..utils.graphql_helpers import extract_nested_data
from ..utils.response_formatters import format_create_response
from .base_client import BaseNewRelicClient

logger = logging.getLogger(__name__)


class AlertsClient:
    """Client for New Relic alerts APIs"""

    def __init__(self, base: BaseNewRelicClient):
        self._base = base

    async def _query_entities(
        self, query: str, account_id: str, data_path: list[str], items_key: str = "entities"
    ) -> PaginatedResult:
        """Execute a GraphQL query and wrap results as PaginatedResult."""
        result = await self._base.execute_graphql(query, {"accountId": int(account_id)})
        data = extract_nested_data(result, data_path)
        return PaginatedResult(
            items=data.get(items_key, []),
            total_count=data.get("totalCount", 0),
        )

    async def create_alert_policy(
        self, account_id: str, name: str, incident_preference: str = "PER_POLICY"
    ) -> dict[str, Any] | ApiError:
        """Create a new alert policy"""
        mutation = """
        mutation($accountId: Int!, $policy: AlertsPolicyInput!) {
          alertsPolicyCreate(accountId: $accountId, policy: $policy) {
            id
            name
            incidentPreference
          }
        }
        """

        policy_input = {"name": name, "incidentPreference": incident_preference}

        try:
            result = await self._base.execute_graphql(mutation, {"accountId": int(account_id), "policy": policy_input})

            policy_result = self._base._extract_mutation_result(
                result, "alertsPolicyCreate", error_message="Failed to create alert policy"
            )
            if isinstance(policy_result, ApiError):
                return policy_result

            return format_create_response(
                policy_result,
                policy_id="id",
                name="name",
                incident_preference="incidentPreference",
            )

        except API_ERRORS as e:
            return handle_api_error("create alert policy", e)

    async def create_nrql_condition(
        self,
        account_id: str,
        policy_id: str,
        name: str,
        nrql_query: str,
        threshold: float,
        threshold_duration: int = 300,
        threshold_operator: str = "ABOVE",
        priority: str = "CRITICAL",
        aggregation_window: int = 60,
        description: str | None = None,
    ) -> dict[str, Any] | ApiError:
        """Create a NRQL alert condition"""
        mutation = """
        mutation($accountId: Int!, $policyId: ID!, $condition: AlertsNrqlConditionStaticInput!) {
          alertsNrqlConditionStaticCreate(accountId: $accountId, policyId: $policyId, condition: $condition) {
            id
            name
            enabled
            nrql {
              query
            }
            signal {
              aggregationWindow
              evaluationOffset
            }
            terms {
              operator
              priority
              threshold
              thresholdDuration
              thresholdOccurrences
            }
          }
        }
        """

        condition_config: dict[str, Any] = {
            "name": name,
            "enabled": True,
            "nrql": {"query": nrql_query},
            "signal": {"aggregationWindow": aggregation_window, "evaluationOffset": 3},
            "terms": [
                {
                    "operator": threshold_operator,
                    "priority": priority,
                    "threshold": threshold,
                    "thresholdDuration": threshold_duration,
                    "thresholdOccurrences": "AT_LEAST_ONCE",
                }
            ],
        }

        if description:
            condition_config["description"] = description

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "policyId": policy_id, "condition": condition_config}
            )

            condition_result = self._base._extract_mutation_result(
                result, "alertsNrqlConditionStaticCreate", error_message="Failed to create NRQL condition"
            )
            if isinstance(condition_result, ApiError):
                return condition_result

            return format_create_response(
                condition_result,
                condition_id="id",
                name="name",
                enabled="enabled",
                query=["nrql", "query"],
                terms="terms",
            )

        except API_ERRORS as e:
            return handle_api_error("create NRQL condition", e)

    async def create_notification_destination(
        self, account_id: str, name: str, destination_type: str, properties: dict[str, Any]
    ) -> dict[str, Any] | ApiError:
        """Create a notification destination"""
        mutation = """
        mutation($accountId: Int!, $destination: AiNotificationsDestinationInput!) {
          aiNotificationsCreateDestination(accountId: $accountId, destination: $destination) {
            destination {
              id
              name
              type
              properties {
                key
                value
              }
            }
            errors {
              ... on AiNotificationsResponseError {
                description
                type
              }
            }
          }
        }
        """

        destination_config = {
            "name": name,
            "type": destination_type,
            "properties": [{"key": k, "value": v} for k, v in properties.items()],
        }

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "destination": destination_config}
            )

            create_result = result.get("data", {}).get("aiNotificationsCreateDestination", {})
            error_response = handle_graphql_notification_errors(create_result, "Destination creation")
            if error_response:
                return error_response

            destination = create_result.get("destination", {})
            return format_create_response(
                destination,
                destination_id="id",
                name="name",
                type="type",
                properties="properties",
            )

        except API_ERRORS as e:
            return handle_api_error("create notification destination", e)

    async def create_notification_channel(
        self,
        account_id: str,
        name: str,
        destination_id: str,
        channel_type: str,
        product: str = "IINT",
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any] | ApiError:
        """Create a notification channel"""
        mutation = """
        mutation($accountId: Int!, $channel: AiNotificationsChannelInput!) {
          aiNotificationsCreateChannel(accountId: $accountId, channel: $channel) {
            channel {
              id
              name
              type
              destinationId
              product
              properties {
                key
                value
              }
            }
            errors {
              ... on AiNotificationsResponseError {
                description
                type
              }
            }
          }
        }
        """

        channel_config = {
            "name": name,
            "type": channel_type,
            "destinationId": destination_id,
            "product": product,
            "properties": [{"key": k, "value": v} for k, v in (properties or {}).items()],
        }

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "channel": channel_config}
            )

            create_result = result.get("data", {}).get("aiNotificationsCreateChannel", {})
            error_response = handle_graphql_notification_errors(create_result, "Channel creation")
            if error_response:
                return error_response

            channel = create_result.get("channel", {})
            return format_create_response(
                channel,
                channel_id="id",
                name="name",
                type="type",
                destination_id="destinationId",
                product="product",
                properties="properties",
            )

        except API_ERRORS as e:
            return handle_api_error("create notification channel", e)

    async def create_workflow(
        self,
        account_id: str,
        name: str,
        channel_ids: list[str],
        enabled: bool = True,
        filter_name: str = "Filter-name",
        filter_predicates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | ApiError:
        """Create a workflow to connect alerts to notification channels"""
        mutation = """
        mutation($accountId: Int!, $createWorkflowData: AiWorkflowsCreateWorkflowInput!) {
          aiWorkflowsCreateWorkflow(accountId: $accountId, createWorkflowData: $createWorkflowData) {
            workflow {
              id
              name
              enrichments {
                configurations {
                  ... on AiWorkflowsNrqlConfiguration {
                    query
                  }
                }
                id
                name
                type
              }
              destinationConfigurations {
                channelId
                name
                type
              }
              issuesFilter {
                name
                predicates {
                  attribute
                  operator
                  values
                }
                type
              }
            }
            errors {
              description
              type
            }
          }
        }
        """

        workflow_config: dict[str, Any] = {
            "name": name,
            "workflowEnabled": enabled,
            "destinationsEnabled": True,
            "enrichmentsEnabled": True,
            "mutingRulesHandling": "NOTIFY_ALL_ISSUES",
            "destinationConfigurations": [{"channelId": cid} for cid in channel_ids],
            "issuesFilter": {"name": filter_name, "type": "FILTER", "predicates": filter_predicates or []},
        }

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "createWorkflowData": workflow_config}
            )

            create_result = self._base._extract_mutation_result(
                result, "aiWorkflowsCreateWorkflow", error_message="Workflow creation failed"
            )
            if isinstance(create_result, ApiError):
                return create_result

            workflow = create_result.get("workflow", {})
            return format_create_response(
                workflow,
                workflow_id="id",
                name="name",
                destination_configurations="destinationConfigurations",
                issues_filter="issuesFilter",
                enrichments="enrichments",
            )

        except API_ERRORS as e:
            return handle_api_error("create workflow", e)

    async def get_alert_policies(self, account_id: str) -> PaginatedResult | ApiError:
        """Get list of alert policies with cursor-based pagination"""
        query = """
        query($accountId: Int!, $cursor: String) {
          actor {
            account(id: $accountId) {
              alerts {
                policiesSearch(cursor: $cursor) {
                  policies {
                    id
                    name
                    incidentPreference
                  }
                  nextCursor
                  totalCount
                }
              }
            }
          }
        }
        """

        try:
            return await self._base.paginate_graphql(
                query,
                {"accountId": int(account_id)},
                ["data", "actor", "account", "alerts", "policiesSearch"],
                "policies",
            )
        except API_ERRORS as e:
            return handle_api_error("get alert policies", e)

    async def get_alert_conditions(
        self, account_id: str, policy_id: str | None = None, name: str | None = None, query: str | None = None
    ) -> PaginatedResult | ApiError:
        """Get alert conditions with cursor-based pagination, optionally filtered"""
        query_str = """
        query($accountId: Int!, $searchCriteria: AlertsNrqlConditionsSearchCriteriaInput, $cursor: String) {
          actor {
            account(id: $accountId) {
              alerts {
                nrqlConditionsSearch(searchCriteria: $searchCriteria, cursor: $cursor) {
                  nrqlConditions {
                    id
                    name
                    description
                    enabled
                    type
                    policyId
                    nrql {
                      query
                    }
                    terms {
                      operator
                      priority
                      threshold
                      thresholdDuration
                      thresholdOccurrences
                    }
                    signal {
                      aggregationWindow
                      evaluationOffset
                      fillOption
                    }
                    createdAt
                    updatedAt
                  }
                  nextCursor
                  totalCount
                }
              }
            }
          }
        }
        """

        search_criteria: dict[str, Any] = {}
        if policy_id:
            search_criteria["policyId"] = policy_id
        if name:
            search_criteria["name"] = name
        if query:
            search_criteria["queryLike"] = query

        try:
            return await self._base.paginate_graphql(
                query_str,
                {"accountId": int(account_id), "searchCriteria": search_criteria},
                ["data", "actor", "account", "alerts", "nrqlConditionsSearch"],
                "nrqlConditions",
            )
        except API_ERRORS as e:
            return handle_api_error("get alert conditions", e)

    async def get_destinations(self, account_id: str) -> PaginatedResult | ApiError:
        """Get notification destinations"""
        query = """
        query($accountId: Int!) {
          actor {
            account(id: $accountId) {
              aiNotifications {
                destinations {
                  entities {
                    id
                    name
                    type
                    properties {
                      key
                      value
                    }
                    createdAt
                    updatedAt
                  }
                  nextCursor
                  totalCount
                }
              }
            }
          }
        }
        """

        try:
            return await self._query_entities(
                query, account_id, ["data", "actor", "account", "aiNotifications", "destinations"]
            )
        except API_ERRORS as e:
            return handle_api_error("get destinations", e)

    async def get_notification_channels(self, account_id: str) -> PaginatedResult | ApiError:
        """Get notification channels"""
        query = """
        query($accountId: Int!) {
          actor {
            account(id: $accountId) {
              aiNotifications {
                channels {
                  entities {
                    id
                    name
                    type
                    destinationId
                    product
                    properties {
                      key
                      value
                    }
                    createdAt
                    updatedAt
                  }
                  nextCursor
                  totalCount
                }
              }
            }
          }
        }
        """

        try:
            return await self._query_entities(
                query, account_id, ["data", "actor", "account", "aiNotifications", "channels"]
            )
        except API_ERRORS as e:
            return handle_api_error("get notification channels", e)

    async def get_workflows(self, account_id: str) -> PaginatedResult | ApiError:
        """Get workflows"""
        query = """
        query($accountId: Int!) {
          actor {
            account(id: $accountId) {
              aiWorkflows {
                workflows {
                  entities {
                    id
                    name
                    destinationConfigurations {
                      channelId
                      name
                      type
                    }
                    issuesFilter {
                      name
                      type
                      predicates {
                        attribute
                        operator
                        values
                      }
                    }
                    enrichments {
                      id
                      name
                      type
                    }
                    createdAt
                    updatedAt
                  }
                  nextCursor
                  totalCount
                }
              }
            }
          }
        }
        """

        try:
            return await self._query_entities(
                query, account_id, ["data", "actor", "account", "aiWorkflows", "workflows"]
            )
        except API_ERRORS as e:
            return handle_api_error("get workflows", e)

    async def delete_alert_policy(self, account_id: str, policy_id: str) -> dict[str, Any] | ApiError:
        """Delete an alert policy"""
        mutation = """
        mutation($accountId: Int!, $id: ID!) {
          alertsPolicyDelete(accountId: $accountId, id: $id) {
            id
          }
        }
        """

        try:
            result = await self._base.execute_graphql(mutation, {"accountId": int(account_id), "id": policy_id})

            delete_result = self._base._extract_mutation_result(
                result, "alertsPolicyDelete", error_message="Failed to delete alert policy"
            )
            if isinstance(delete_result, ApiError):
                return delete_result

            return {
                "success": True,
                "id": delete_result.get("id"),
                "message": f"Alert policy '{policy_id}' deleted successfully",
            }

        except API_ERRORS as e:
            return handle_api_error("delete alert policy", e)

    async def update_alert_policy(
        self,
        account_id: str,
        policy_id: str,
        name: str | None = None,
        incident_preference: str | None = None,
    ) -> dict[str, Any] | ApiError:
        """Update an existing alert policy"""
        mutation = """
        mutation($accountId: Int!, $id: ID!, $policy: AlertsPolicyUpdateInput!) {
          alertsPolicyUpdate(accountId: $accountId, id: $id, policy: $policy) {
            id
            name
            incidentPreference
          }
        }
        """

        policy_input: dict[str, Any] = {}
        if name is not None:
            policy_input["name"] = name
        if incident_preference is not None:
            policy_input["incidentPreference"] = incident_preference

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "id": policy_id, "policy": policy_input}
            )

            policy_result = self._base._extract_mutation_result(
                result, "alertsPolicyUpdate", error_message="Failed to update alert policy"
            )
            if isinstance(policy_result, ApiError):
                return policy_result

            return format_create_response(
                policy_result,
                policy_id="id",
                name="name",
                incident_preference="incidentPreference",
            )

        except API_ERRORS as e:
            return handle_api_error("update alert policy", e)

    async def delete_nrql_condition(self, account_id: str, condition_id: str) -> dict[str, Any] | ApiError:
        """Delete an alert condition"""
        mutation = """
        mutation($accountId: Int!, $id: ID!) {
          alertsConditionDelete(accountId: $accountId, id: $id) {
            id
          }
        }
        """

        try:
            result = await self._base.execute_graphql(mutation, {"accountId": int(account_id), "id": condition_id})

            delete_result = self._base._extract_mutation_result(
                result, "alertsConditionDelete", error_message="Failed to delete alert condition"
            )
            if isinstance(delete_result, ApiError):
                return delete_result

            return {
                "success": True,
                "id": delete_result.get("id"),
                "message": "Alert condition deleted successfully",
            }

        except API_ERRORS as e:
            return handle_api_error("delete alert condition", e)

    async def _get_nrql_condition(self, account_id: str, condition_id: str) -> dict[str, Any] | ApiError:
        """Fetch a single NRQL condition by ID to read its current state."""
        query_str = """
        query($accountId: Int!, $conditionId: ID!) {
          actor {
            account(id: $accountId) {
              alerts {
                nrqlCondition(id: $conditionId) {
                  ... on AlertsNrqlStaticCondition {
                    id
                    name
                    description
                    enabled
                    nrql { query }
                    terms { operator priority threshold thresholdDuration thresholdOccurrences }
                  }
                }
              }
            }
          }
        }
        """
        try:
            result = await self._base.execute_graphql(
                query_str, {"accountId": int(account_id), "conditionId": condition_id}
            )
            condition: dict[str, Any] = extract_nested_data(
                result, ["data", "actor", "account", "alerts", "nrqlCondition"]
            )
            if not condition:
                return ApiError(f"Condition '{condition_id}' not found")
            return condition
        except API_ERRORS as e:
            return handle_api_error("fetch NRQL condition", e)

    async def update_nrql_condition(
        self,
        account_id: str,
        condition_id: str,
        name: str | None = None,
        nrql_query: str | None = None,
        enabled: bool | None = None,
        threshold: float | None = None,
        threshold_operator: str | None = None,
        threshold_duration: int | None = None,
        description: str | None = None,
        priority: str | None = None,
    ) -> dict[str, Any] | ApiError:
        """Update an existing NRQL alert condition (fetch-then-merge for partial updates)."""
        mutation = """
        mutation($accountId: Int!, $id: ID!, $condition: AlertsNrqlConditionUpdateStaticInput!) {
          alertsNrqlConditionStaticUpdate(accountId: $accountId, id: $id, condition: $condition) {
            id
            name
            enabled
            nrql {
              query
            }
            terms {
              operator
              priority
              threshold
              thresholdDuration
              thresholdOccurrences
            }
          }
        }
        """

        # Fetch current condition to merge with user-provided fields
        needs_term_update = any(v is not None for v in (threshold, threshold_operator, threshold_duration, priority))
        if needs_term_update:
            current = await self._get_nrql_condition(account_id, condition_id)
            if isinstance(current, ApiError):
                return current
            existing_terms = current.get("terms", [{}])
            existing_term = existing_terms[0] if existing_terms else {}
        else:
            existing_term = {}

        condition_config: dict[str, Any] = {}
        if name is not None:
            condition_config["name"] = name
        if nrql_query is not None:
            condition_config["nrql"] = {"query": nrql_query}
        if enabled is not None:
            condition_config["enabled"] = enabled
        if description is not None:
            condition_config["description"] = description
        if needs_term_update:
            condition_config["terms"] = [
                {
                    "threshold": threshold if threshold is not None else existing_term.get("threshold", 0),
                    "operator": threshold_operator or existing_term.get("operator", "ABOVE"),
                    "thresholdDuration": threshold_duration or existing_term.get("thresholdDuration", 300),
                    "thresholdOccurrences": existing_term.get("thresholdOccurrences", "AT_LEAST_ONCE"),
                    "priority": priority or existing_term.get("priority", "CRITICAL"),
                }
            ]

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "id": condition_id, "condition": condition_config}
            )

            condition_result = self._base._extract_mutation_result(
                result, "alertsNrqlConditionStaticUpdate", error_message="Failed to update NRQL condition"
            )
            if isinstance(condition_result, ApiError):
                return condition_result

            return format_create_response(
                condition_result,
                condition_id="id",
                name="name",
                enabled="enabled",
                query=["nrql", "query"],
                terms="terms",
            )

        except API_ERRORS as e:
            return handle_api_error("update NRQL condition", e)

    async def delete_notification_destination(self, account_id: str, destination_id: str) -> dict[str, Any] | ApiError:
        """Delete a notification destination"""
        mutation = """
        mutation($accountId: Int!, $destinationId: ID!) {
          aiNotificationsDeleteDestination(accountId: $accountId, destinationId: $destinationId) {
            ids
            error {
              description
              type
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "destinationId": destination_id}
            )

            delete_result = result.get("data", {}).get("aiNotificationsDeleteDestination", {})
            error = delete_result.get("error")
            if error:
                error_msg = error.get("description", error.get("type", "Unknown error"))
                return ApiError(f"Destination deletion failed: {error_msg}")

            return {
                "success": True,
                "id": destination_id,
                "message": "Notification destination deleted successfully",
            }

        except API_ERRORS as e:
            return handle_api_error("delete notification destination", e)

    async def create_muting_rule(
        self,
        account_id: str,
        name: str,
        description: str | None = None,
        enabled: bool = True,
        condition_operator: str = "AND",
        conditions: list[dict[str, Any]] | None = None,
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any] | ApiError:
        """Create a muting rule to suppress alert notifications"""
        mutation = """
        mutation($accountId: Int!, $rule: AlertsMutingRuleInput!) {
          alertsMutingRuleCreate(accountId: $accountId, rule: $rule) {
            id
            name
            description
            enabled
            condition {
              operator
              conditions {
                attribute
                operator
                values
              }
            }
            schedule {
              startTime
              endTime
              timeZone
              repeat
              endRepeat
              weeklyRepeatDays
            }
          }
        }
        """

        rule_input: dict[str, Any] = {
            "name": name,
            "enabled": enabled,
            "condition": {
                "operator": condition_operator,
                "conditions": conditions or [],
            },
        }

        if description:
            rule_input["description"] = description
        if schedule:
            rule_input["schedule"] = schedule

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "rule": rule_input}
            )

            rule_result = self._base._extract_mutation_result(
                result, "alertsMutingRuleCreate", error_message="Failed to create muting rule"
            )
            if isinstance(rule_result, ApiError):
                return rule_result

            return format_create_response(
                rule_result,
                rule_id="id",
                name="name",
                enabled="enabled",
                schedule="schedule",
            )

        except API_ERRORS as e:
            return handle_api_error("create muting rule", e)

    async def get_muting_rules(self, account_id: str) -> PaginatedResult | ApiError:
        """Get all muting rules for the account"""
        query = """
        query($accountId: Int!) {
          actor {
            account(id: $accountId) {
              alerts {
                mutingRules {
                  id
                  name
                  description
                  enabled
                  condition {
                    operator
                    conditions {
                      attribute
                      operator
                      values
                    }
                  }
                  schedule {
                    startTime
                    endTime
                    timeZone
                    repeat
                    endRepeat
                    weeklyRepeatDays
                  }
                  createdAt
                  updatedAt
                }
              }
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(query, {"accountId": int(account_id)})
            data = extract_nested_data(result, ["data", "actor", "account", "alerts"])
            rules = data.get("mutingRules", [])
            return PaginatedResult(items=rules, total_count=len(rules))
        except API_ERRORS as e:
            return handle_api_error("get muting rules", e)

    async def delete_muting_rule(self, account_id: str, rule_id: str) -> dict[str, Any] | ApiError:
        """Delete a muting rule"""
        mutation = """
        mutation($accountId: Int!, $id: ID!) {
          alertsMutingRuleDelete(accountId: $accountId, id: $id) {
            id
          }
        }
        """

        try:
            result = await self._base.execute_graphql(mutation, {"accountId": int(account_id), "id": rule_id})

            delete_result = self._base._extract_mutation_result(
                result, "alertsMutingRuleDelete", error_message="Failed to delete muting rule"
            )
            if isinstance(delete_result, ApiError):
                return delete_result

            return {
                "success": True,
                "id": delete_result.get("id"),
                "message": f"Muting rule '{rule_id}' deleted successfully",
            }

        except API_ERRORS as e:
            return handle_api_error("delete muting rule", e)

    async def delete_workflow(
        self, account_id: str, workflow_id: str, delete_channels: bool = True
    ) -> dict[str, Any] | ApiError:
        """Delete a workflow"""
        mutation = """
        mutation($accountId: Int!, $deleteChannels: Boolean!, $id: ID!) {
          aiWorkflowsDeleteWorkflow(accountId: $accountId, deleteChannels: $deleteChannels, id: $id) {
            id
            errors {
              description
              type
            }
          }
        }
        """

        try:
            result = await self._base.execute_graphql(
                mutation, {"accountId": int(account_id), "deleteChannels": delete_channels, "id": workflow_id}
            )

            delete_result = self._base._extract_mutation_result(
                result, "aiWorkflowsDeleteWorkflow", error_message="Workflow deletion failed"
            )
            if isinstance(delete_result, ApiError):
                return delete_result

            return {
                "success": True,
                "id": delete_result.get("id"),
                "message": "Workflow deleted successfully",
            }

        except API_ERRORS as e:
            return handle_api_error("delete workflow", e)
