"""Report router: manager-only revenue/top-items view (run_report perm)."""
from fastapi import APIRouter, Depends, Form, Request

from app.deps import get_db, require_permission
from app.services.reporting import for_table, summary, top_items
from app.web.htmx import render

router = APIRouter()


@router.get("/report")
def report_page(
    request: Request,
    db=Depends(get_db),
    staff=Depends(require_permission("run_report")),
):
    return render(request, "pages/report.html", "partials/report_table.html", summary(db))


@router.post("/report")
def report_filter(
    request: Request,
    table_no: int | None = Form(None),
    n: int = Form(5),
    db=Depends(get_db),
    staff=Depends(require_permission("run_report")),
):
    base = summary(db)
    if table_no is not None:
        base["records"] = for_table(db, table_no)
    base["top_items"] = top_items(db, n)
    return render(request, "pages/report.html", "partials/report_table.html", base)
