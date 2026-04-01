"""
Tool definitions for New Relic MCP Server.

Centralized definition of all available tools and their schemas.
"""

from mcp.types import Tool


def get_monitoring_tools() -> list[Tool]:
    """Get monitoring and performance tools"""
    return [
        Tool(
            name="query_nrql",
            description=(
                "Execute a NRQL query against New Relic. "
                "Common event types: Transaction, TransactionError, Span, Log, Metric, "
                "KeyTransaction, ExternalCall, SyntheticCheck, PageView, MobileSession. "
                "Tips: Use SINCE X hours/days ago for time ranges (e.g. SINCE 3 hours ago). "
                "For high-volume apps, use shorter time windows (1-3 hours) to avoid query timeouts. "
                "Use TIMESERIES for trend data over time. Use FACET for grouping results. "
                "Prefer uniqueCount() over uniques() for high-cardinality attributes. "
                "Use LIMIT to cap result rows (default is 10 for FACET queries). "
                "Time range formats: SINCE 1 hour ago, SINCE '2024-01-15 00:00:00', SINCE timestamp."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "NRQL query to execute"},
                    "account_id": {
                        "type": "string",
                        "description": "New Relic account ID (optional, uses default if not provided)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_app_performance",
            description="Get performance metrics for a specific application",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application"},
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 1)",
                        "default": 1,
                    },
                },
                "required": ["app_name"],
            },
        ),
        Tool(
            name="get_app_errors",
            description="Get error metrics for a specific application",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application"},
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 1)",
                        "default": 1,
                    },
                },
                "required": ["app_name"],
            },
        ),
        Tool(
            name="get_incidents",
            description="Get recent incidents from New Relic",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 24)",
                        "default": 24,
                    }
                },
            },
        ),
        Tool(
            name="get_infrastructure_hosts",
            description="Get infrastructure hosts and their metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 1)",
                        "default": 1,
                    }
                },
            },
        ),
        Tool(
            name="get_alert_violations",
            description="Get recent alert violations and incidents",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 24)",
                        "default": 24,
                    }
                },
            },
        ),
        Tool(
            name="get_deployments",
            description="Get deployment markers and their impact",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application (optional, gets all deployments if not provided)",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (default: 168 = 1 week)",
                        "default": 168,
                    },
                },
            },
        ),
    ]


def get_dashboard_tools() -> list[Tool]:
    """Get dashboard management tools"""
    return [
        Tool(
            name="get_dashboards",
            description="Get New Relic dashboards (max 200 due to API limits). Use search parameter to find specific dashboards efficiently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Search term to filter dashboards by name (case-insensitive). Recommended for large accounts.",
                    },
                    "guid": {"type": "string", "description": "Specific dashboard GUID to retrieve"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of dashboards to retrieve (default: 200, API max: 200)",
                        "default": 200,
                        "maximum": 200,
                    },
                },
            },
        ),
        Tool(
            name="create_dashboard",
            description="Create a new New Relic dashboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the dashboard"},
                    "description": {"type": "string", "description": "Description of the dashboard (optional)"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="add_widget_to_dashboard",
            description="""Add a widget to an existing dashboard (requires dashboard GUID and widget configuration).

Use the optional `raw_configuration` parameter to control advanced chart display settings. When provided,
it is sent as `rawConfiguration` to NerdGraph and takes precedence over the typed configuration.
The `raw_configuration` object should include `nrqlQueries` plus any display options.

**IMPORTANT: `nrqlQueries` uses `accountIds` (array) not `accountId` (scalar):**
`"nrqlQueries": [{"accountIds": [123456], "query": "SELECT ..."}]`
This is auto-populated from widget_query if omitted.

**Fixed Y-Axis Range (left axis):**
`{"yAxisLeft": {"min": 0, "max": 500, "zero": false}}`

**Dual Y-Axis (second axis on right):**
IMPORTANT: dual y-axis requires the COMPLETE rawConfiguration (not just yAxisRight).
NR automatically appends an aggregation suffix to series names: percentile() → " (99%)", average() → no suffix.
The alias in the query should NOT include the suffix — NR adds it. Use the rendered name in series[].name.
Example — query alias is 'My Series', NR renders it as 'My Series (99%)' for percentile():
```json
{
  "nrqlQueries": [{"accountIds": [123456], "query": "SELECT count(*) AS 'Left', percentile(duration, 99) AS 'My Series' FROM ... TIMESERIES"}],
  "chartStyles": {"lineInterpolation": "linear"},
  "facet": {"showOtherSeries": false},
  "legend": {"enabled": true},
  "markers": {"displayedTypes": {"criticalViolations": false, "deployments": true, "relatedDeployments": true, "warningViolations": false}},
  "platformOptions": {"ignoreTimeRange": false},
  "thresholds": {"isLabelVisible": true},
  "yAxisLeft": {"zero": true},
  "yAxisRight": {"zero": true, "series": [{"name": "My Series (99%)"}]}
}
```

**Hide Legend:**
`{"legend": {"enabled": false}}`

**Facet - show/hide Other series:**
`{"facet": {"showOtherSeries": true}}`

**Ignore dashboard time picker:**
`{"platformOptions": {"ignoreTimeRange": true}}`

**Threshold label visibility (shows/hides threshold labels on chart):**
`{"thresholds": {"isLabelVisible": true}}`

**Chart line style:**
`{"chartStyles": {"lineInterpolation": "linear"}}` (or "step", "smooth")

**Deployment markers:**
`{"markers": {"displayedTypes": {"deployments": true, "relatedDeployments": true, "criticalViolations": false, "warningViolations": false}}}`

**Combined example (fixed range + no legend):**
```json
{
  "nrqlQueries": [{"accountIds": [123456], "query": "SELECT count(*) FROM Log TIMESERIES"}],
  "yAxisLeft": {"min": 0, "max": 1000, "zero": true},
  "legend": {"enabled": false}
}
```
Note: logarithmic scale is not supported by New Relic for line/area charts.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_guid": {"type": "string", "description": "GUID of the dashboard to add widget to"},
                    "widget_title": {"type": "string", "description": "Title for the widget"},
                    "widget_query": {"type": "string", "description": "NRQL query for the widget"},
                    "widget_type": {
                        "type": "string",
                        "description": "Type of widget (line, area, bar, pie, table, billboard, etc.)",
                        "default": "line",
                    },
                    "raw_configuration": {
                        "type": "object",
                        "description": (
                            "Advanced chart display configuration sent as rawConfiguration to NerdGraph. "
                            "Must include 'nrqlQueries' array with accountIds (array, not scalar). "
                            "Supports: yAxisLeft ({min, max, zero}), yAxisRight ({zero, series:[{name}]}), "
                            "legend ({enabled}), facet ({showOtherSeries}), platformOptions ({ignoreTimeRange}), "
                            "thresholds ({isLabelVisible}), chartStyles ({lineInterpolation: linear/step/smooth}), "
                            "markers ({displayedTypes: {deployments, relatedDeployments, criticalViolations, warningViolations}}). "
                            "Note: logarithmic scale is NOT supported. "
                            "Overrides the typed configuration when provided."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["dashboard_guid", "widget_title", "widget_query"],
            },
        ),
        Tool(
            name="search_all_dashboards",
            description="Search through dashboards with local filtering (retrieves max 200 from API, then searches locally). Better for complex searches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Search term to filter dashboards by name (case-insensitive)",
                    },
                    "guid": {"type": "string", "description": "Specific dashboard GUID to find"},
                },
            },
        ),
        Tool(
            name="get_dashboard_widgets",
            description="Get all widgets from a dashboard with their details and IDs",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_guid": {"type": "string", "description": "Dashboard GUID to get widgets from"}
                },
                "required": ["dashboard_guid"],
            },
        ),
        Tool(
            name="update_widget",
            description="""Update an existing widget on a dashboard.

Use the optional `raw_configuration` parameter to control advanced chart display settings. When provided,
it is sent as `rawConfiguration` to NerdGraph and takes precedence over the typed configuration.
The `raw_configuration` object should include `nrqlQueries` plus any display options.

**IMPORTANT: `nrqlQueries` uses `accountIds` (array) not `accountId` (scalar):**
`"nrqlQueries": [{"accountIds": [123456], "query": "SELECT ..."}]`
This is auto-populated from widget_query if omitted.

**Fixed Y-Axis Range (left axis):**
`{"yAxisLeft": {"min": 0, "max": 500, "zero": false}}`

**Dual Y-Axis (second axis on right):**
IMPORTANT: requires the COMPLETE rawConfiguration. NR appends aggregation suffix to series names automatically
(percentile() → " (99%)", average() → no suffix). Query alias should NOT include the suffix.
See add_widget_to_dashboard for the full dual y-axis example.

**Hide Legend:**
`{"legend": {"enabled": false}}`

**Facet - show/hide Other series:**
`{"facet": {"showOtherSeries": true}}`

**Ignore dashboard time picker:**
`{"platformOptions": {"ignoreTimeRange": true}}`

**Threshold label visibility:**
`{"thresholds": {"isLabelVisible": true}}`

**Chart line style:**
`{"chartStyles": {"lineInterpolation": "linear"}}` (or "step", "smooth")

Note: logarithmic scale is not supported by New Relic for line/area charts.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_guid": {"type": "string", "description": "Page GUID where the widget is located"},
                    "widget_id": {"type": "string", "description": "Widget ID to update"},
                    "widget_title": {"type": "string", "description": "New title for the widget"},
                    "widget_query": {"type": "string", "description": "New NRQL query for the widget"},
                    "widget_type": {
                        "type": "string",
                        "description": "New widget type (line, area, bar, pie, table, billboard, etc.)",
                        "default": "line",
                    },
                    "raw_configuration": {
                        "type": "object",
                        "description": (
                            "Advanced chart display configuration sent as rawConfiguration to NerdGraph. "
                            "Must include 'nrqlQueries' array with accountIds (array, not scalar). "
                            "Supports: yAxisLeft ({min, max, zero}), yAxisRight ({zero, series:[{name}]}), "
                            "legend ({enabled}), facet ({showOtherSeries}), platformOptions ({ignoreTimeRange}), "
                            "thresholds ({isLabelVisible}), chartStyles ({lineInterpolation: linear/step/smooth}). "
                            "Note: logarithmic scale is NOT supported. "
                            "Overrides the typed configuration when provided."
                        ),
                        "additionalProperties": True,
                    },
                },
                "required": ["page_guid", "widget_id"],
            },
        ),
        Tool(
            name="delete_widget",
            description="Delete a widget from a dashboard",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_guid": {"type": "string", "description": "Page GUID where the widget is located"},
                    "widget_id": {"type": "string", "description": "Widget ID to delete"},
                },
                "required": ["page_guid", "widget_id"],
            },
        ),
        Tool(
            name="delete_dashboard",
            description="Delete a dashboard by GUID",
            inputSchema={
                "type": "object",
                "properties": {
                    "dashboard_guid": {"type": "string", "description": "GUID of the dashboard to delete"},
                },
                "required": ["dashboard_guid"],
            },
        ),
    ]


def get_alert_tools() -> list[Tool]:
    """Get alert management tools"""
    return [
        Tool(
            name="create_alert_policy",
            description="Create a new alert policy",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the alert policy"},
                    "incident_preference": {
                        "type": "string",
                        "description": "How incidents are created (PER_POLICY, PER_CONDITION, PER_CONDITION_AND_TARGET)",
                        "default": "PER_POLICY",
                        "enum": ["PER_POLICY", "PER_CONDITION", "PER_CONDITION_AND_TARGET"],
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="create_nrql_condition",
            description="Create a NRQL alert condition",
            inputSchema={
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "Alert policy ID to attach the condition to"},
                    "name": {"type": "string", "description": "Name of the alert condition"},
                    "description": {"type": "string", "description": "Description of the alert condition (optional)"},
                    "nrql_query": {"type": "string", "description": "NRQL query for the condition"},
                    "threshold": {"type": "number", "description": "Alert threshold value"},
                    "threshold_operator": {
                        "type": "string",
                        "description": "Threshold operator (ABOVE, BELOW, EQUAL)",
                        "default": "ABOVE",
                        "enum": ["ABOVE", "BELOW", "EQUAL"],
                    },
                    "threshold_duration": {
                        "type": "integer",
                        "description": "Duration in seconds for threshold breach (60-7200)",
                        "default": 300,
                        "minimum": 60,
                        "maximum": 7200,
                    },
                    "priority": {
                        "type": "string",
                        "description": "Alert priority (CRITICAL, HIGH, MEDIUM, LOW)",
                        "default": "CRITICAL",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                    "aggregation_window": {
                        "type": "integer",
                        "description": "Aggregation window in seconds (30-1200)",
                        "default": 60,
                        "minimum": 30,
                        "maximum": 1200,
                    },
                },
                "required": ["policy_id", "name", "nrql_query", "threshold"],
            },
        ),
        Tool(
            name="create_notification_destination",
            description="Create a notification destination (email, webhook, Slack, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the destination"},
                    "type": {
                        "type": "string",
                        "description": "Type of destination (EMAIL, WEBHOOK, SLACK, etc.)",
                        "enum": ["EMAIL", "WEBHOOK", "SLACK", "PAGERDUTY", "SERVICE_NOW"],
                    },
                    "properties": {
                        "type": "object",
                        "description": "Destination-specific properties (e.g., email address, webhook URL)",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["name", "type", "properties"],
            },
        ),
        Tool(
            name="create_notification_channel",
            description="Create a notification channel linked to a destination",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the notification channel"},
                    "destination_id": {"type": "string", "description": "ID of the destination to link to"},
                    "product": {
                        "type": "string",
                        "description": "Product type (IINT for Applied Intelligence)",
                        "default": "IINT",
                    },
                    "type": {
                        "type": "string",
                        "description": "Channel type (EMAIL, WEBHOOK, SLACK, etc.)",
                        "enum": ["EMAIL", "WEBHOOK", "SLACK", "PAGERDUTY", "SERVICE_NOW"],
                    },
                    "properties": {
                        "type": "object",
                        "description": "Channel-specific properties",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["name", "destination_id", "type"],
            },
        ),
        Tool(
            name="create_workflow",
            description="Create a workflow to connect alert policies to notification channels",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the workflow"},
                    "channel_ids": {
                        "type": "array",
                        "description": "List of notification channel IDs to send alerts to",
                        "items": {"type": "string"},
                    },
                    "filter_name": {
                        "type": "string",
                        "description": "Name for the issues filter (optional)",
                        "default": "Filter-name",
                    },
                    "filter_predicates": {
                        "type": "array",
                        "description": "Filter predicates to determine which alerts trigger this workflow",
                        "items": {
                            "type": "object",
                            "properties": {
                                "attribute": {"type": "string"},
                                "operator": {
                                    "type": "string",
                                    "enum": ["EQUAL", "NOT_EQUAL", "IN", "NOT_IN", "CONTAINS", "DOES_NOT_CONTAIN"],
                                },
                                "values": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["attribute", "operator", "values"],
                        },
                    },
                    "enabled": {"type": "boolean", "description": "Whether the workflow is enabled", "default": True},
                },
                "required": ["name", "channel_ids"],
            },
        ),
        Tool(
            name="update_alert_policy",
            description="Update an existing alert policy (name and/or incident preference)",
            inputSchema={
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "ID of the alert policy to update"},
                    "name": {"type": "string", "description": "New name for the policy (optional)"},
                    "incident_preference": {
                        "type": "string",
                        "description": "New incident preference (optional)",
                        "enum": ["PER_POLICY", "PER_CONDITION", "PER_CONDITION_AND_TARGET"],
                    },
                },
                "required": ["policy_id"],
            },
        ),
        Tool(
            name="delete_alert_policy",
            description="Delete an alert policy by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "policy_id": {"type": "string", "description": "ID of the alert policy to delete"},
                },
                "required": ["policy_id"],
            },
        ),
        Tool(
            name="update_nrql_condition",
            description="Update an existing NRQL alert condition",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {"type": "string", "description": "ID of the condition to update"},
                    "name": {"type": "string", "description": "New name (optional)"},
                    "description": {"type": "string", "description": "New description (optional)"},
                    "nrql_query": {"type": "string", "description": "New NRQL query (optional)"},
                    "enabled": {"type": "boolean", "description": "Enable or disable the condition (optional)"},
                    "threshold": {"type": "number", "description": "New threshold value (optional)"},
                    "threshold_operator": {
                        "type": "string",
                        "description": "New threshold operator (optional)",
                        "enum": ["ABOVE", "BELOW", "EQUAL"],
                    },
                    "threshold_duration": {
                        "type": "integer",
                        "description": "New threshold duration in seconds (optional)",
                        "minimum": 60,
                        "maximum": 7200,
                    },
                    "priority": {
                        "type": "string",
                        "description": "New alert priority (optional)",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                    },
                },
                "required": ["condition_id"],
            },
        ),
        Tool(
            name="delete_nrql_condition",
            description="Delete a NRQL alert condition by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "condition_id": {"type": "string", "description": "ID of the condition to delete"},
                },
                "required": ["condition_id"],
            },
        ),
        Tool(
            name="delete_notification_destination",
            description="Delete a notification destination by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "destination_id": {"type": "string", "description": "ID of the destination to delete"},
                },
                "required": ["destination_id"],
            },
        ),
        Tool(
            name="delete_workflow",
            description="Delete a workflow by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "ID of the workflow to delete"},
                    "delete_channels": {
                        "type": "boolean",
                        "description": "Also delete associated notification channels (default: true)",
                        "default": True,
                    },
                },
                "required": ["workflow_id"],
            },
        ),
        Tool(
            name="create_muting_rule",
            description=(
                "Create a muting rule to suppress alert notifications during scheduled windows. "
                "Use conditions to match specific policies, condition names, or entity attributes. "
                "Use schedule for recurring windows (DAILY, WEEKLY). "
                "Condition attributes: policyId, policyName, conditionId, conditionName, entity.name, entity.type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the muting rule"},
                    "description": {"type": "string", "description": "Description of the muting rule (optional)"},
                    "enabled": {"type": "boolean", "description": "Whether the rule is enabled (default: true)", "default": True},
                    "condition_operator": {
                        "type": "string",
                        "description": "Logical operator for combining conditions (AND, OR)",
                        "default": "AND",
                        "enum": ["AND", "OR"],
                    },
                    "conditions": {
                        "type": "array",
                        "description": "Conditions that define which alerts to mute",
                        "items": {
                            "type": "object",
                            "properties": {
                                "attribute": {
                                    "type": "string",
                                    "description": "Alert attribute (policyId, policyName, conditionId, conditionName, entity.name, entity.type)",
                                },
                                "operator": {
                                    "type": "string",
                                    "description": "Comparison operator",
                                    "enum": ["EQUALS", "NOT_EQUALS", "IN", "NOT_IN", "CONTAINS", "DOES_NOT_CONTAIN", "ENDS_WITH", "NOT_ENDS_WITH", "STARTS_WITH", "NOT_STARTS_WITH", "IS_BLANK", "IS_NOT_BLANK", "ANY"],
                                },
                                "values": {
                                    "type": "array",
                                    "description": "Values to match against",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": ["attribute", "operator", "values"],
                        },
                    },
                    "schedule": {
                        "type": "object",
                        "description": "Schedule for recurring muting (optional). startTime/endTime format: ISO 8601 (e.g. 2026-04-01T03:00:00)",
                        "properties": {
                            "startTime": {"type": "string", "description": "Start time (ISO 8601)"},
                            "endTime": {"type": "string", "description": "End time (ISO 8601)"},
                            "timeZone": {"type": "string", "description": "Time zone (e.g. America/New_York)"},
                            "repeat": {
                                "type": "string",
                                "description": "Recurrence (DAILY, WEEKLY, MONTHLY)",
                                "enum": ["DAILY", "WEEKLY", "MONTHLY"],
                            },
                            "endRepeat": {"type": "string", "description": "When to stop repeating (ISO 8601, optional)"},
                            "weeklyRepeatDays": {
                                "type": "array",
                                "description": "Days for WEEKLY repeat",
                                "items": {"type": "string", "enum": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]},
                            },
                        },
                    },
                },
                "required": ["name", "conditions"],
            },
        ),
        Tool(
            name="list_muting_rules",
            description="List all muting rules in the account with their conditions and schedules",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="delete_muting_rule",
            description="Delete a muting rule by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string", "description": "ID of the muting rule to delete"},
                },
                "required": ["rule_id"],
            },
        ),
        Tool(
            name="list_alert_policies",
            description="List all alert policies in the account",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_alert_conditions",
            description="List alert conditions with optional filters by policy, name, or NRQL query",
            inputSchema={
                "type": "object",
                "properties": {
                    "policy_id": {
                        "type": "string",
                        "description": "Policy ID to filter conditions (optional)",
                    },
                    "name": {
                        "type": "string",
                        "description": "Exact condition name to search for (optional)",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search conditions by NRQL query content (partial match, optional)",
                    },
                },
            },
        ),
        Tool(
            name="list_notification_destinations",
            description="List all notification destinations",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_notification_channels",
            description="List all notification channels",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_workflows",
            description="List all alert workflows",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def get_entity_tools() -> list[Tool]:
    """Get entity search, tagging, service level, and synthetic monitor tools"""
    return [
        Tool(
            name="entity_search",
            description=(
                "Search for New Relic entities (APM apps, hosts, synthetic monitors, browsers, etc.) "
                "by name, type, domain, or tags. Returns GUIDs, alert severity, and metadata. "
                "Use domain values: APM, INFRA, SYNTH, BROWSER, MOBILE, EXT. "
                "Use type values: APPLICATION, HOST, MONITOR, KEY_TRANSACTION, etc. "
                "Use minimal_output=true to reduce response size (omits tags and type-specific fields). "
                "Use limit to cap results (default 25, max 200)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Entity name to search for (partial match)"},
                    "entity_type": {
                        "type": "string",
                        "description": "Entity type filter (e.g. APPLICATION, HOST, MONITOR, KEY_TRANSACTION)",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Domain filter: APM, INFRA, SYNTH, BROWSER, MOBILE, EXT",
                    },
                    "tags": {
                        "type": "array",
                        "description": "Tag filters as [{key, value}] pairs",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum entities to return (default 25, max 200)",
                        "default": 25,
                        "maximum": 200,
                    },
                    "minimal_output": {
                        "type": "boolean",
                        "description": "If true, return only name, GUID, domain, type, and alertSeverity (omit tags and type-specific fields) to reduce response size",
                        "default": False,
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
            },
        ),
        Tool(
            name="decode_entity_guid",
            description=(
                "Decode a New Relic entity GUID (base64-encoded) to reveal its components: "
                "account ID, domain (APM, EXT, INFRA, etc.), entity type (APPLICATION, KEY_TRANSACTION, HOST, etc.), "
                "and domain ID. Useful for understanding what an entity GUID refers to without making an API call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "The NR entity GUID to decode"},
                },
                "required": ["guid"],
            },
        ),
        Tool(
            name="get_entity",
            description=(
                "Look up a single New Relic entity by its GUID. Returns full details including "
                "name, type, domain, alert severity, account info, tags, permalink, and type-specific "
                "metadata (language for APM apps, monitor type for synthetics, host metrics for infra). "
                "Use entity_search to find GUIDs, or decode_entity_guid to inspect a GUID without an API call."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID to look up"},
                },
                "required": ["guid"],
            },
        ),
        Tool(
            name="get_entity_tags",
            description="Get all tags for a New Relic entity by its GUID. Use entity_search to find GUIDs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID"},
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["guid"],
            },
        ),
        Tool(
            name="add_tags_to_entity",
            description="Add or update tags on a New Relic entity. Tags are key-value pairs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID"},
                    "tags": {
                        "type": "array",
                        "description": "Tags to add as [{key, value}] pairs",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["guid", "tags"],
            },
        ),
        Tool(
            name="replace_tags_on_entity",
            description="Replace ALL tags on a New Relic entity (overwrites existing tags). Use add_tags_to_entity to append instead.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID"},
                    "tags": {
                        "type": "array",
                        "description": "Tags to set as [{key, value}] pairs (replaces all existing tags)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["guid", "tags"],
            },
        ),
        Tool(
            name="delete_tags_from_entity",
            description="Delete tag keys (and all their values) from a New Relic entity.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID"},
                    "tag_keys": {
                        "type": "array",
                        "description": "Tag keys to delete",
                        "items": {"type": "string"},
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["guid", "tag_keys"],
            },
        ),
        Tool(
            name="delete_tag_values",
            description="Delete specific tag key-value pairs from an entity (keeps the key if other values remain).",
            inputSchema={
                "type": "object",
                "properties": {
                    "guid": {"type": "string", "description": "Entity GUID"},
                    "tag_values": {
                        "type": "array",
                        "description": "Tag key-value pairs to delete as [{key, value}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["guid", "tag_values"],
            },
        ),
        Tool(
            name="list_service_levels",
            description=(
                "List all Service Level Indicators (SLIs/SLOs) for the account. "
                "Shows objectives, target percentages, time windows, and the NRQL queries "
                "used to measure good/valid events."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
            },
        ),
        Tool(
            name="list_synthetic_monitors",
            description=(
                "List all synthetic monitors with their current status, success rate, "
                "monitor type (simple, scripted browser, API test, etc.), check period, "
                "and location health."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
            },
        ),
        Tool(
            name="get_synthetic_results",
            description=(
                "Get recent check results for a specific synthetic monitor. "
                "Shows pass/fail per location, duration, and error messages. "
                "Use list_synthetic_monitors to find monitor GUIDs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "monitor_guid": {"type": "string", "description": "Synthetic monitor entity GUID"},
                    "hours": {
                        "type": "integer",
                        "description": "Hours to look back (default: 24)",
                        "default": 24,
                    },
                    "account_id": {"type": "string", "description": "Account ID (optional)"},
                },
                "required": ["monitor_guid"],
            },
        ),
    ]


def get_all_tools() -> list[Tool]:
    """Get all available tools"""
    return get_monitoring_tools() + get_dashboard_tools() + get_alert_tools() + get_entity_tools()
