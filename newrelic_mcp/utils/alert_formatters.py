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
        occurrences = (term.get("thresholdOccurrences") or "").lower().replace("_", " ")
        if threshold is not None:
            suffix = f" ({occurrences})" if occurrences else ""
            lines.append(f"  {priority}: {operator} {threshold} for {duration}s{suffix}")

    signal = _format_signal(condition.get("signal") or {})
    if signal:
        lines.append(f"  Signal: {signal}")

    lines.append("")
    return "\n".join(lines) + "\n"


def _format_signal(signal: dict[str, Any]) -> str:
    parts = []
    if signal.get("aggregationWindow") is not None:
        parts.append(f"{signal['aggregationWindow']}s window")
    if signal.get("aggregationMethod"):
        parts.append(signal["aggregationMethod"].lower().replace("_", " "))
    if signal.get("aggregationDelay") is not None:
        parts.append(f"{signal['aggregationDelay']}s delay")
    if signal.get("aggregationTimer") is not None:
        parts.append(f"{signal['aggregationTimer']}s timer")
    if signal.get("evaluationOffset") is not None:
        parts.append(f"evaluation offset {signal['evaluationOffset']} windows")
    return ", ".join(parts)


def format_workflow(workflow: dict[str, Any]) -> str:
    """Format a single workflow with its enabled state, issues filter and destinations."""
    lines = [
        f"- **{workflow.get('name', 'Unknown')}**",
        f"  ID: {workflow.get('id', 'Unknown')}",
        f"  Enabled: {workflow.get('workflowEnabled', 'Unknown')}",
    ]

    predicates = (workflow.get("issuesFilter") or {}).get("predicates") or []
    if predicates:
        rendered = "; ".join(f"{p.get('attribute')} {p.get('operator')} {p.get('values')}" for p in predicates)
        lines.append(f"  Filter: {rendered}")

    destinations = workflow.get("destinationConfigurations") or []
    if destinations:
        rendered = ", ".join(f"{d.get('name', 'Unknown')} ({d.get('type', 'Unknown')})" for d in destinations)
        lines.append(f"  Destinations: {rendered}")

    lines.append("")
    return "\n".join(lines) + "\n"
