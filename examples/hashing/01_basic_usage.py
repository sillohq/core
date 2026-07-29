"""Basic password hashing example using passlib and sillo.

Run with:
    uv run python examples/hashing/01_basic_usage.py
"""

from sillo.hashing import hash_password, verify_password


def main():
    """Demonstrate basic password hashing."""
    password = "my_secure_password"

    print("=" * 60)
    print("BASIC PASSWORD HASHING")
    print("=" * 60)
    print()

    hashed = hash_password(password)
    print(f"Password: {password}")
    print(f"Hash: {hashed}")
    print()

    is_valid = verify_password(password, hashed)
    print(f"Verify correct password: {is_valid}")

    is_invalid = verify_password("wrong_password", hashed)
    print(f"Verify wrong password: {is_invalid}")
    print()


if __name__ == "__main__":
    main()
