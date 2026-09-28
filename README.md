# 🍅 FeastFit — by Raj Thakur

A diet & recipe platform with an Italian soul. Backend-first: **FastAPI · SQLAlchemy 2 · JWT auth · Pillow image pipeline · pytest · Docker · GitHub Actions CI/CD**.
The UI is intentionally thin (Jinja + vanilla JS) so the API is the star.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python -m scripts.seed                                 # demo chef + 10 recipes with images
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> (site) and <http://127.0.0.1:8000/docs> (interactive API docs).
Demo login after seeding: **`chef_raj` / `Feast2026`** (or just register your own account).

## Run with Docker (PostgreSQL)

```bash
docker compose up --build
docker compose exec api python -m scripts.seed
```

## Tests & lint

```bash
pytest --cov=app --cov-report=term-missing
ruff check .
```
Tests run against an in-memory SQLite DB and a temp upload folder — nothing touches your real data.

## Project layout

```
app/
  main.py          app factory, middleware, static/media mounts, router wiring
  config.py        env-driven settings (pydantic-settings)
  database.py      engine/session (SQLite or PostgreSQL)
  models.py        User, Recipe, Ingredient, Step, Favorite, Review
  schemas.py       Pydantic request/response models + validation rules
  security.py      PBKDF2 password hashing, JWT create/verify
  deps.py          get_current_user / get_optional_user
  exceptions.py    domain exceptions + JSON error handlers
  routers/         auth, recipes, users, meta(+health), pages
  services/        recipes (business logic), images (upload pipeline)
  templates/ static/   the (light) front-end
scripts/seed.py    demo data
tests/             auth, recipes, images, security, pages
Dockerfile · docker-compose.yml · .github/workflows/ci.yml
```

## Data model

```
User 1───* Recipe 1───* Ingredient
  │  │        │ └──* Step
  │  └─* Favorite *─┘   (composite PK user_id + recipe_id)
  └────* Review *───────  (one per user per recipe, rating 1–5 enforced by CHECK)
```

## API overview

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/auth/register` | – | Create account (409 on duplicate email/username) |
| POST | `/api/auth/login` | – | Form login (username **or** email) → JWT |
| GET | `/api/auth/me` | ✔ | Current user |
| GET | `/api/recipes` | – | Search + filter (`q`, `cuisine`, `category`, `diet`, `difficulty`, `max_minutes`, `max_calories`), `sort`, `page`, `size` |
| POST | `/api/recipes` | ✔ | Publish recipe (ingredients + steps + nutrition) |
| GET | `/api/recipes/{id}` · `/slug/{slug}` | opt | Full recipe (`is_favorite` when logged in) |
| PATCH | `/api/recipes/{id}` | ✔ owner/admin | Partial update |
| DELETE | `/api/recipes/{id}` | ✔ owner/admin | Delete (also removes image files) |
| POST | `/api/recipes/{id}/image` | ✔ owner/admin | Upload photo (JPEG/PNG/WebP, ≥600×400, ≤8 MB) → WebP + thumbnail |
| POST/DELETE | `/api/recipes/{id}/favorite` | ✔ | Save / unsave (idempotent) |
| GET/POST | `/api/recipes/{id}/reviews` | POST ✔ | List / create-or-update your review |
| GET | `/api/users/me/recipes` · `/favorites` | ✔ | My recipes / saved recipes |
| GET | `/api/meta` · `/health` | – | Allowed values · liveness + DB check |

### Error format (exception-based)
Every failure returns the same shape, with a stable machine-readable `code`:
```json
{"error": {"code": "validation_error", "message": "Request validation failed",
           "details": [{"field": "cuisine", "message": "Value error, must be one of: italian, ..."}]}}
```
Codes: `validation_error` (422) · `authentication_failed` (401) · `forbidden` (403) · `not_found` (404) · `conflict` (409) · `file_too_large` (413) · `unsupported_media_type` (415) · `internal_error` (500).
Raise `NotFoundError("…")`, `ConflictError("…")` etc. anywhere in services — handlers in `app/exceptions.py` do the rest.

## CI/CD (GitHub Actions)

`lint (ruff) → test (pytest + coverage) → docker (build, boot-and-curl /health smoke test, push to GHCR) → deploy (webhook)`.
* PRs run lint + tests + image build. Pushes to `main` also publish `ghcr.io/<you>/<repo>:latest`.
* For automatic deploys add a repo secret **`DEPLOY_HOOK_URL`** (Render/Railway deploy hook). Without it the deploy job is skipped.
* In production set `ENVIRONMENT=production` and a strong `SECRET_KEY` (the app refuses to boot with the default).

## Notes / next steps
* Tables are created on startup with `create_all`. Once the schema starts changing on a live DB, adopt **Alembic**.
* Add rate limiting (e.g. `slowapi`) on `/api/auth/login`, and move uploads to S3/R2 for multi-instance deploys.
* Ideas: meal planner, shopping list, macro calculator, recipe import from URL, LLM recipe assistant.
