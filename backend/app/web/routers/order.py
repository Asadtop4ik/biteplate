"""Ordering router (Factory + Composite menu, Observer fired on confirm).

UX: the menu picker lives in the order_summary partial. The page starts with an
empty #order-summary; once an order is started the returned partial carries the
order code, so every menu "Add" button can hx-post to /order/{code}/item. When
the order leaves NEW state the add/confirm controls disappear.
"""
from fastapi import APIRouter, Depends, Form, Request

from app.deps import current_staff, get_db, get_redis, require_permission
from app.domain.errors import BitePlateError
from app.infra.repositories import MenuRepo, TableRepo
from app.services import ordering
from app.web.htmx import render, templates

router = APIRouter()


def _summary_ctx(request, db, code):
    ctx = ordering.summary(db, code)
    ctx["request"] = request
    ctx["menu"] = MenuRepo(db).list_items()
    return ctx


@router.get("/order")
def order_page(request: Request, staff=Depends(current_staff), db=Depends(get_db)):
    return render(
        request,
        "pages/order.html",
        "pages/order.html",
        {
            "menu": MenuRepo(db).list_items(),
            "tables": TableRepo(db).list_all(),
        },
    )


@router.post("/order/start")
def order_start(
    request: Request,
    table_number: int = Form(...),
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    row = ordering.start_order(db, table_number, staff.staff_id)
    return templates.TemplateResponse(
        request, "partials/order_summary.html", _summary_ctx(request, db, row.code)
    )


@router.post("/order/{code}/item")
def order_add_item(
    request: Request,
    code: str,
    item_code: str = Form(...),
    qty: int = Form(1),
    notes: str = Form(""),
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    try:
        ordering.add_item(db, code, item_code, qty, notes)
    except BitePlateError as exc:
        return templates.TemplateResponse(
            request,
            "partials/flash.html",
            {"message": str(exc), "level": "error"},
            status_code=400,
        )
    return templates.TemplateResponse(
        request, "partials/order_summary.html", _summary_ctx(request, db, code)
    )


@router.post("/order/{code}/confirm")
def order_confirm(
    request: Request,
    code: str,
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    ordering.confirm(db, code, get_redis())
    return templates.TemplateResponse(
        request, "partials/order_summary.html", _summary_ctx(request, db, code)
    )
