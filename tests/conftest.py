import io
import os
import tempfile

# --- Configure the app for testing BEFORE it is imported -------------------------------
_TMP = tempfile.mkdtemp(prefix="feastfit-test-")
os.environ.update(
    {
        "ENVIRONMENT": "testing",
        "DATABASE_URL": "sqlite://",  # in-memory, shared via StaticPool
        "UPLOAD_DIR": os.path.join(_TMP, "uploads"),
        "SECRET_KEY": "test-secret-key-that-is-definitely-long-enough-for-hs256",
        "PASSWORD_ITERATIONS": "1000",  # fast hashing in tests
        "ADMIN_EMAIL": "admin@example.com",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "Str0ngPass1"


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_user(client, username="raj", email="raj@example.com", password=PASSWORD) -> dict:
    """Register + log in; returns the Authorization header."""
    r = client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return make_user(client)


@pytest.fixture
def auth2(client):
    return make_user(client, "giulia", "giulia@example.com")


@pytest.fixture
def admin_auth(client):
    return make_user(client, "admin", "admin@example.com")


@pytest.fixture
def recipe_payload():
    return {
        "title": "Spaghetti alla Carbonara",
        "description": "Silky Roman pasta made with eggs, pecorino and guanciale.",
        "cuisine": "italian",
        "category": "primo",
        "difficulty": "easy",
        "diet_tags": ["high-protein"],
        "prep_minutes": 10,
        "cook_minutes": 15,
        "servings": 2,
        "calories": 610,
        "protein_g": 28,
        "carbs_g": 62,
        "fat_g": 26,
        "ingredients": [
            {"name": "Spaghetti", "quantity": "200 g"},
            {"name": "Guanciale", "quantity": "100 g"},
        ],
        "steps": [
            {"instruction": "Boil the pasta in salted water."},
            {"instruction": "Crisp the guanciale and toss with eggs and cheese."},
        ],
    }


@pytest.fixture
def create_recipe(client, recipe_payload):
    def _create(headers, **overrides):
        r = client.post("/api/recipes", json={**recipe_payload, **overrides}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture
def make_image():
    def _make(size=(900, 700), fmt="PNG") -> bytes:
        buf = io.BytesIO()
        Image.new("RGB", size, (200, 60, 40)).save(buf, fmt)
        return buf.getvalue()

    return _make


@pytest.fixture
def upload_dir():
    return os.environ["UPLOAD_DIR"]
