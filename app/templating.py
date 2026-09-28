from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, get_settings

settings = get_settings()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["app_version"] = settings.app_version
