"""
Input validation utilities for New Relic MCP Server.

Provides robust validation to prevent security issues and improve reliability.
"""

import re


class ValidationError(Exception):
    """Custom exception for validation errors"""


# NRQL is read-only (no DDL/DML), so validation is shape + length only.
# Queries may start with either SELECT or FROM (both are valid NRQL forms).
_NRQL_START_PATTERN = re.compile(r"^\s*(SELECT|FROM)\s+", re.IGNORECASE)
_GUID_PATTERN = re.compile(r"^[A-Za-z0-9+/=]+$")


class InputValidator:
    """Validates and sanitizes user inputs"""

    @classmethod
    def validate_nrql_query(cls, query: str) -> str:
        """Validate and sanitize NRQL query"""
        if not query:
            raise ValidationError("NRQL query cannot be empty")

        if len(query) > 10000:
            raise ValidationError("NRQL query too long (max 10,000 characters)")

        if not _NRQL_START_PATTERN.match(query):
            raise ValidationError("NRQL query must start with SELECT or FROM")

        return query.strip()

    @classmethod
    def validate_guid(cls, guid: str) -> str:
        """Validate New Relic GUID format"""
        if not guid:
            raise ValidationError("GUID cannot be empty")

        if not _GUID_PATTERN.match(guid):
            raise ValidationError("Invalid GUID format")

        if len(guid) < 10 or len(guid) > 100:
            raise ValidationError("GUID length invalid")

        return guid

    @classmethod
    def validate_app_name(cls, app_name: str) -> str:
        """Validate application name"""
        if not app_name:
            raise ValidationError("Application name cannot be empty")

        if len(app_name) > 200:
            raise ValidationError("Application name too long")

        # Basic sanitization
        return app_name.strip()

    @classmethod
    def validate_time_range(cls, hours: int) -> int:
        """Validate time range parameters"""
        if not isinstance(hours, int):
            raise ValidationError("Time range must be an integer")

        if hours < 1:
            raise ValidationError("Time range must be at least 1 hour")

        if hours > 8760:  # 1 year
            raise ValidationError("Time range cannot exceed 1 year")

        return hours
