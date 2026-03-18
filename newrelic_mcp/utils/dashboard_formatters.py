"""Dashboard-specific formatting utilities."""

from typing import Any


def format_dashboard_list(
    dashboards: list[dict[str, Any]],
    search: str = None,
    guid: str = None,
    limit_display: int = 50
) -> str:
    """Format dashboard list for display with consistent styling"""
    if not dashboards:
        search_info = f" matching '{search}'" if search else ""
        guid_info = f" with GUID '{guid}'" if guid else ""
        return f"No dashboards found{search_info}{guid_info}."

    # Create appropriate header
    if guid:
        dashboard_text = f"Found dashboard with GUID {guid}:\n\n"
    elif search:
        dashboard_text = f"Found {len(dashboards)} dashboards matching '{search}':\n\n"
    else:
        dashboard_text = f"Found {len(dashboards)} dashboards:\n\n"
        if len(dashboards) >= 200:
            dashboard_text += "📄 **Note**: New Relic API caps results at 200 dashboards. Use the search parameter to find specific dashboards.\n\n"

    # Format dashboard list
    for dashboard in dashboards[:limit_display]:
        name = dashboard.get("name", "Unknown")
        dashboard_guid = dashboard.get("guid", "Unknown")
        created = dashboard.get("createdAt", "Unknown")
        permalink = dashboard.get("permalink", "")

        dashboard_text += f"- **{name}**\n"
        dashboard_text += f"  GUID: {dashboard_guid}\n"
        dashboard_text += f"  Created: {created}\n"
        if permalink:
            dashboard_text += f"  URL: {permalink}\n"
        dashboard_text += "\n"

    if len(dashboards) > limit_display:
        if search:
            dashboard_text += f"... and {len(dashboards) - limit_display} more dashboards (use specific search terms to narrow results)\n"
        else:
            dashboard_text += f"... and {len(dashboards) - limit_display} more dashboards\n"

    return dashboard_text


def build_raw_nrql_queries(account_id: str, widget_query: str) -> list[dict[str, Any]]:
    """Build nrqlQueries array for rawConfiguration using accountIds (array, not scalar)."""
    return [{"accountIds": [int(account_id)], "query": widget_query}]


def build_widget_configuration(widget_type: str, account_id: str, widget_query: str) -> dict[str, Any]:
    """Build widget configuration for different visualization types"""
    nrql_query = {"accountId": int(account_id), "query": widget_query}

    widget_configurations = {
        "area": {"area": {"nrqlQueries": [nrql_query]}},
        "bar": {"bar": {"nrqlQueries": [nrql_query]}},
        "billboard": {"billboard": {"nrqlQueries": [nrql_query]}},
        "line": {"line": {"nrqlQueries": [nrql_query]}},
        "pie": {"pie": {"nrqlQueries": [nrql_query]}},
        "table": {"table": {"nrqlQueries": [nrql_query]}},
    }

    return widget_configurations.get(widget_type, {"line": {"nrqlQueries": [nrql_query]}})


def extract_nrql_queries(config: dict[str, Any]) -> list[str]:
    """Extract NRQL queries from widget configuration"""
    nrql_queries = []

    for viz_key in ["line", "area", "bar", "pie", "table", "billboard"]:
        if viz_key in config and config[viz_key] is not None and "nrqlQueries" in config[viz_key]:
            for query_obj in config[viz_key].get("nrqlQueries", []):
                if query_obj and query_obj.get("query"):
                    nrql_queries.append(query_obj["query"])

    return nrql_queries
