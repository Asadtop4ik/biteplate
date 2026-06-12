"""Custom exceptions and validation helpers (secure coding)."""

class BitePlateError(Exception):
    """Base class for all domain errors."""

class ValidationError(BitePlateError):
    """Raised when user input fails validation."""

class PermissionDenied(BitePlateError):
    """Raised when a staff role attempts an action it is not allowed to."""

class IllegalStateTransition(BitePlateError):
    """Raised when a Table is moved to an invalid next state."""


def require_positive_int(value, field):
    """Validate that *value* is a positive integer."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number, got {value!r}")
    if ivalue <= 0:
        raise ValidationError(f"{field} must be positive, got {ivalue}")
    return ivalue


def require_non_empty(value, field):
    """Validate that *value* is a non-empty string."""
    if value is None or not str(value).strip():
        raise ValidationError(f"{field} must not be empty")
    return str(value).strip()


def require_money(value, field):
    """Validate that *value* is a non-negative monetary amount."""
    try:
        fvalue = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number, got {value!r}")
    if fvalue < 0:
        raise ValidationError(f"{field} must not be negative, got {fvalue}")
    return round(fvalue, 2)
