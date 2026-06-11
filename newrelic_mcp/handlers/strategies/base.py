"""Base strategy interface for tool handlers"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from mcp.types import TextContent

from ...client import NewRelicClient
from ...config import NewRelicConfig
from ...types import ApiError, PaginatedResult, ToolError
from ...validators import InputValidator

_T = TypeVar("_T")


class ToolHandlerStrategy(ABC):
    """Abstract base class for tool handlers"""

    requires_account_id: bool = True

    def __init__(self, client: NewRelicClient, config: NewRelicConfig):
        self.client = client
        self.config = config

    @abstractmethod
    async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
        """Handle the tool execution"""

    @staticmethod
    def _create_error_response(message: str) -> list[TextContent]:
        """Create standardized error response"""
        return [TextContent(type="text", text=f"Error: {message}")]

    @staticmethod
    def _create_success_response(message: str) -> list[TextContent]:
        """Create standardized success response"""
        return [TextContent(type="text", text=message)]

    @staticmethod
    def _format_duration(duration: Any) -> str:
        """Format a duration value with ms units, or N/A if unavailable"""
        return f"{duration:.2f}ms" if isinstance(duration, int | float) else "N/A"

    @staticmethod
    def _format_tag_str(tags: list[dict[str, str]]) -> str:
        """Format a list of key/value tag dicts as 'key=value, ...'."""
        return ", ".join(f"{t['key']}={t['value']}" for t in tags)

    def _require_guid(self, arguments: dict[str, Any], key: str = "guid") -> str:
        """Validate and return a GUID from arguments. Raises ValidationError if invalid."""
        return InputValidator.validate_guid(arguments[key])

    def _unwrap(self, result: "_T | ApiError", error_context: str) -> "_T":
        """Return result if successful, raise ToolError if it's an ApiError."""
        if isinstance(result, ApiError):
            raise ToolError(f"{error_context}: {result.message}")
        return result

    def _handle_list_response(
        self,
        result: PaginatedResult | list[dict[str, Any]] | ApiError,
        *,
        error_context: str,
        empty_message: str,
        item_noun: str,
        format_item: Callable[[dict[str, Any]], str],
    ) -> list[TextContent]:
        """Handle common list response pattern: check error, check empty, format items."""
        if isinstance(result, ApiError):
            return self._create_error_response(f"{error_context}: {result.message}")
        items = result.items if isinstance(result, PaginatedResult) else result
        if not items:
            return self._create_success_response(empty_message)
        text = f"Found {len(items)} {item_noun}:\n\n"
        for item in items:
            text += format_item(item)
        return self._create_success_response(text)


def make_delete_handler(
    noun: str,
    arg_key: str,
    get_delete_method: Callable[[NewRelicClient], Callable[[str, str], Awaitable[dict[str, Any] | ApiError]]],
    *,
    error_noun: str,
) -> type[ToolHandlerStrategy]:
    """Build a handler class for delete tools of the shape: read id arg → delete → success message."""

    class _DeleteHandler(ToolHandlerStrategy):
        async def handle(self, arguments: dict[str, Any], account_id: str) -> list[TextContent]:
            item_id = arguments[arg_key]
            self._unwrap(
                await get_delete_method(self.client)(account_id, item_id),
                f"deleting {error_noun} '{item_id}'",
            )
            return self._create_success_response(f"{noun} '{item_id}' deleted successfully.")

    _DeleteHandler.__name__ = f"Delete{noun.title().replace(' ', '')}Handler"
    return _DeleteHandler
