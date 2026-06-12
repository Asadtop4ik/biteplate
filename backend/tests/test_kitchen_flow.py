"""Kitchen vertical tests: COMMAND-over-Celery + Observer/Redis publish.

Redis is replaced by a tiny in-process FakeRedis (rpush/rpop/lrange/publish over
a dict of lists) so no network is needed. The Celery tasks normally open their
OWN SessionLocal (Postgres) which is not available under SQLite tests; therefore
the enqueue/undo tests MONKEYPATCH the task ``.delay`` to call the pure
``_apply``/``_revert`` inner functions with the TEST db_session + FakeRedis. The
pure functions themselves are exercised directly with the test session.
"""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import current_staff, get_db
from app.domain.orders import OrderStatus
from app.domain.staff import Cashier, Chef
from app.infra.repositories import OrderRepo
from app.services import kitchen
from app.web.routers.kitchen import router


class FakeRedis:
    """Minimal Redis stand-in covering the list + publish ops we use."""

    def __init__(self):
        self.lists = {}
        self.published = []

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    def rpop(self, key):
        items = self.lists.get(key)
        if not items:
            return None
        return items.pop()

    def lrange(self, key, start, end):
        items = self.lists.get(key, [])
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    def publish(self, channel, message):
        self.published.append((channel, message))
        return 1


def _make_queued_order(db, table_number=1, staff_code="C01"):
    """Create an order with one item, advance it to QUEUED, return its code."""
    repo = OrderRepo(db)
    order_row = repo.create(table_number=table_number, staff_code=staff_code)
    repo.add_item(order_row, "M10", 1, "")
    repo.set_status(order_row.code, OrderStatus.QUEUED.value)
    db.commit()
    return order_row.code


# --- pure _apply / _revert -------------------------------------------------


def test_apply_prepare_sets_cooking(seeded):
    from app.infra.tasks import _apply

    fake = FakeRedis()
    code = _make_queued_order(seeded)

    result = _apply(seeded, code, "prepare", "C01", fake)

    assert OrderRepo(seeded).get(code).status == OrderStatus.COOKING.value
    assert result["prev_status"] == OrderStatus.QUEUED.value
    assert result["new_status"] == OrderStatus.COOKING.value
    # Observer published the status change to the events channel.
    assert any("cooking" in msg for _, msg in fake.published)


def test_apply_expedite_sets_ready(seeded):
    from app.infra.tasks import _apply

    fake = FakeRedis()
    code = _make_queued_order(seeded)

    _apply(seeded, code, "expedite", "C01", fake)

    assert OrderRepo(seeded).get(code).status == OrderStatus.READY.value


# --- enqueue / undo with monkeypatched task delay --------------------------


def test_enqueue_pushes_history_and_dispatches(seeded, monkeypatch):
    """enqueue records one undo entry and (eager) runs the inner _apply."""
    from app.infra import tasks

    fake = FakeRedis()
    code = _make_queued_order(seeded)

    # Redirect the Celery task .delay to call the pure inner function with the
    # TEST session + FakeRedis (the real task would open a Postgres SessionLocal).
    monkeypatch.setattr(
        tasks.prepare_order_task,
        "delay",
        lambda order_code, staff_code: tasks._apply(
            seeded, order_code, "prepare", staff_code, fake
        ),
    )

    out = kitchen.enqueue(seeded, "prepare", code, Chef("C01", "Bek"), fake)

    assert out == {"dispatched": "prepare", "order_code": code}
    # exactly one undo-history entry, recording the prior QUEUED status
    history = fake.lists[f"kitchen:history:{code}"]
    assert len(history) == 1
    assert json.loads(history[0])["prev_status"] == OrderStatus.QUEUED.value
    # the dispatched task advanced the order
    assert OrderRepo(seeded).get(code).status == OrderStatus.COOKING.value


def test_undo_last_pops_and_reverts(seeded, monkeypatch):
    from app.infra import tasks

    fake = FakeRedis()
    code = _make_queued_order(seeded)

    monkeypatch.setattr(
        tasks.prepare_order_task,
        "delay",
        lambda order_code, staff_code: tasks._apply(
            seeded, order_code, "prepare", staff_code, fake
        ),
    )
    monkeypatch.setattr(
        tasks.revert_status_task,
        "delay",
        lambda order_code, prev_status, action, staff_code="": tasks._revert(
            seeded, order_code, prev_status, action, fake
        ),
    )

    kitchen.enqueue(seeded, "prepare", code, Chef("C01", "Bek"), fake)
    assert OrderRepo(seeded).get(code).status == OrderStatus.COOKING.value

    label = kitchen.undo_last(seeded, code, fake)

    assert label == "undo prepare"
    assert OrderRepo(seeded).get(code).status == OrderStatus.QUEUED.value
    # history list is now empty
    assert fake.lists[f"kitchen:history:{code}"] == []


def test_undo_last_returns_none_when_empty(seeded):
    fake = FakeRedis()
    assert kitchen.undo_last(seeded, "ORD-9999", fake) is None


def test_pending_lists_entries(seeded):
    fake = FakeRedis()
    code = "ORD-0001"
    fake.rpush(
        f"kitchen:history:{code}",
        json.dumps({"action": "prepare", "prev_status": "queued"}),
    )
    out = kitchen.pending(fake, code)
    assert out == [{"action": "prepare", "prev_status": "queued"}]


def test_active_orders_filters_in_flight(seeded):
    code = _make_queued_order(seeded)
    cards = kitchen.active_orders(seeded)
    assert {"order_code": code, "table_no": 1, "status": "queued"} in cards


# --- endpoint permission gating --------------------------------------------


def _make_client(db_session, staff):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff
    return TestClient(app)


def test_action_forbidden_for_cashier(seeded, monkeypatch):
    # enqueue must never run for a forbidden request; stub it to be safe.
    monkeypatch.setattr(kitchen, "enqueue", lambda *a, **k: pytest.fail("must not enqueue"))
    client = _make_client(seeded, Cashier("K01", "Lola"))
    resp = client.post("/kitchen/ORD-0001/prepare")
    assert resp.status_code == 403


def test_action_allowed_for_chef(seeded, monkeypatch):
    # Avoid hitting Postgres: stub enqueue so the route just returns its flash.
    calls = {}
    monkeypatch.setattr(
        kitchen,
        "enqueue",
        lambda db, action, code, staff, rc: calls.update(action=action, code=code),
    )
    client = _make_client(seeded, Chef("C01", "Bek"))
    resp = client.post("/kitchen/ORD-0001/prepare")
    assert resp.status_code == 200
    assert "Prepare dispatched" in resp.text
    assert calls == {"action": "prepare", "code": "ORD-0001"}


def test_unknown_action_rejected(seeded):
    client = _make_client(seeded, Chef("C01", "Bek"))
    resp = client.post("/kitchen/ORD-0001/frobnicate")
    assert resp.status_code == 400


def test_undo_route_reaches_handler(seeded, monkeypatch):
    """Regression: /kitchen/{code}/undo must NOT be shadowed by /{action}."""
    monkeypatch.setattr(
        kitchen, "undo_last", lambda db, code, rc, staff=None: "undo prepare"
    )
    client = _make_client(seeded, Chef("C01", "Bek"))
    resp = client.post("/kitchen/ORD-0001/undo")
    assert resp.status_code == 200
    assert "undo prepare" in resp.text
