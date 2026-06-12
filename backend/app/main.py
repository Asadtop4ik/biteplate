"""FastAPI application entrypoint: session middleware, static mount, routers.

Sessions are Redis-backed via starsessions. SessionAutoloadMiddleware loads the
session on every request so `request.session` behaves like a dict.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starsessions import SessionAutoloadMiddleware, SessionMiddleware
from starsessions.stores.redis import RedisStore

from app.config import settings
from app.web.htmx import render
from app.web.routers import auth

app = FastAPI(title="BitePlate")

_store = RedisStore(settings.REDIS_URL)
app.add_middleware(SessionAutoloadMiddleware)
app.add_middleware(
    SessionMiddleware,
    store=_store,
    cookie_name=settings.SESSION_COOKIE,
    lifetime=3600,
    cookie_https_only=False,  # dev runs over plain HTTP; tighten in prod
)

_STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

app.include_router(auth.router)

# === feature routers ===
from app.web.routers import billing, kitchen, order, report, seat, sse

app.include_router(seat.router)
app.include_router(order.router)
app.include_router(kitchen.router)
app.include_router(billing.router)
app.include_router(report.router)
app.include_router(sse.router)
# === end feature routers ===


@app.get("/")
def dashboard(request: Request):
    if not request.session.get("staff_code"):
        return RedirectResponse(url="/login", status_code=303)
    role = request.session.get("role", "")
    return render(request, "pages/dashboard.html", "pages/dashboard.html", {"role": role})
