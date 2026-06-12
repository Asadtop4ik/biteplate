"""Auth vertical tests: login page, login/logout, and the permission dependency.

`client` (from conftest) overrides only get_db, so the real session middleware
and the real `current_staff`/`require_permission` chain are exercised end to end.
The permission-dependency cases use a fresh minimal app to isolate the dependency.
"""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware as CookieSessionMiddleware

from app.deps import current_staff, require_permission
from app.domain.staff import Cashier
from tests.conftest import login


def test_login_page_renders(client, seeded):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert 'type="password"' in resp.text


def test_login_success_sets_session_and_dashboard_ok(client, seeded):
    resp = login(client, "M01", "manager")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"

    # Session cookie now lets us reach the dashboard.
    home = client.get("/")
    assert home.status_code == 200


def test_login_bad_password_does_not_authenticate(client, seeded):
    resp = login(client, "M01", "wrong-password")
    assert resp.status_code == 401
    assert "staff_code" not in client.cookies or resp.headers.get("location") != "/"

    # Confirm not logged in: dashboard redirects back to /login.
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"] == "/login"


def test_logout_clears_session(client, seeded):
    login(client, "M01", "manager")
    assert client.get("/").status_code == 200

    out = client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/login"

    home = client.get("/", follow_redirects=False)
    assert home.status_code == 303
    assert home.headers["location"] == "/login"


def _protected_app():
    app = FastAPI()
    # Plain signed-cookie session (no Redis) so `request.session` is a dict.
    app.add_middleware(CookieSessionMiddleware, secret_key="test")

    @app.get("/protected")
    def protected(staff=Depends(require_permission("prepare"))):
        return {"ok": True}

    return app


def test_protected_route_without_login_is_401():
    app = _protected_app()
    with TestClient(app) as c:
        resp = c.get("/protected")
    assert resp.status_code == 401


def test_cashier_lacks_prepare_permission_is_403():
    app = _protected_app()
    app.dependency_overrides[current_staff] = lambda: Cashier("K01", "Lola")
    with TestClient(app) as c:
        resp = c.get("/protected")
    assert resp.status_code == 403
    app.dependency_overrides.clear()
