import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import BASE_DIR, DEFAULT_SECRET, get_settings
from app.database import Base, engine
from app.exceptions import register_exception_handlers
from app.routers import auth, meta, pages, recipes, users

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("feastfit")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.is_production and settings.secret_key == DEFAULT_SECRET:
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production")
    Base.metadata.create_all(bind=engine)  # swap for Alembic migrations as the schema grows
    logger.info("%s v%s started (%s)", settings.app_name, settings.app_version, settings.environment)
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    version=settings.app_version,
    description="Diet & recipe platform with an Italian soul. Built by Raj Thakur.",
    lifespan=lifespan,
)

register_exception_handlers(app)

if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def timing_and_logging(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-ms"] = f"{elapsed_ms:.1f}"
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if not request.url.path.startswith(("/static", "/media")):
        logger.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.upload_dir), name="media")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(auth.router)
app.include_router(recipes.router)
app.include_router(users.router)
app.include_router(meta.router)
app.include_router(pages.router)
