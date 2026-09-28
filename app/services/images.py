"""Image upload pipeline: validate -> fix orientation -> resize -> store as WebP (+ thumbnail)."""
import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import get_settings
from app.exceptions import (
    FileTooLargeError,
    UnsupportedMediaError,
    ValidationFailedError,
)

settings = get_settings()

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAIN_MAX_SIZE = (1600, 1600)
THUMB_SIZE = (640, 480)


def _recipes_dir() -> Path:
    folder = Path(settings.upload_dir) / "recipes"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def store_image(img: Image.Image) -> tuple[str, str]:
    """Save a PIL image as a full-size WebP and a 4:3 thumbnail. Returns relative paths."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    name = uuid.uuid4().hex
    folder = _recipes_dir()

    main = img.copy()
    main.thumbnail(MAIN_MAX_SIZE, Image.Resampling.LANCZOS)
    main.save(folder / f"{name}.webp", "WEBP", quality=88, method=4)

    thumb = ImageOps.fit(img, THUMB_SIZE, Image.Resampling.LANCZOS)
    thumb.save(folder / f"{name}_thumb.webp", "WEBP", quality=82, method=4)

    return f"recipes/{name}.webp", f"recipes/{name}_thumb.webp"


def save_upload(upload: UploadFile) -> tuple[str, str]:
    data = upload.file.read(settings.max_upload_bytes + 1)
    if not data:
        raise ValidationFailedError("The uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise FileTooLargeError(f"Image must be smaller than {settings.max_upload_mb} MB")

    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # cheap integrity check; the file must be reopened afterwards
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise UnsupportedMediaError("The file is not a valid image") from None

    if img.format not in ALLOWED_FORMATS:
        raise UnsupportedMediaError("Only JPEG, PNG or WebP images are allowed")

    width, height = img.size
    if width < settings.min_image_width or height < settings.min_image_height:
        raise ValidationFailedError(
            f"Image is too small ({width}x{height}px). "
            f"Minimum is {settings.min_image_width}x{settings.min_image_height}px for good quality."
        )
    return store_image(img)


def delete_image_files(*relative_paths: str | None) -> None:
    for rel in relative_paths:
        if rel:
            (Path(settings.upload_dir) / rel).unlink(missing_ok=True)
