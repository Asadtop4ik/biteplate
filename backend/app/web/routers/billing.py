"""Billing router: view a bill (with a pricing STRATEGY), recalc and close it."""
from fastapi import APIRouter, Depends, Form, Request

from app.deps import get_db, require_permission
from app.services import billing
from app.web.htmx import render

router = APIRouter()


@router.get("/bills")
def bills_list(
    request: Request,
    db=Depends(get_db),
    staff=Depends(require_permission("view_bill")),
):
    return render(
        request,
        "pages/bills.html",
        "pages/bills.html",
        {"orders": billing.list_billable(db)},
    )


@router.get("/bill/{code}")
def view_bill(
    request: Request,
    code: str,
    db=Depends(get_db),
    staff=Depends(require_permission("view_bill")),
):
    ctx = billing.build(db, code)
    return render(request, "pages/bill.html", "partials/bill_doc.html", ctx)


@router.post("/bill/{code}")
def recalc_bill(
    request: Request,
    code: str,
    strategy: str = Form("standard"),
    tip: float = Form(0.0),
    guests: int = Form(1),
    db=Depends(get_db),
    staff=Depends(require_permission("view_bill")),
):
    data = billing.build(db, code, strategy, tip)
    data["per_guest"] = billing.split(data["bill"], data["order_domain"], guests)
    data["guests"] = guests
    return render(request, "partials/bill_doc.html", "partials/bill_doc.html", data)


@router.post("/bill/{code}/close")
def close_bill(
    request: Request,
    code: str,
    db=Depends(get_db),
    staff=Depends(require_permission("close_bill")),
):
    table = billing.close(db, code)
    return render(
        request,
        "partials/flash.html",
        "partials/flash.html",
        {"message": f"Bill closed; table advanced to {table.state}", "level": "info"},
    )
