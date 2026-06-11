"""Common error handling utilities for New Relic MCP Server."""

import logging
from typing import Any

import httpx

from ..types import ApiError

logger = logging.getLogger(__name__)

# Exception types that indicate API/network failures (not bugs in our code).
# GraphQL errors and JSON decode failures surface as ValueError from the base client;
# KeyError/TypeError are deliberately excluded so programming errors keep their traceback.
API_ERRORS = (httpx.HTTPError, ValueError)


def handle_api_error(operation_name: str, exception: Exception) -> ApiError:
    """Standardized error handling for API operations"""
    logger.error("%s failed: %s", operation_name, exception)
    return ApiError(str(exception))


def handle_graphql_notification_errors(create_result: dict[str, Any], operation_name: str) -> ApiError | None:
    """Handle GraphQL notification API errors"""
    if create_result.get("errors"):
        errors = create_result["errors"]
        if errors:
            error = errors[0]
            error_type = error.get("__typename", "Unknown")
            error_msg = error.get("description", error.get("type", f"Error type: {error_type}"))
            return ApiError(f"{operation_name} failed: {error_msg}")
    return None


def format_resource_error(error: ApiError, section_title: str) -> str:
    """Format error response for resource handlers"""
    return f"# {section_title}\n\nError: {error.message}"
