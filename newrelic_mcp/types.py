"""Common types for New Relic MCP Server."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ApiError:
    """Represents an API operation failure.

    Replaces the fragile {"error": "..."} dict convention with an explicit type.
    Client methods return T | ApiError, and handlers use isinstance() checks.
    """

    message: str


class ToolError(Exception):
    """Raised by strategy handlers to signal a user-facing error.

    Caught by ToolHandlers.handle_tool_call and rendered as "Error: {message}".
    This lets handlers use _unwrap() instead of repeating isinstance(result, ApiError) checks.
    """


@dataclass(frozen=True, slots=True)
class DecodedEntityGuid:
    """Components of a decoded New Relic entity GUID.

    NR entity GUIDs are base64-encoded strings in the format:
    accountId|domain|entityType|domainId
    """

    account_id: int
    domain: str
    entity_type: str
    domain_id: str


@dataclass(frozen=True, slots=True)
class PaginatedResult:
    """Result from a paginated or list API query.

    Used by client list/search methods instead of raw dicts.
    Handlers use .items and .total_count instead of dict key lookups.
    """

    items: list[dict[str, Any]] = field(default_factory=list)
    total_count: int | None = None
