"""HTMX rendering helper: full page vs partial based on the HX-Request header.

`templates` is the shared Jinja2Templates instance; other modules (e.g. SSE)
import it to fetch individual templates via `templates.get_template(...)`.
"""
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"


def render(request: Request, page: str, partial: str, ctx: dict | None = None) -> HTMLResponse:
    tmpl = partial if is_htmx(request) else page
    return templates.TemplateResponse(request, tmpl, ctx or {})
