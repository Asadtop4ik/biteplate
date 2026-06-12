"""Kitchen service: the COMMAND invoker over Celery, with Redis-backed undo.

``enqueue`` records the previous status in a per-order Redis list (the undo
history) and dispatches the matching Celery task. ``undo_last`` pops the most
recent entry and dispatches a revert task. ``active_orders`` reads the orders
currently in flight for the kitchen board.
"""
import json

from app.domain.orders import OrderStatus
from app.infra.repositories import OrderRepo
from app.infra.tasks import (
    cancel_order_task,
    expedite_order_task,
    prepare_order_task,
    revert_status_task,
)

ACTION_TASK = {
    "prepare": prepare_order_task,
    "cancel": cancel_order_task,
    "expedite": expedite_order_task,
}

ACTION_PERM = {
    "prepare": "prepare",
    "cancel": "prepare",
    "expedite": "reprioritise_kitchen",
}

_ACTIVE_STATUSES = (
    OrderStatus.QUEUED.value,
    OrderStatus.COOKING.value,
    OrderStatus.READY.value,
)


def _history_key(order_code):
    return f"kitchen:history:{order_code}"


def enqueue(db, action, order_code, staff, redis_client):
    prev = OrderRepo(db).get(order_code).status
    redis_client.rpush(
        _history_key(order_code),
        json.dumps({"action": action, "prev_status": prev}),
    )
    ACTION_TASK[action].delay(order_code, staff.staff_id)  # eager in tests
    return {"dispatched": action, "order_code": order_code}


def undo_last(db, order_code, redis_client, staff=None):
    raw = redis_client.rpop(_history_key(order_code))
    if not raw:
        return None
    item = json.loads(raw)
    staff_code = staff.staff_id if staff is not None else ""
    revert_status_task.delay(
        order_code, item["prev_status"], item["action"], staff_code
    )
    return f"undo {item['action']}"


def pending(redis_client, order_code):
    raw = redis_client.lrange(_history_key(order_code), 0, -1)
    return [json.loads(r) for r in raw]


def active_orders(db):
    from app.infra.models import OrderRow

    rows = (
        db.query(OrderRow)
        .filter(OrderRow.status.in_(_ACTIVE_STATUSES))
        .order_by(OrderRow.id)
        .all()
    )
    return [
        {"order_code": row.code, "table_no": row.table_number, "status": row.status}
        for row in rows
    ]
