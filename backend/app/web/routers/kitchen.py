"""Kitchen board router: HTMX page + per-order command actions.

The GET page renders the live board (initial card list + an SSE feed). The
action POST maps the URL action to a permission, enforces it via the domain
``staff.require(perm)``, then dispatches the Celery command through the kitchen
service. Each action returns a small flash partial swapped into the page.
"""
from fastapi import APIRouter, Depends, Request

from app.deps import current_staff, get_db, get_redis, require_permission
from app.domain.errors import PermissionDenied
from app.services import kitchen
from app.web.htmx import render, templates

router = APIRouter()

_FLASH_LABELS = {
    "prepare": "Prepare dispatched",
    "cancel": "Cancel dispatched",
    "expedite": "Expedite dispatched",
}


def _flash(request, message, level="success", status_code=200):
    return templates.TemplateResponse(
        request,
        "partials/flash.html",
        {"message": message, "level": level},
        status_code=status_code,
    )


@router.get("/kitchen")
def kitchen_page(
    request: Request,
    staff=Depends(require_permission("view_kitchen")),
    db=Depends(get_db),
):
    return render(
        request,
        "pages/kitchen.html",
        "pages/kitchen.html",
        {"orders": kitchen.active_orders(db)},
    )


# NOTE: the specific /undo route MUST be registered before the generic
# /{action} catch-all, otherwise "undo" matches {action} and never reaches here.
@router.post("/kitchen/{code}/undo")
def kitchen_undo(
    request: Request,
    code: str,
    staff=Depends(require_permission("prepare")),
    db=Depends(get_db),
):
    label = kitchen.undo_last(db, code, get_redis(), staff)
    if label is None:
        return _flash(request, f"Nothing to undo for {code}", "info")
    return _flash(request, f"{label} for {code}")


@router.post("/kitchen/{code}/{action}")
def kitchen_action(
    request: Request,
    code: str,
    action: str,
    staff=Depends(current_staff),
    db=Depends(get_db),
):
    perm = kitchen.ACTION_PERM.get(action)
    if perm is None:
        return _flash(request, f"Unknown action '{action}'", "error", status_code=400)
    try:
        staff.require(perm)
    except PermissionDenied as e:
        return _flash(request, str(e), "error", status_code=403)
    kitchen.enqueue(db, action, code, staff, get_redis())
    return _flash(request, f"{_FLASH_LABELS[action]} for {code}")
