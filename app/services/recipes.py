import math
import re
import unicodedata

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.models import Favorite, Ingredient, Recipe, Review, Step, User
from app.schemas import RecipeCreate, RecipeDetail, RecipeUpdate

_NULLABLE_FIELDS = {"calories", "protein_g", "carbs_g", "fat_g"}
_SIMPLE_FIELDS = {
    "title", "description", "cuisine", "category", "difficulty",
    "prep_minutes", "cook_minutes", "servings", "calories", "protein_g", "carbs_g", "fat_g",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text[:120] or "recipe"


def unique_slug(db: Session, title: str, exclude_id: int | None = None) -> str:
    base = slugify(title)
    slug, n = base, 2
    while True:
        existing = db.scalar(select(Recipe.id).where(Recipe.slug == slug))
        if existing is None or existing == exclude_id:
            return slug
        slug = f"{base}-{n}"
        n += 1


def _full_load():
    return (
        joinedload(Recipe.author),
        selectinload(Recipe.ingredients),
        selectinload(Recipe.steps),
        selectinload(Recipe.reviews).joinedload(Review.user),
    )


def get_recipe_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.scalar(select(Recipe).where(Recipe.id == recipe_id).options(*_full_load()))
    if recipe is None:
        raise NotFoundError("Recipe not found")
    return recipe


def get_recipe_by_slug_or_404(db: Session, slug: str) -> Recipe:
    recipe = db.scalar(select(Recipe).where(Recipe.slug == slug).options(*_full_load()))
    if recipe is None:
        raise NotFoundError("Recipe not found")
    return recipe


def ensure_can_modify(user: User, recipe: Recipe) -> None:
    if recipe.author_id != user.id and not user.is_admin:
        raise PermissionDeniedError("Only the author can change this recipe")


def build_detail(db: Session, recipe: Recipe, user: User | None) -> RecipeDetail:
    detail = RecipeDetail.model_validate(recipe)
    if user is not None:
        detail.is_favorite = db.get(Favorite, (user.id, recipe.id)) is not None
    return detail


def _make_ingredients(data) -> list[Ingredient]:
    return [
        Ingredient(position=i, name=item.name.strip(), quantity=item.quantity.strip())
        for i, item in enumerate(data, start=1)
    ]


def _make_steps(data) -> list[Step]:
    return [Step(position=i, instruction=item.instruction.strip()) for i, item in enumerate(data, start=1)]


def create_recipe(db: Session, author: User, data: RecipeCreate) -> Recipe:
    recipe = Recipe(
        title=data.title.strip(),
        slug=unique_slug(db, data.title),
        description=data.description.strip(),
        cuisine=data.cuisine,
        category=data.category,
        difficulty=data.difficulty,
        prep_minutes=data.prep_minutes,
        cook_minutes=data.cook_minutes,
        servings=data.servings,
        calories=data.calories,
        protein_g=data.protein_g,
        carbs_g=data.carbs_g,
        fat_g=data.fat_g,
        author_id=author.id,
    )
    recipe.diet_tags = data.diet_tags
    recipe.ingredients = _make_ingredients(data.ingredients)
    recipe.steps = _make_steps(data.steps)
    db.add(recipe)
    db.commit()
    return get_recipe_or_404(db, recipe.id)


def update_recipe(db: Session, recipe: Recipe, data: RecipeUpdate) -> Recipe:
    changes = data.model_dump(exclude_unset=True)

    for field in _SIMPLE_FIELDS & changes.keys():
        value = changes[field]
        if value is None and field not in _NULLABLE_FIELDS:
            continue  # required columns can't be nulled out
        setattr(recipe, field, value.strip() if isinstance(value, str) else value)

    if changes.get("diet_tags") is not None:
        recipe.diet_tags = changes["diet_tags"]
    if data.ingredients is not None:
        recipe.ingredients = _make_ingredients(data.ingredients)
    if data.steps is not None:
        recipe.steps = _make_steps(data.steps)

    db.commit()
    db.expire(recipe)  # force a fresh reload of relationships / updated_at
    return get_recipe_or_404(db, recipe.id)


def delete_recipe(db: Session, recipe: Recipe) -> None:
    db.delete(recipe)
    db.commit()


def list_recipes(
    db: Session,
    *,
    q: str | None = None,
    cuisine: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    diet: str | None = None,
    max_minutes: int | None = None,
    max_calories: int | None = None,
    author_id: int | None = None,
    sort: str = "newest",
    page: int = 1,
    size: int = 12,
) -> tuple[list[Recipe], int]:
    stmt = select(Recipe)

    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Recipe.title).like(like),
                func.lower(Recipe.description).like(like),
                Recipe.ingredients.any(func.lower(Ingredient.name).like(like)),
            )
        )
    if cuisine:
        stmt = stmt.where(Recipe.cuisine == cuisine.lower())
    if category:
        stmt = stmt.where(Recipe.category == category.lower())
    if difficulty:
        stmt = stmt.where(Recipe.difficulty == difficulty.lower())
    if diet:
        stmt = stmt.where(Recipe.diet_tags_raw.like(f"%,{diet.lower()},%"))
    total_time = Recipe.prep_minutes + Recipe.cook_minutes
    if max_minutes is not None:
        stmt = stmt.where(total_time <= max_minutes)
    if max_calories is not None:
        stmt = stmt.where(Recipe.calories.is_not(None), Recipe.calories <= max_calories)
    if author_id is not None:
        stmt = stmt.where(Recipe.author_id == author_id)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    order = {
        "newest": (Recipe.created_at.desc(), Recipe.id.desc()),
        "oldest": (Recipe.created_at.asc(), Recipe.id.asc()),
        "quickest": (total_time.asc(), Recipe.id.desc()),
        "lightest": (Recipe.calories.asc(), Recipe.id.desc()),
        "az": (func.lower(Recipe.title).asc(), Recipe.id.asc()),
    }.get(sort, (Recipe.created_at.desc(), Recipe.id.desc()))

    items = db.scalars(
        stmt.order_by(*order)
        .offset((page - 1) * size)
        .limit(size)
        .options(joinedload(Recipe.author), selectinload(Recipe.reviews))
    ).all()
    return list(items), total


def page_count(total: int, size: int) -> int:
    return max(1, math.ceil(total / size)) if total else 0


# ------------------------------------------------------------------ favorites


def add_favorite(db: Session, user: User, recipe: Recipe) -> None:
    if db.get(Favorite, (user.id, recipe.id)) is None:
        db.add(Favorite(user_id=user.id, recipe_id=recipe.id))
        db.commit()


def remove_favorite(db: Session, user: User, recipe: Recipe) -> None:
    favorite = db.get(Favorite, (user.id, recipe.id))
    if favorite is not None:
        db.delete(favorite)
        db.commit()


def list_favorites(db: Session, user: User) -> list[Recipe]:
    stmt = (
        select(Recipe)
        .join(Favorite, Favorite.recipe_id == Recipe.id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
        .options(joinedload(Recipe.author), selectinload(Recipe.reviews))
    )
    return list(db.scalars(stmt).all())


# ------------------------------------------------------------------ reviews


def upsert_review(db: Session, user: User, recipe: Recipe, rating: int, comment: str) -> tuple[Review, bool]:
    """Create or update the user's single review. Returns (review, created)."""
    if recipe.author_id == user.id:
        raise PermissionDeniedError("You cannot review your own recipe")
    review = db.scalar(select(Review).where(Review.user_id == user.id, Review.recipe_id == recipe.id))
    created = review is None
    if created:
        review = Review(user_id=user.id, recipe_id=recipe.id, rating=rating, comment=comment.strip())
        db.add(review)
    else:
        review.rating = rating
        review.comment = comment.strip()
    try:
        db.commit()
    except Exception as exc:  # concurrent double-submit hit the unique constraint
        db.rollback()
        raise ConflictError("Review already exists") from exc
    db.refresh(review)
    return review, created
