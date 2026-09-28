import pytest


def test_create_requires_auth(client, recipe_payload):
    r = client.post("/api/recipes", json=recipe_payload)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "authentication_failed"


def test_create_recipe_returns_full_detail(client, auth, recipe_payload):
    r = client.post("/api/recipes", json=recipe_payload, headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "spaghetti-alla-carbonara"
    assert body["total_minutes"] == 25
    assert body["author_name"] == "raj"
    assert body["diet_tags"] == ["high-protein"]
    assert [i["name"] for i in body["ingredients"]] == ["Spaghetti", "Guanciale"]
    assert [s["position"] for s in body["steps"]] == [1, 2]
    assert body["avg_rating"] is None and body["review_count"] == 0
    assert body["image_url"] is None


def test_duplicate_titles_get_unique_slugs(auth, create_recipe):
    first = create_recipe(auth)
    second = create_recipe(auth)
    assert first["slug"] == "spaghetti-alla-carbonara"
    assert second["slug"] == "spaghetti-alla-carbonara-2"


def test_accents_are_slugified(auth, create_recipe):
    assert create_recipe(auth, title="Tiramisù Classico")["slug"] == "tiramisu-classico"


@pytest.mark.parametrize(
    "override",
    [
        {"cuisine": "martian"},
        {"category": "nonsense"},
        {"difficulty": "impossible"},
        {"diet_tags": ["paleo-ish"]},
        {"ingredients": []},
        {"steps": []},
        {"title": "ab"},
        {"servings": 0},
        {"calories": -5},
    ],
)
def test_create_validation_errors(client, auth, recipe_payload, override):
    r = client.post("/api/recipes", json={**recipe_payload, **override}, headers=auth)
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "validation_error"
    assert error["details"], "field-level details should be returned"


def test_get_by_id_and_slug_and_404(client, auth, create_recipe):
    recipe = create_recipe(auth)
    by_id = client.get(f"/api/recipes/{recipe['id']}")
    by_slug = client.get(f"/api/recipes/slug/{recipe['slug']}")
    assert by_id.status_code == by_slug.status_code == 200
    assert by_id.json()["title"] == by_slug.json()["title"]

    missing = client.get("/api/recipes/9999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert client.get("/api/recipes/slug/does-not-exist").status_code == 404


def test_list_filters_search_sort_and_pagination(client, auth, create_recipe):
    create_recipe(auth, title="Tiramisu Classico", category="dolce", diet_tags=["vegetarian"],
                  prep_minutes=30, cook_minutes=0, calories=430,
                  ingredients=[{"name": "Mascarpone", "quantity": "500 g"}])
    create_recipe(auth, title="Vegan Minestrone", category="primo", diet_tags=["vegan", "vegetarian"],
                  prep_minutes=20, cook_minutes=40, calories=210)
    create_recipe(auth, title="Miso Salmon Bowl", cuisine="japanese", category="secondo",
                  diet_tags=["high-protein"], prep_minutes=10, cook_minutes=12, calories=560)

    def total(**params):
        r = client.get("/api/recipes", params=params)
        assert r.status_code == 200
        return r.json()["total"]

    assert total() == 3
    assert total(cuisine="italian") == 2
    assert total(category="dolce") == 1
    assert total(diet="vegetarian") == 2
    assert total(diet="vegan") == 1
    assert total(q="tiramis") == 1
    assert total(q="mascarpone") == 1  # matches ingredient names too
    assert total(max_minutes=30) == 2
    assert total(max_calories=300) == 1
    assert total(cuisine="italian", diet="vegan") == 1

    quickest = client.get("/api/recipes", params={"sort": "quickest"}).json()["items"]
    assert quickest[0]["title"] == "Miso Salmon Bowl"

    page = client.get("/api/recipes", params={"size": 1, "page": 2}).json()
    assert page["total"] == 3 and page["pages"] == 3 and len(page["items"]) == 1

    assert client.get("/api/recipes", params={"sort": "bogus"}).status_code == 422
    assert client.get("/api/recipes", params={"size": 500}).status_code == 422


def test_update_by_owner_replaces_children_keeps_slug(client, auth, create_recipe):
    recipe = create_recipe(auth)
    r = client.patch(
        f"/api/recipes/{recipe['id']}",
        json={
            "title": "Carbonara Perfetta",
            "calories": None,
            "ingredients": [{"name": "Pasta", "quantity": "300 g"}],
        },
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Carbonara Perfetta"
    assert body["slug"] == recipe["slug"]
    assert body["calories"] is None
    assert [i["name"] for i in body["ingredients"]] == ["Pasta"]
    assert len(body["steps"]) == 2  # untouched


def test_update_and_delete_forbidden_for_other_users(client, auth, auth2, create_recipe):
    recipe = create_recipe(auth)
    patch = client.patch(f"/api/recipes/{recipe['id']}", json={"title": "Hijacked"}, headers=auth2)
    assert patch.status_code == 403
    assert patch.json()["error"]["code"] == "forbidden"
    assert client.delete(f"/api/recipes/{recipe['id']}", headers=auth2).status_code == 403
    assert client.delete(f"/api/recipes/{recipe['id']}").status_code == 401


def test_delete_by_owner_and_by_admin(client, auth, admin_auth, create_recipe):
    mine = create_recipe(auth)
    assert client.delete(f"/api/recipes/{mine['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/recipes/{mine['id']}").status_code == 404

    other = create_recipe(auth, title="Another Dish")
    assert client.delete(f"/api/recipes/{other['id']}", headers=admin_auth).status_code == 204


def test_favorites_flow(client, auth, auth2, create_recipe):
    recipe = create_recipe(auth)
    rid = recipe["id"]

    assert client.post(f"/api/recipes/{rid}/favorite", headers=auth2).status_code == 204
    assert client.post(f"/api/recipes/{rid}/favorite", headers=auth2).status_code == 204  # idempotent

    favs = client.get("/api/users/me/favorites", headers=auth2).json()
    assert [f["id"] for f in favs] == [rid]
    assert client.get(f"/api/recipes/{rid}", headers=auth2).json()["is_favorite"] is True
    assert client.get(f"/api/recipes/{rid}").json()["is_favorite"] is False

    assert client.delete(f"/api/recipes/{rid}/favorite", headers=auth2).status_code == 204
    assert client.get("/api/users/me/favorites", headers=auth2).json() == []
    assert client.post("/api/recipes/9999/favorite", headers=auth2).status_code == 404
    assert client.post(f"/api/recipes/{rid}/favorite").status_code == 401


def test_my_recipes(client, auth, auth2, create_recipe):
    create_recipe(auth)
    create_recipe(auth2, title="Giulia's Gnocchi")
    mine = client.get("/api/users/me/recipes", headers=auth).json()
    assert [r["title"] for r in mine] == ["Spaghetti alla Carbonara"]


def test_reviews_flow(client, auth, auth2, create_recipe):
    rid = create_recipe(auth)["id"]

    own = client.post(f"/api/recipes/{rid}/reviews", json={"rating": 5}, headers=auth)
    assert own.status_code == 403  # can't review your own dish

    created = client.post(
        f"/api/recipes/{rid}/reviews", json={"rating": 5, "comment": "Perfetto!"}, headers=auth2
    )
    assert created.status_code == 201
    assert created.json()["username"] == "giulia"

    updated = client.post(f"/api/recipes/{rid}/reviews", json={"rating": 3, "comment": "Good"}, headers=auth2)
    assert updated.status_code == 200  # same user -> updated, not duplicated

    detail = client.get(f"/api/recipes/{rid}").json()
    assert detail["avg_rating"] == 3.0 and detail["review_count"] == 1

    reviews = client.get(f"/api/recipes/{rid}/reviews").json()
    assert len(reviews) == 1 and reviews[0]["comment"] == "Good"

    assert client.post(f"/api/recipes/{rid}/reviews", json={"rating": 6}, headers=auth2).status_code == 422
    assert client.post(f"/api/recipes/{rid}/reviews", json={"rating": 4}).status_code == 401


def test_meta_and_health(client):
    meta = client.get("/api/meta").json()
    assert "italian" in meta["cuisines"]
    assert {"value": "primo", "label": "Primi (Pasta & Rice)"} in meta["categories"]

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "up"}
