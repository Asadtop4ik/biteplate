"""Ordering service: start an order, add items, summarise, and confirm.

Builds on the Factory/Composite menu (via OrderRepo.to_domain + MenuRepo) and
fires the Observer (RedisPublishObserver) when an order is confirmed, which is
the moment the kitchen needs to know about it.
"""
from app.domain.errors import (
    IllegalStateTransition,
    ValidationError,
    require_positive_int,
)
from app.domain.orders import OrderStatus
from app.infra.events import RedisPublishObserver
from app.infra.repositories import (
    MenuRepo,
    OrderRepo,
    SqlAlchemyHistoryRepository,
)


def start_order(db, table_number, staff_code):
    row = OrderRepo(db).create(table_number, staff_code)
    db.commit()
    return row


def add_item(db, order_code, item_code, qty, notes=""):
    qty = require_positive_int(qty, "qty")
    repo = OrderRepo(db)
    order_row = repo.get(order_code)
    if order_row is None or order_row.status != OrderStatus.NEW.value:
        raise IllegalStateTransition(
            "Cannot add items to an order that is missing or has left NEW state"
        )
    if MenuRepo(db).get(item_code) is None:
        raise ValidationError(f"Unknown menu item: {item_code!r}")
    repo.add_item(order_row, item_code, qty, notes)
    db.commit()
    return order_row


def summary(db, order_code):
    repo = OrderRepo(db)
    order_row = repo.get(order_code)
    order = repo.to_domain(order_row, MenuRepo(db))
    lines = [
        {
            "name": item.menu_item.name,
            "qty": item.qty,
            "notes": item.notes,
            "line_total": item.line_total(),
        }
        for item in order.items
    ]
    return {"order": order_row, "lines": lines, "subtotal": order.total()}


def confirm(db, order_code, redis_client):
    repo = OrderRepo(db)
    order_row = repo.get(order_code)
    order = repo.to_domain(
        order_row, MenuRepo(db), observers=[RedisPublishObserver(redis_client)]
    )
    order.set_status(OrderStatus.QUEUED)
    updated = repo.set_status(order_code, OrderStatus.QUEUED.value)
    SqlAlchemyHistoryRepository(db).append(order)
    return updated
