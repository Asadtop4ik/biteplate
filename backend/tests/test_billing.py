"""Tests for the billing vertical (FACADE over the STRATEGY pricing engine)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.deps import current_staff, get_db
from app.domain.staff import Cashier, Waiter
from app.infra.repositories import OrderRepo
from app.services import billing
from app.web.routers.billing import router


def make_client(db_session, staff):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff
    return TestClient(app)


def make_order(db, item_code="M10", qty=1):
    """One BBQ Burger (8.50) by default; returns the order code."""
    repo = OrderRepo(db)
    row = repo.create(1, "W01")
    repo.add_item(row, item_code, qty, "")
    db.commit()
    return row.code


def test_build_standard(seeded):
    code = make_order(seeded)
    data = billing.build(seeded, code, "standard", tip=0.0)
    assert data["subtotal"] == 8.50
    assert data["tax"] == 1.02      # 12% of 8.50
    assert data["total"] == 9.52


def test_build_happy_hour_and_loyalty(seeded):
    code = make_order(seeded)
    happy = billing.build(seeded, code, "happy_hour")
    assert happy["subtotal"] == 6.80     # -20%
    assert happy["gross"] == 8.50        # full price of the line items
    assert happy["discount"] == 1.70     # gross - subtotal, so the bill foots
    assert billing.build(seeded, code, "loyalty")["subtotal"] == 5.65   # -10% - 2.00 drink


def test_split(seeded):
    code = make_order(seeded)
    data = billing.build(seeded, code, "standard", tip=0.0)
    per_guest = billing.split(data["bill"], data["order_domain"], 4)
    assert per_guest == round(9.52 / 4, 2)


def test_view_bill_cashier_ok(seeded):
    code = make_order(seeded)
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.get(f"/bill/{code}")
    assert resp.status_code == 200


def test_recalc_reflects_strategy(seeded):
    code = make_order(seeded)
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.post(f"/bill/{code}", data={"strategy": "happy_hour", "tip": 0.0, "guests": 2})
    assert resp.status_code == 200
    assert "6.80" in resp.text


def test_close_bill_cashier_ok(seeded):
    code = make_order(seeded)
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.post(f"/bill/{code}/close")
    assert resp.status_code == 200


def test_view_bill_waiter_forbidden(seeded):
    code = make_order(seeded)
    client = make_client(seeded, Waiter("W01", "Aziz"))
    resp = client.get(f"/bill/{code}")
    assert resp.status_code == 403


def test_bills_list_shows_confirmed_orders(seeded):
    code = make_order(seeded)
    OrderRepo(seeded).set_status(code, "queued")  # leaves NEW -> billable
    seeded.commit()
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.get("/bills")
    assert resp.status_code == 200
    assert code in resp.text


def test_bills_list_waiter_forbidden(seeded):
    client = make_client(seeded, Waiter("W01", "Aziz"))
    resp = client.get("/bills")
    assert resp.status_code == 403
