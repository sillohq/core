"""Coverage for sillo.hashing.utils: none of these helpers had prior tests."""

from __future__ import annotations

from sillo.hashing.utils import (
    UNUSABLE_PASSWORD_PREFIX,
    constant_time_compare,
    is_password_usable,
    make_unusable_password,
    md5,
    password_strength,
    sha256,
    validate_password,
)


def test_make_unusable_password_has_prefix_and_is_unusable():
    marker = make_unusable_password()
    assert marker.startswith(UNUSABLE_PASSWORD_PREFIX)
    assert is_password_usable(marker) is False


def test_is_password_usable_true_for_normal_hash():
    assert is_password_usable("$2b$12$something") is True


def test_is_password_usable_false_for_empty_string():
    assert is_password_usable("") is False


def test_validate_password_reports_every_missing_requirement():
    errors = validate_password("short")
    assert any("8 characters" in e for e in errors)
    assert any("uppercase" in e for e in errors)
    assert any("digit" in e for e in errors)
    assert any("special character" in e for e in errors)


def test_validate_password_lowercase_requirement():
    errors = validate_password("ALLCAPS123!")
    assert any("lowercase" in e for e in errors)


def test_validate_password_accepts_a_strong_password():
    assert validate_password("Str0ng!Passw0rd") == []


def test_validate_password_respects_custom_min_length():
    errors = validate_password("Ab1!ab1!", min_length=20)
    assert any("20 characters" in e for e in errors)


def test_password_strength_too_short_gives_weak():
    result = password_strength("ab")
    assert result["strength"] == "weak"
    assert "Too short" in result["feedback"]


def test_password_strength_medium():
    result = password_strength("abcdefgh1")
    assert result["strength"] == "medium"


def test_password_strength_strong_with_diverse_long_password():
    result = password_strength("Xk9#mQ2$vLp7!zR4")
    assert result["strength"] == "strong"
    assert result["score"] >= 5


def test_password_strength_flags_low_character_diversity():
    result = password_strength("aaaaaaaaaaaa")
    assert "Low character diversity" in result["feedback"]


def test_constant_time_compare_equal_and_different():
    assert constant_time_compare("secret", "secret") is True
    assert constant_time_compare("secret", "different") is False


def test_md5_of_str_and_bytes_match():
    assert md5("hello") == md5(b"hello")
    assert len(md5("hello")) == 32


def test_sha256_of_str_and_bytes_match():
    assert sha256("hello") == sha256(b"hello")
    assert len(sha256("hello")) == 64
