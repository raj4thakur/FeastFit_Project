from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.constants import CATEGORY_LABELS, CUISINES, DIET_TAGS, DIFFICULTIES, SORT_OPTIONS
from app.database import get_db
from app.exceptions import AppError

router = APIRouter(tags=["Meta"])


@router.get("/api/meta", summary="Allowed values for filters and forms")
def meta():
    return {
        "cuisines": CUISINES,
        "categories": [{"value": k, "label": v} for k, v in CATEGORY_LABELS.items()],
        "difficulties": DIFFICULTIES,
        "diet_tags": DIET_TAGS,
        "sort_options": SORT_OPTIONS,
    }


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Database is not reachable"


@router.get("/health", summary="Liveness + database check (used by Docker / CI / load balancers)")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise ServiceUnavailableError() from exc
    return {"status": "ok", "database": "up"}
