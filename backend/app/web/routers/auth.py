"""Auth router: login page, login/logout actions.

Session is the single source of truth: a successful login stores `staff_code`
(and `role` for the navbar). `current_staff` rebuilds the domain Staff from it.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.deps import get_db
from app.services.auth import authenticate
from app.web.htmx import templates

router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if request.session.get("staff_code"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "pages/login.html")


@router.post("/login")
def login(
    request: Request,
    code: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db),
):
    row = authenticate(db, code, password)
    if row is None:
        return templates.TemplateResponse(
            request,
            "pages/login.html",
            {
                "error": True,
                "message": "Invalid staff code or password.",
                "level": "error",
            },
            status_code=401,
        )
    request.session["staff_code"] = row.staff_code
    request.session["role"] = row.role
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
