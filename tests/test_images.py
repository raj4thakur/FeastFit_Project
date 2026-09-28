import os

from app.config import get_settings


def _upload(client, headers, rid, content, name="dish.png", mime="image/png"):
    return client.post(
        f"/api/recipes/{rid}/image", files={"file": (name, content, mime)}, headers=headers
    )


def test_upload_image_creates_webp_and_thumbnail(client, auth, create_recipe, make_image, upload_dir):
    rid = create_recipe(auth)["id"]
    r = _upload(client, auth, rid, make_image())
    assert r.status_code == 200
    body = r.json()
    assert body["image_url"].startswith("/media/recipes/") and body["image_url"].endswith(".webp")
    assert body["thumb_url"].endswith("_thumb.webp")

    for url in (body["image_url"], body["thumb_url"]):
        assert os.path.exists(os.path.join(upload_dir, url.removeprefix("/media/")))
    served = client.get(body["image_url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/webp"


def test_replacing_image_deletes_old_files(client, auth, create_recipe, make_image, upload_dir):
    rid = create_recipe(auth)["id"]
    first = _upload(client, auth, rid, make_image()).json()["image_url"]
    second = _upload(client, auth, rid, make_image(fmt="JPEG"), "dish.jpg", "image/jpeg").json()["image_url"]
    assert first != second
    assert not os.path.exists(os.path.join(upload_dir, first.removeprefix("/media/")))
    assert os.path.exists(os.path.join(upload_dir, second.removeprefix("/media/")))


def test_deleting_recipe_removes_its_images(client, auth, create_recipe, make_image, upload_dir):
    rid = create_recipe(auth)["id"]
    url = _upload(client, auth, rid, make_image()).json()["image_url"]
    path = os.path.join(upload_dir, url.removeprefix("/media/"))
    assert os.path.exists(path)
    assert client.delete(f"/api/recipes/{rid}", headers=auth).status_code == 204
    assert not os.path.exists(path)


def test_rejects_non_image(client, auth, create_recipe):
    rid = create_recipe(auth)["id"]
    r = _upload(client, auth, rid, b"definitely not an image", "notes.txt", "text/plain")
    assert r.status_code == 415
    assert r.json()["error"]["code"] == "unsupported_media_type"


def test_rejects_disallowed_format(client, auth, create_recipe, make_image):
    rid = create_recipe(auth)["id"]
    r = _upload(client, auth, rid, make_image(fmt="GIF"), "anim.gif", "image/gif")
    assert r.status_code == 415


def test_rejects_low_resolution(client, auth, create_recipe, make_image):
    rid = create_recipe(auth)["id"]
    r = _upload(client, auth, rid, make_image(size=(100, 100)))
    assert r.status_code == 422
    assert "too small" in r.json()["error"]["message"]


def test_rejects_empty_file(client, auth, create_recipe):
    rid = create_recipe(auth)["id"]
    assert _upload(client, auth, rid, b"").status_code == 422


def test_rejects_oversized_file(client, auth, create_recipe, make_image, monkeypatch):
    rid = create_recipe(auth)["id"]
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    r = _upload(client, auth, rid, make_image())
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "file_too_large"


def test_upload_permissions(client, auth, auth2, create_recipe, make_image):
    rid = create_recipe(auth)["id"]
    assert _upload(client, auth2, rid, make_image()).status_code == 403
    assert client.post(
        f"/api/recipes/{rid}/image", files={"file": ("d.png", make_image(), "image/png")}
    ).status_code == 401
    assert _upload(client, auth, 9999, make_image()).status_code == 404
