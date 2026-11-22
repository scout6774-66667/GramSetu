"""Exception hierarchy for GramSetu AI."""
from __future__ import annotations

from typing import Optional, Dict, Any


class GramSetuError(Exception):
    """Base exception for all GramSetu domain and store errors."""
    def __init__(self, message: str, status_code: int = 400, error_code: str = "BAD_REQUEST", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class CorruptionError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, error_code="STATE_CORRUPTION", details=details)


class DomainValidationError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, error_code="UNPROCESSABLE_ENTITY", details=details)


class NotFoundError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, error_code="NOT_FOUND", details=details)


class ConflictError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, error_code="CONFLICT", details=details)


class AuthorizationError(GramSetuError):
    def __init__(self, message: str, status_code: int = 403, error_code: str = "FORBIDDEN", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=status_code, error_code=error_code, details=details)


class InvariantViolationError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, error_code="INVARIANT_VIOLATION", details=details)


class ProcessLockError(GramSetuError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, error_code="CONCURRENT_WRITER_COLLISION", details=details)
