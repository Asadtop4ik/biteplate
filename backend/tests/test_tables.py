"""Tests for the tables/seat vertical (STATE pattern over persisted rows)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.deps import current_staff, get_db
from app.domain.staff import Cashier, Waiter
from app.infra.repositories import TableRepo
from app.services import tables
from app.web.routers.seat import router


def make_client(db_session, staff):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")  # so base.html request.session works
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff
    return TestClient(app)


def _force_free(db, number):
    TableRepo(db).save_state(number, "Free")
    db.commit()


def test_seat_service_free_to_occupied(seeded):
    _force_free(seeded, 1)
    row = tables.seat(seeded, 1)
    assert row.state == "Occupied"


def test_reserve_service_free_to_reserved(seeded):
    _force_free(seeded, 2)
    row = tables.reserve(seeded, 2)
    assert row.state == "Reserved"


def test_get_tables_lists_all(seeded):
    client = make_client(seeded, Waiter("W01", "Aziz"))
    resp = client.get("/tables")
    assert resp.status_code == 200
    assert resp.text.count("table-card") >= 8


def test_seat_endpoint_waiter_ok(seeded):
    _force_free(seeded, 3)
    client = make_client(seeded, Waiter("W01", "Aziz"))
    resp = client.post("/tables/3/seat")
    assert resp.status_code == 200
    assert "Occupied" in resp.text
    assert TableRepo(seeded).get(3).state == "Occupied"


def test_seat_endpoint_cashier_forbidden(seeded):
    client = make_client(seeded, Cashier("K01", "Lola"))
    resp = client.post("/tables/4/seat")
    assert resp.status_code == 403
