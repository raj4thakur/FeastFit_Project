def test_html_pages_render(client):
    for path in ("/", "/login", "/register", "/upload", "/me", "/recipes/some-slug"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "text/html" in r.headers["content-type"]
        assert "FeastFit" in r.text


def test_static_assets_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_unknown_page_gives_html_404(client):
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "text/html" in r.headers["content-type"]
    assert "isn't on the menu" in r.text


def test_unknown_api_route_gives_json_404(client):
    r = client.get("/api/no-such-route")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_method_not_allowed_is_json(client):
    r = client.delete("/api/meta")
    assert r.status_code == 405
    assert r.json()["error"]["code"] == "method_not_allowed"
