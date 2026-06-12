"""Authentication service: thin wrapper over StaffRepo for login.

Re-exports the password helpers so callers have a single import surface.
"""
from app.infra.repositories import StaffRepo
from app.services._security import hash_password, verify_password

__all__ = ["authenticate", "hash_password", "verify_password"]


def authenticate(db, code, password):
    """Return the StaffRow on valid credentials, else None."""
    return StaffRepo(db).authenticate(code, password)
