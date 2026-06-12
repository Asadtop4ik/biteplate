"""Celery tasks: the kitchen COMMAND pattern executed asynchronously.

The pure ``_apply``/``_revert`` functions hold all the domain logic and take an
explicit session + redis client so they can be unit-tested without a broker or
Postgres. The ``@celery_app.task`` wrappers are thin: they open their own
``SessionLocal`` and redis client, then delegate. Eager mode (set from the
``CELERY_TASK_ALWAYS_EAGER`` env var) lets tests run the task body inline.
"""
import os

from celery import Celery

from app.config import settings
from app.deps import get_redis
from app.domain.kitchen import (
    CancelOrderCommand,
    ExpediteOrderCommand,
    PrepareOrderCommand,
)
from app.domain.orders import OrderStatus
from app.domain.staff import Cashier, Chef, Manager, Waiter
from app.infra.db import SessionLocal
from app.infra.events import RedisPublishObserver
from app.infra.repositories import MenuRepo, OrderRepo, StaffRepo

celery_app = Celery(
    "biteplate",
    broker=settings.BROKER_URL,
    backend=settings.RESULT_BACKEND,
)
celery_app.conf.task_always_eager = os.environ.get("CELERY_TASK_ALWAYS_EAGER") == "1"
celery_app.conf.task_eager_propagates = True

ACTION_COMMANDS = {
    "prepare": PrepareOrderCommand,
    "cancel": CancelOrderCommand,
    "expedite": ExpediteOrderCommand,
}

_ROLE_CLASSES = {
    "waiter": Waiter,
    "chef": Chef,
    "cashier": Cashier,
    "manager": Manager,
}


def _build_staff(db, staff_code):
    row = StaffRepo(db).get_by_code(staff_code)
    if row is None:
        # Fall back to Manager so eager tests still run even without a staff row.
        return Manager(staff_code or "M00", "system")
    klass = _ROLE_CLASSES.get(row.role, Manager)
    return klass(row.staff_code, row.name)


def _apply(db, order_code, action, staff_code, redis_client):
    order_row = OrderRepo(db).get(order_code)
    staff = _build_staff(db, staff_code)
    order = OrderRepo(db).to_domain(
        order_row, MenuRepo(db), observers=[RedisPublishObserver(redis_client)]
    )
    cmd = ACTION_COMMANDS[action](staff, order)
    prev = order.status.value
    cmd.execute()  # checks permission, sets new status, notifies (publishes)
    OrderRepo(db).set_status(order_code, order.status.value)
    db.commit()
    return {
        "order_code": order_code,
        "action": action,
        "prev_status": prev,
        "new_status": order.status.value,
    }


def _revert(db, order_code, prev_status, action, redis_client, staff_code=""):
    """Undo a kitchen action by driving the SAME domain Command's undo().

    The forward task captured the pre-execute status in ``self._prev``; since the
    Command object cannot survive across Celery tasks/processes, we rebuild it and
    restore ``_prev`` from the persisted value, then call ``undo()`` — so the
    domain ``Command.undo()`` is the actual undo mechanism, not a bare set_status.
    """
    order_row = OrderRepo(db).get(order_code)
    staff = _build_staff(db, staff_code)
    order = OrderRepo(db).to_domain(
        order_row, MenuRepo(db), observers=[RedisPublishObserver(redis_client)]
    )
    cmd = ACTION_COMMANDS[action](staff, order)
    cmd._prev = OrderStatus(prev_status)  # restore the command's captured state
    cmd.undo()  # domain Command.undo(): reverts status + notifies (publishes)
    OrderRepo(db).set_status(order_code, order.status.value)
    db.commit()
    return {"order_code": order_code, "reverted_to": order.status.value}


@celery_app.task
def prepare_order_task(order_code, staff_code):
    with SessionLocal() as db:
        return _apply(db, order_code, "prepare", staff_code, get_redis())


@celery_app.task
def cancel_order_task(order_code, staff_code):
    with SessionLocal() as db:
        return _apply(db, order_code, "cancel", staff_code, get_redis())


@celery_app.task
def expedite_order_task(order_code, staff_code):
    with SessionLocal() as db:
        return _apply(db, order_code, "expedite", staff_code, get_redis())


@celery_app.task
def revert_status_task(order_code, prev_status, action, staff_code=""):
    with SessionLocal() as db:
        return _revert(db, order_code, prev_status, action, get_redis(), staff_code)
