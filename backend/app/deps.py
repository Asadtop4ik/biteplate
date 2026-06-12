"""FastAPI dependencies: DB session, Redis client, current staff, permissions.

These wire the web layer to infra/domain. `current_staff` rebuilds a domain
`Staff` object from the session-stored staff_code so the permission model
(`staff.require(perm)`) is reused verbatim.
"""
import redis
from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.domain.errors import PermissionDenied
from app.domain.staff import Cashier, Chef, Manager, Waiter
from app.infra.db import SessionLocal
from app.infra.models import StaffRow

_ROLE_CLASSES = {
    "waiter": Waiter,
    "chef": Chef,
    "cashier": Cashier,
    "manager": Manager,
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis():
    return _redis


def current_staff(request: Request, db=Depends(get_db)):
    code = request.session.get("staff_code")
    if not code:
        raise HTTPException(status_code=401)
    row = db.query(StaffRow).filter_by(staff_code=code).first()
    if not row:
        raise HTTPException(status_code=401)
    klass = _ROLE_CLASSES.get(row.role)
    if klass is None:
        raise HTTPException(status_code=401)
    return klass(row.staff_code, row.name)


def require_permission(perm: str):
    def dep(staff=Depends(current_staff)):
        try:
            staff.require(perm)
        except PermissionDenied as e:
            raise HTTPException(status_code=403, detail=str(e))
        return staff

    return dep
