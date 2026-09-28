from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.constants import SORT_OPTIONS
from app.database import get_db
from app.deps import get_current_user, get_optional_user
from app.models import User
from app.schemas import (
    RecipeCreate,
    RecipeDetail,
    RecipePage,
    RecipeSummary,
    RecipeUpdate,
    ReviewIn,
    ReviewOut,
)
from app.services import images
from app.services import recipes as svc

router = APIRouter(prefix="/api/recipes", tags=["Recipes"])


@router.get("", response_model=RecipePage, summary="Search and filter recipes")
def list_recipes(
    q: str | None = Query(None, max_length=100, description="Search title, description, ingredients"),
    cuisine: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    diet: str | None = Query(None, description="e.g. vegan, gluten-free"),
    max_minutes: int | None = Query(None, ge=1, description="Total time limit"),
    max_calories: int | None = Query(None, ge=1, description="Calories per serving limit"),
    sort: str = Query("newest", pattern=f"^({'|'.join(SORT_OPTIONS)})$"),
    page: int = Query(1, ge=1),
    size: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    items, total = svc.list_recipes(
        db, q=q, cuisine=cuisine, category=category, difficulty=difficulty, diet=diet,
        max_minutes=max_minutes, max_calories=max_calories, sort=sort, page=page, size=size,
    )
    return RecipePage(
        items=[RecipeSummary.model_validate(r) for r in items],
        total=total,
        page=page,
        size=size,
        pages=svc.page_count(total, size),
    )


@router.post("", response_model=RecipeDetail, status_code=201, summary="Publish a recipe")
def create_recipe(
    data: RecipeCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    recipe = svc.create_recipe(db, user, data)
    return svc.build_detail(db, recipe, user)


@router.get("/slug/{slug}", response_model=RecipeDetail, summary="Get a recipe by its slug")
def get_by_slug(
    slug: str, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)
):
    return svc.build_detail(db, svc.get_recipe_by_slug_or_404(db, slug), user)


@router.get("/{recipe_id}", response_model=RecipeDetail, summary="Get a recipe by id")
def get_recipe(
    recipe_id: int, user: User | None = Depends(get_optional_user), db: Session = Depends(get_db)
):
    return svc.build_detail(db, svc.get_recipe_or_404(db, recipe_id), user)


@router.patch("/{recipe_id}", response_model=RecipeDetail, summary="Edit your recipe")
def update_recipe(
    recipe_id: int,
    data: RecipeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = svc.get_recipe_or_404(db, recipe_id)
    svc.ensure_can_modify(user, recipe)
    recipe = svc.update_recipe(db, recipe, data)
    return svc.build_detail(db, recipe, user)


@router.delete("/{recipe_id}", status_code=204, summary="Delete your recipe")
def delete_recipe(
    recipe_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    recipe = svc.get_recipe_or_404(db, recipe_id)
    svc.ensure_can_modify(user, recipe)
    image_path, thumb_path = recipe.image_path, recipe.thumb_path
    svc.delete_recipe(db, recipe)
    images.delete_image_files(image_path, thumb_path)
    return Response(status_code=204)


@router.post("/{recipe_id}/image", response_model=RecipeDetail, summary="Upload / replace the photo")
def upload_image(
    recipe_id: int,
    file: UploadFile = File(..., description="JPEG, PNG or WebP, min 600x400px"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = svc.get_recipe_or_404(db, recipe_id)
    svc.ensure_can_modify(user, recipe)
    new_image, new_thumb = images.save_upload(file)
    old_image, old_thumb = recipe.image_path, recipe.thumb_path
    recipe.image_path, recipe.thumb_path = new_image, new_thumb
    db.commit()
    images.delete_image_files(old_image, old_thumb)
    return svc.build_detail(db, recipe, user)


# ---------------------------------------------------------------- favorites


@router.post("/{recipe_id}/favorite", status_code=204, summary="Save to favorites")
def favorite(recipe_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.add_favorite(db, user, svc.get_recipe_or_404(db, recipe_id))
    return Response(status_code=204)


@router.delete("/{recipe_id}/favorite", status_code=204, summary="Remove from favorites")
def unfavorite(recipe_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    svc.remove_favorite(db, user, svc.get_recipe_or_404(db, recipe_id))
    return Response(status_code=204)


# ---------------------------------------------------------------- reviews


@router.get("/{recipe_id}/reviews", response_model=list[ReviewOut], summary="List reviews")
def list_reviews(recipe_id: int, db: Session = Depends(get_db)):
    return svc.get_recipe_or_404(db, recipe_id).reviews


@router.post(
    "/{recipe_id}/reviews",
    response_model=ReviewOut,
    status_code=201,
    summary="Rate a recipe (creates, or updates your existing review)",
)
def review_recipe(
    recipe_id: int,
    data: ReviewIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = svc.get_recipe_or_404(db, recipe_id)
    review, created = svc.upsert_review(db, user, recipe, data.rating, data.comment)
    if not created:
        response.status_code = 200
    return review
