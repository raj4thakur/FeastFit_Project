import pytest

from app.exceptions import AuthenticationError
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("Str0ngPass1")
    assert hashed != "Str0ngPass1"
    assert verify_password("Str0ngPass1", hashed)
    assert not verify_password("wrong-password", hashed)


def test_hashes_are_salted():
    assert hash_password("same-password1") != hash_password("same-password1")


def test_verify_rejects_garbage_hash():
    assert not verify_password("x", "not-a-valid-hash")


def test_token_roundtrip():
    assert decode_access_token(create_access_token(42)) == 42


def test_expired_token_is_rejected():
    with pytest.raises(AuthenticationError):
        decode_access_token(create_access_token(1, expires_minutes=-1))


def test_tampered_token_is_rejected():
    token = create_access_token(1)
    with pytest.raises(AuthenticationError):
        decode_access_token(token[:-3] + "abc")
