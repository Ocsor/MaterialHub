"""Login and logout routes."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import authenticate_user, current_user
from ..main_paths import TEMPLATES_DIR

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/login")
def login_page(request: Request, next: str = "/materials"):
    if current_user(request) is not None:
        return RedirectResponse(next if next.startswith("/") else "/materials", status_code=303)
    return templates.TemplateResponse(request, "login.html", {
        "next": next if next.startswith("/") else "/materials",
        "auth_user": None,
    })


@router.post("/login")
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/materials",
):
    user = authenticate_user(username.strip(), password)
    safe_next = next if next.startswith("/") else "/materials"
    if user is None:
        return templates.TemplateResponse(request, "login.html", {
            "next": safe_next,
            "error": "Invalid username or password",
            "auth_user": None,
        }, status_code=401)

    request.session.clear()
    request.session["user"] = user.username
    request.session["role"] = user.role
    return RedirectResponse(safe_next, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
