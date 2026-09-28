"""Server-rendered HTML shells. All data is loaded by the JS from the JSON API."""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.templating import templates

router = APIRouter(include_in_schema=False, default_response_class=HTMLResponse)


@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.get("/recipes/{slug}")
def recipe_page(request: Request, slug: str):
    return templates.TemplateResponse(request, "recipe.html", {"slug": slug})


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@router.get("/upload")
def upload_page(request: Request):
    return templates.TemplateResponse(request, "upload.html")


@router.get("/me")
def profile_page(request: Request):
    return templates.TemplateResponse(request, "profile.html")
