"""Ordering vertical tests: service (start/add/summary/confirm) and endpoints.

A FakeRedis avoids any network in confirm() — the Observer only needs .publish.
Endpoint tests use the self-contained make_client pattern so the feature router
is exercised without app.main wiring.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.deps import current_staff, get_db
from app.domain.errors import IllegalStateTransition
from app.domain.staff import Cashier, Waiter
from app.infra.repositories import SqlAlchemyHistoryRepository
from app.services import ordering
from app.web.routers.order import router


class FakeRedis:
    def publish(self, *args, **kwargs):
        pass


def make_client(db_session, staff):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff
    return TestClient(app)


def test_start_order_creates_first_code(seeded):
    row = ordering.start_order(seeded, 1, "W01")
    assert row.code == "ORD-0001"
    assert row.status == "new"


def test_add_item_subtotal_and_summary(seeded):
    code = ordering.start_order(seeded, 1, "W01").code
    ordering.add_item(seeded, code, "M10", 2)
    result = ordering.summary(seeded, code)
    assert result["subtotal"] == 17.00
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line["name"] == "BBQ Burger"
    assert line["qty"] == 2
    assert line["line_total"] == 17.00


def test_confirm_sets_queued_and_appends_history(seeded):
    history = SqlAlchemyHistoryRepository(seeded)
    before = len(history)
    code = ordering.start_order(seeded, 1, "W01").code
    ordering.add_item(seeded, code, "M10", 2)
    updated = ordering.confirm(seeded, code, FakeRedis())
    assert updated.status == "queued"
    assert len(history) == before + 1
    assert history.total_revenue() > 0


def test_add_item_on_non_new_order_raises(seeded):
    code = ordering.start_order(seeded, 1, "W01").code
    ordering.add_item(seeded, code, "M10", 1)
    ordering.confirm(seeded, code, FakeRedis())
    with pytest.raises(IllegalStateTransition):
        ordering.add_item(seeded, code, "M10", 1)


def test_endpoint_start_as_waiter_ok(seeded):
    client = make_client(seeded, Waiter("W01", "Aziz"))
    resp = client.post("/order/start", data={"table_number": 1})
    assert resp.status_code == 200
    assert "ORD-0001" in resp.text


def test_endpoint_start_as_cashier_forbidden(seeded):
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.post("/order/start", data={"table_number": 1})
    assert resp.status_code == 403
