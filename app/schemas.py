from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

from app.constants import CATEGORIES, CUISINES, DIET_TAGS, DIFFICULTIES

# ---------------------------------------------------------------- auth / users


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("must contain at least one letter and one number")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------- recipes

_CHOICES = {"cuisine": CUISINES, "category": CATEGORIES, "difficulty": DIFFICULTIES}


class IngredientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: str = Field(default="", max_length=60)


class StepIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    name: str
    quantity: str


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    instruction: str


class _RecipeValidators(BaseModel):
    @field_validator("cuisine", "category", "difficulty", check_fields=False)
    @classmethod
    def _check_choice(cls, v: str | None, info: ValidationInfo):
        if v is None:
            return v
        v = v.strip().lower()
        allowed = _CHOICES[info.field_name]
        if v not in allowed:
            raise ValueError(f"must be one of: {', '.join(allowed)}")
        return v

    @field_validator("diet_tags", check_fields=False)
    @classmethod
    def _check_tags(cls, v: list[str] | None):
        if v is None:
            return v
        cleaned: list[str] = []
        for tag in v:
            tag = tag.strip().lower()
            if tag not in DIET_TAGS:
                raise ValueError(f"unknown diet tag '{tag}'. Allowed: {', '.join(DIET_TAGS)}")
            if tag not in cleaned:
                cleaned.append(tag)
        return cleaned


class RecipeCreate(_RecipeValidators):
    title: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    cuisine: str = "italian"
    category: str
    difficulty: str = "easy"
    diet_tags: list[str] = Field(default_factory=list, max_length=8)
    prep_minutes: int = Field(default=0, ge=0, le=1440)
    cook_minutes: int = Field(default=0, ge=0, le=2880)
    servings: int = Field(default=2, ge=1, le=100)
    calories: int | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=500)
    carbs_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=500)
    ingredients: list[IngredientIn] = Field(min_length=1, max_length=60)
    steps: list[StepIn] = Field(min_length=1, max_length=60)


class RecipeUpdate(_RecipeValidators):
    """Partial update: only the fields you send are changed."""

    title: str | None = Field(default=None, min_length=3, max_length=160)
    description: str | None = Field(default=None, min_length=10, max_length=4000)
    cuisine: str | None = None
    category: str | None = None
    difficulty: str | None = None
    diet_tags: list[str] | None = Field(default=None, max_length=8)
    prep_minutes: int | None = Field(default=None, ge=0, le=1440)
    cook_minutes: int | None = Field(default=None, ge=0, le=2880)
    servings: int | None = Field(default=None, ge=1, le=100)
    calories: int | None = Field(default=None, ge=0, le=5000)
    protein_g: float | None = Field(default=None, ge=0, le=500)
    carbs_g: float | None = Field(default=None, ge=0, le=1000)
    fat_g: float | None = Field(default=None, ge=0, le=500)
    ingredients: Annotated[list[IngredientIn], Field(min_length=1, max_length=60)] | None = None
    steps: Annotated[list[StepIn], Field(min_length=1, max_length=60)] | None = None


class RecipeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str
    cuisine: str
    category: str
    difficulty: str
    diet_tags: list[str]
    prep_minutes: int
    cook_minutes: int
    total_minutes: int
    servings: int
    calories: int | None
    image_url: str | None
    thumb_url: str | None
    author_name: str
    avg_rating: float | None
    review_count: int
    created_at: datetime


class RecipeDetail(RecipeSummary):
    author_id: int
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    ingredients: list[IngredientOut]
    steps: list[StepOut]
    is_favorite: bool = False
    updated_at: datetime


class RecipePage(BaseModel):
    items: list[RecipeSummary]
    total: int
    page: int
    size: int
    pages: int


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rating: int
    comment: str
    username: str
    created_at: datetime
