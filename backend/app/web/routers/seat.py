"""Seat/Tables router: full board page + per-card HTMX transitions.

The board lists every table as a card; seat/reserve/advance each apply a domain
STATE transition and return the single updated table_card partial, which swaps
itself in place (hx-swap='outerHTML'). Domain BitePlateError -> 400 flash.
"""
from fastapi import APIRouter, Depends, Request

from app.deps import current_staff, get_db, require_permission
from app.domain.errors import BitePlateError
from app.services import tables
from app.web.htmx import render, templates

router = APIRouter()


@router.get("/tables")
def board(request: Request, staff=Depends(current_staff), db=Depends(get_db)):
    return render(
        request,
        "pages/tables.html",
        "pages/tables.html",
        {"tables": tables.list_tables(db)},
    )


def _card_or_flash(request, action, number):
    try:
        row = action(number)
    except BitePlateError as e:
        return templates.TemplateResponse(
            request,
            "partials/flash.html",
            {"message": str(e), "level": "error"},
            status_code=400,
        )
    return render(
        request,
        "partials/table_card.html",
        "partials/table_card.html",
        {"table": row},
    )


@router.post("/tables/{number}/seat")
def seat(
    request: Request,
    number: int,
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    return _card_or_flash(request, lambda n: tables.seat(db, n), number)


@router.post("/tables/{number}/reserve")
def reserve(
    request: Request,
    number: int,
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    return _card_or_flash(request, lambda n: tables.reserve(db, n), number)


@router.post("/tables/{number}/advance")
def advance(
    request: Request,
    number: int,
    staff=Depends(require_permission("take_order")),
    db=Depends(get_db),
):
    return _card_or_flash(request, lambda n: tables.advance(db, n), number)
