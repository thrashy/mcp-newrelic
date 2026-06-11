"""Shared per-item formatters for alert policies and conditions.

Used by both the tool handlers and the MCP resource handlers.
"""

from typing import Any


def format_alert_policy(policy: dict[str, Any]) -> str:
    """Format a single alert policy as a markdown list item."""
    name = policy.get("name", "Unknown")
    policy_id = policy.get("id", "Unknown")
    incident_preference = policy.get("incidentPreference", "Unknown")
    return f"- **{name}**\n  ID: {policy_id}\n  Incident Preference: {incident_preference}\n\n"


def format_alert_condition(condition: dict[str, Any]) -> str:
    """Format a single NRQL alert condition as a markdown list item."""
    name = condition.get("name", "Unknown")
    condition_id = condition.get("id", "Unknown")
    enabled = condition.get("enabled", "Unknown")
    policy_name = condition.get("policyName", "Unknown")
    description = condition.get("description")

    nrql = condition.get("nrql", {})
    query = nrql.get("query", "") if isinstance(nrql, dict) else ""

    terms = condition.get("terms", [])

    lines = [f"- **{name}**", f"  ID: {condition_id}", f"  Policy: {policy_name}", f"  Enabled: {enabled}"]

    if description:
        lines.append(f"  Description: {description}")

    if query:
        lines.append(f"  NRQL: `{query}`")

    for term in terms:
        priority = term.get("priority", "").capitalize()
        operator = term.get("operator", "").lower()
        threshold = term.get("threshold")
        duration = term.get("thresholdDuration")
        if threshold is not None:
            lines.append(f"  {priority}: {operator} {threshold} for {duration}s")

    lines.append("")
    return "\n".join(lines) + "\n"
