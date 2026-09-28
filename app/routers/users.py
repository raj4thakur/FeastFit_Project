from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import RecipeSummary
from app.services import recipes as svc

router = APIRouter(prefix="/api/users/me", tags=["My account"])


@router.get("/recipes", response_model=list[RecipeSummary], summary="Recipes I published")
def my_recipes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, _ = svc.list_recipes(db, author_id=user.id, size=50)
    return [RecipeSummary.model_validate(r) for r in items]


@router.get("/favorites", response_model=list[RecipeSummary], summary="Recipes I saved")
def my_favorites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [RecipeSummary.model_validate(r) for r in svc.list_favorites(db, user)]
