"""GraphQL utility functions for data extraction and query building."""

from typing import Any


def extract_nested_data(result: dict[str, Any], path: list[str]) -> Any:
    """Extract nested data from GraphQL result following a path"""
    current: Any = result
    for key in path:
        if isinstance(current, dict):
            current = current.get(key, {})
        else:
            return {}
    return current


def extract_nrql_results(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract NRQL result rows from a standard actor.account.nrql response"""
    rows = extract_nested_data(result, ["data", "actor", "account", "nrql", "results"])
    return rows if isinstance(rows, list) else []


def escape_nrql_string(value: str) -> str:
    """Escape a string value for safe embedding in a NRQL query"""
    return value.replace("\\", "\\\\").replace("'", "\\'")
