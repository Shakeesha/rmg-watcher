"""Custom errors: ApiError, ValidationError, StorageError."""

from __future__ import annotations


class TransitError(Exception):
    """Base class for application errors."""


class ApiError(TransitError):
    """Raised when a transit API request cannot be completed."""


class ValidationError(TransitError):
    """Raised when a payload cannot be validated."""


class StorageError(TransitError):
    """Raised when a database operation fails."""
