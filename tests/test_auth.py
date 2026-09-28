from tests.conftest import PASSWORD, make_user


def test_register_success_hides_password(client):
    r = client.post(
        "/api/auth/register",
        json={"username": "raj", "email": "Raj@Example.com", "password": PASSWORD},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "raj"
    assert body["email"] == "raj@example.com"  # normalised to lowercase
    assert body["is_admin"] is False
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email_and_username(client):
    make_user(client)
    dup_email = client.post(
        "/api/auth/register", json={"username": "other", "email": "RAJ@example.com", "password": PASSWORD}
    )
    assert dup_email.status_code == 409
    assert dup_email.json()["error"]["code"] == "conflict"

    dup_name = client.post(
        "/api/auth/register", json={"username": "RAJ", "email": "new@example.com", "password": PASSWORD}
    )
    assert dup_name.status_code == 409


def test_register_validation(client):
    weak = client.post("/api/auth/register", json={"username": "raj", "email": "a@example.com", "password": "short"})
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "validation_error"

    no_digit = client.post(
        "/api/auth/register", json={"username": "raj", "email": "a@example.com", "password": "onlyletters"}
    )
    assert no_digit.status_code == 422

    bad_email = client.post("/api/auth/register", json={"username": "raj", "email": "nope", "password": PASSWORD})
    assert bad_email.status_code == 422

    bad_name = client.post(
        "/api/auth/register", json={"username": "no spaces!", "email": "a@example.com", "password": PASSWORD}
    )
    assert bad_name.status_code == 422


def test_login_with_username_or_email(client):
    make_user(client)
    for ident in ("raj", "raj@example.com", "RAJ"):
        r = client.post("/api/auth/login", data={"username": ident, "password": PASSWORD})
        assert r.status_code == 200, ident
        assert r.json()["token_type"] == "bearer"


def test_login_wrong_password_and_unknown_user(client):
    make_user(client)
    bad_pw = client.post("/api/auth/login", data={"username": "raj", "password": "WrongPass1"})
    assert bad_pw.status_code == 401
    assert bad_pw.json()["error"]["code"] == "authentication_failed"
    assert bad_pw.headers["www-authenticate"] == "Bearer"

    ghost = client.post("/api/auth/login", data={"username": "ghost", "password": PASSWORD})
    assert ghost.status_code == 401


def test_me_requires_valid_token(client, auth):
    ok = client.get("/api/auth/me", headers=auth)
    assert ok.status_code == 200
    assert ok.json()["username"] == "raj"

    assert client.get("/api/auth/me").status_code == 401
    bad = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Invalid or expired token"


def test_admin_email_gets_admin_flag(client, admin_auth):
    assert client.get("/api/auth/me", headers=admin_auth).json()["is_admin"] is True
