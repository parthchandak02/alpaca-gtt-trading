"""Helper utilities for database transaction management."""

import logging
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_transaction(db: Session, operation: Callable[[], T]) -> T:
    """Execute a database operation with proper commit/rollback handling.

    Args:
        db: Database session
        operation: Callable that performs database operations

    Returns:
        Result of the operation

    Raises:
        Exception: Re-raises any exception after rolling back
    """
    try:
        result = operation()
        db.commit()
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Database transaction failed, rolled back: {e}", exc_info=True)
        raise


def safe_commit(db: Session, operation_name: str = "operation") -> None:
    """Safely commit database changes with error handling.

    Args:
        db: Database session
        operation_name: Name of operation for logging

    Raises:
        Exception: Re-raises any exception after rolling back
    """
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to commit {operation_name}, rolled back: {e}", exc_info=True
        )
        raise
