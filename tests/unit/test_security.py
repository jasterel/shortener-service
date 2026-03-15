from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)
from app.core.config import settings


class TestHashPassword:
    def test_returns_non_empty_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_hash_differs_from_plaintext(self):
        pw = "mypassword"
        assert hash_password(pw) != pw

    def test_two_hashes_of_same_password_differ(self):
        
        pw = "mypassword"
        assert hash_password(pw) != hash_password(pw)


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        pw = "correct_horse_battery_staple"
        hashed = hash_password(pw)
        assert verify_password(pw, hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("realpassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_empty_password_against_hash_returns_false(self):
        hashed = hash_password("notempty")
        assert verify_password("", hashed) is False


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token("42")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_subject(self):
        token = create_access_token("99")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "99"

    def test_token_has_expiry(self):
        token = create_access_token("1")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload

    def test_expiry_is_in_the_future(self):
        token = create_access_token("1")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)


class TestDecodeToken:
    def test_valid_token_returns_payload(self):
        token = create_access_token("7")
        result = decode_token(token)
        assert result is not None
        assert result["sub"] == "7"

    def test_invalid_token_returns_none(self):
        assert decode_token("this.is.not.a.token") is None

    def test_tampered_token_returns_none(self):
        token = create_access_token("1")
        tampered = token[:-5] + "XXXXX"
        assert decode_token(tampered) is None

    def test_expired_token_returns_none(self):
        expired_token = jwt.encode(
            {
                "sub": "1",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        assert decode_token(expired_token) is None
