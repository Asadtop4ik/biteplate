"""Tests for the reporting vertical (Singleton history repo + Iterator)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.deps import current_staff, get_db
from app.domain.menu import MenuFactory
from app.domain.orders import Order, OrderItem
from app.domain.staff import Manager, Waiter
from app.infra.repositories import SqlAlchemyHistoryRepository
from app.services import reporting
from app.web.routers.report import router


def _seed_order(table_no, qty):
    o = Order(table_no, "W01")
    o.add_item(OrderItem(MenuFactory.create("main", "M10", "BBQ Burger", 8.5), qty))
    return o


def make_client(db_session, staff):
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[current_staff] = lambda: staff
    return TestClient(app)


def test_revenue_single_order(db_session):
    repo = SqlAlchemyHistoryRepository(db_session)
    repo.append(_seed_order(3, 2))
    assert reporting.revenue(db_session) == 17.0


def test_aggregates_over_two_orders(db_session):
    repo = SqlAlchemyHistoryRepository(db_session)
    repo.append(_seed_order(3, 2))
    assert reporting.summary(db_session)["count"] == 1
    repo.append(_seed_order(5, 1))

    assert reporting.revenue(db_session) == 25.5
    assert reporting.summary(db_session)["count"] == 2

    top = reporting.top_items(db_session)
    assert top[0] == ("BBQ Burger", 3)

    mf = reporting.most_frequent(db_session)
    assert mf[0] == "BBQ Burger"

    assert reporting.last_24h(db_session) == 2

    rows = reporting.for_table(db_session, 5)
    assert len(rows) == 1 and rows[0].table_no == 5


def test_get_report_manager_ok(db_session):
    SqlAlchemyHistoryRepository(db_session).append(_seed_order(3, 2))
    client = make_client(db_session, Manager("M01", "Sardor"))
    resp = client.get("/report")
    assert resp.status_code == 200
    assert "BBQ Burger" in resp.text


def test_get_report_waiter_forbidden(db_session):
    client = make_client(db_session, Waiter("W01", "Aziz"))
    resp = client.get("/report")
    assert resp.status_code == 403


def test_post_report_filters(db_session):
    repo = SqlAlchemyHistoryRepository(db_session)
    repo.append(_seed_order(3, 2))
    repo.append(_seed_order(5, 1))
    client = make_client(db_session, Manager("M01", "Sardor"))
    resp = client.post("/report", data={"table_no": 5, "n": 5})
    assert resp.status_code == 200
    assert 'id="report-table"' in resp.text
