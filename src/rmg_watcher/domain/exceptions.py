"""Custom errors: ApiError, StorageError."""

from __future__ import annotations


class TransitError(Exception):
    """Base class for application errors."""


class ApiError(TransitError):
    """Raised when a transit API request cannot be completed."""


class StorageError(TransitError):
    """Raised when a database operation fails."""
