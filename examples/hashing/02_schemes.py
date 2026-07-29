"""Password hashing with different schemes example.

Before running, install the schemes you want:
    uv add bcrypt               # bcrypt (default)
    uv add argon2-cffi         # Argon2 (recommended)
    uv add scrypt              # Scrypt

Run with:
    uv run python examples/hashing/02_schemes.py
"""

from sillo.hashing import (
    hash_password,
    verify_password,
    get_available_schemes_list,
    set_default_scheme,
)


def main():
    """Demonstrate different hashing schemes."""
    password = "test_password_123"

    print("=" * 60)
    print("AVAILABLE SCHEMES")
    print("=" * 60)
    available = get_available_schemes_list()
    print(f"Available schemes: {available}")
    print()

    print("=" * 60)
    print("HASHING WITH DIFFERENT SCHEMES")
    print("=" * 60)
    print(f"Password: {password}")
    print()

    for scheme in available:
        try:
            hashed = hash_password(password, scheme=scheme)
            verified = verify_password(password, hashed)
            print(f"✓ {scheme:20s} - Hash: {hashed[:40]}... - Verified: {verified}")
        except Exception as e:
            print(f"✗ {scheme:20s} - Error: {e}")

    print()

    print("=" * 60)
    print("AUTO-DETECTION ON VERIFICATION")
    print("=" * 60)

    if "bcrypt" in available:
        bcrypt_hash = hash_password(password, scheme="bcrypt")
        print(f"Bcrypt hash: {bcrypt_hash[:40]}...")
        print(f"Verify (auto-detect): {verify_password(password, bcrypt_hash)}")
    print()

    print("=" * 60)
    print("SETTING DEFAULT SCHEME")
    print("=" * 60)

    if "argon2" in available:
        set_default_scheme("argon2")
        print("Default scheme set to: argon2")
        hashed = hash_password(password)
        print(f"Hashed with default: {hashed[:40]}...")
        print(f"Verified: {verify_password(password, hashed)}")
    else:
        print("Note: argon2 not available. Install with: uv add argon2-cffi")

    print()


if __name__ == "__main__":
    main()
