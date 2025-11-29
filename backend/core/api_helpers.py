"""Helper utilities for consistent API responses and error handling."""

import logging
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def success_response(data: Any, message: str | None = None) -> dict[str, Any]:
    """Create a consistent success response.

    Args:
        data: Response data
        message: Optional success message

    Returns:
        Standardized success response dict
    """
    response: dict[str, Any] = {"success": True, "data": data}
    if message:
        response["message"] = message
    return response


def error_response(
    detail: str,
    status_code: int = 500,
    error_type: str | None = None,
    errors: list | None = None,
) -> HTTPException:
    """Create a consistent error response.

    Args:
        detail: Error message
        status_code: HTTP status code
        error_type: Optional error type/code
        errors: Optional list of validation errors

    Returns:
        HTTPException with standardized error format
    """
    error_detail: dict[str, Any] = {"detail": detail}
    if error_type:
        error_detail["error_type"] = error_type
    if errors:
        error_detail["errors"] = errors

    return HTTPException(status_code=status_code, detail=error_detail)


def handle_database_error(operation: str, error: Exception) -> HTTPException:
    """Handle database errors consistently.

    Args:
        operation: Description of the operation that failed
        error: The exception that occurred

    Returns:
        HTTPException with appropriate error response
    """
    logger.error(f"Database error during {operation}: {error}", exc_info=True)
    return error_response(
        detail=f"Database error: {error!s}",
        status_code=500,
        error_type="database_error",
    )


def handle_validation_error(field: str, message: str) -> HTTPException:
    """Handle validation errors consistently.

    Args:
        field: Field name that failed validation
        message: Validation error message

    Returns:
        HTTPException with validation error response
    """
    return error_response(
        detail=f"Validation error: {message}",
        status_code=400,
        error_type="validation_error",
        errors=[{"field": field, "message": message}],
    )
