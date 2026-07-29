"""Multi-algorithm password hashing example.

This demonstrates using different hashing algorithms (bcrypt, argon2, scrypt, pbkdf2).

Before running, install the algorithms you want to use:
    uv add bcrypt                    # bcrypt (default, lightweight)
    uv add argon2-cffi               # Argon2 (most secure, recommended)
    uv add scrypt                    # Scrypt
    # PBKDF2 is built-in, no extra dependency

Run with:
    uv run python 02_multiple_algorithms.py
"""

from sillo.hashing import hash_password, verify_password, set_default_algorithm


def example_bcrypt():
    """Example: Bcrypt (simple, good for most uses)."""
    print("=" * 60)
    print("BCRYPT HASHING")
    print("=" * 60)

    password = "my_secure_password"

    hashed = hash_password(password, algorithm="bcrypt")
    print(f"Password: {password}")
    print(f"Hash: {hashed}")
    print(f"Hash starts with: {hashed[:10]}")

    is_valid = verify_password(password, hashed)
    print(f"Verification: {is_valid}")
    print()


def example_argon2():
    """Example: Argon2 (most modern and secure)."""
    print("=" * 60)
    print("ARGON2 HASHING (Most Secure)")
    print("=" * 60)

    password = "my_secure_password"

    try:
        hashed = hash_password(password, algorithm="argon2")
        print(f"Password: {password}")
        print(f"Hash: {hashed}")
        print(f"Hash starts with: {hashed[:10]}")

        is_valid = verify_password(password, hashed)
        print(f"Verification: {is_valid}")
    except Exception as e:
        print(f"Note: Argon2 requires argon2-cffi. Install with: uv add argon2-cffi")
        print(f"Error: {e}")

    print()


def example_scrypt():
    """Example: Scrypt (memory-hard algorithm)."""
    print("=" * 60)
    print("SCRYPT HASHING (Memory-Hard)")
    print("=" * 60)

    password = "my_secure_password"

    try:
        hashed = hash_password(password, algorithm="scrypt")
        print(f"Password: {password}")
        print(f"Hash: {hashed[:50]}...")
        print(f"Hash starts with: {hashed.split('$')[0]}")

        is_valid = verify_password(password, hashed)
        print(f"Verification: {is_valid}")
    except Exception as e:
        print(f"Note: Scrypt requires scrypt. Install with: uv add scrypt")
        print(f"Error: {e}")

    print()


def example_pbkdf2():
    """Example: PBKDF2 (built-in, no extra dependency)."""
    print("=" * 60)
    print("PBKDF2 HASHING (Built-in, No Dependencies)")
    print("=" * 60)

    password = "my_secure_password"

    hashed = hash_password(password, algorithm="pbkdf2")
    print(f"Password: {password}")
    print(f"Hash: {hashed[:60]}...")
    print(f"Hash starts with: {hashed.split('$')[0]}")

    is_valid = verify_password(password, hashed)
    print(f"Verification: {is_valid}")
    print()


def example_auto_detection():
    """Example: Automatic algorithm detection on verification."""
    print("=" * 60)
    print("AUTOMATIC ALGORITHM DETECTION")
    print("=" * 60)

    password = "my_secure_password"

    bcrypt_hash = hash_password(password, algorithm="bcrypt")
    pbkdf2_hash = hash_password(password, algorithm="pbkdf2")

    print(f"Bcrypt hash: {bcrypt_hash[:30]}...")
    print(f"PBKDF2 hash: {pbkdf2_hash[:30]}...")
    print()

    print("Verifying without specifying algorithm:")
    print(f"Bcrypt verify: {verify_password(password, bcrypt_hash)}")
    print(f"PBKDF2 verify: {verify_password(password, pbkdf2_hash)}")
    print()


def example_set_default():
    """Example: Setting a default algorithm."""
    print("=" * 60)
    print("SETTING DEFAULT ALGORITHM")
    print("=" * 60)

    password = "my_secure_password"

    set_default_algorithm("pbkdf2")

    hashed = hash_password(password)
    print(f"Default algorithm set to: PBKDF2")
    print(f"Hashed (using default): {hashed[:50]}...")
    print(f"Verify: {verify_password(password, hashed)}")
    print()


def example_comparison():
    """Example: Comparing different algorithms."""
    print("=" * 60)
    print("ALGORITHM COMPARISON")
    print("=" * 60)

    password = "test_password_123"

    algorithms = {
        "bcrypt": "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUi",
        "pbkdf2": "pbkdf2$sha256$600000$dGVzdHNhbHQxMjM0NTY=$...",
    }

    print(f"Password: {password}")
    print()

    for algo, desc in [
        ("bcrypt", "Bcrypt (time cost: 12 rounds)"),
        ("argon2", "Argon2 (memory-hard, recommended)"),
        ("scrypt", "Scrypt (memory-hard)"),
        ("pbkdf2", "PBKDF2 (600,000 iterations)"),
    ]:
        try:
            hashed = hash_password(password, algorithm=algo)
            verified = verify_password(password, hashed)
            print(f"✓ {algo:10s} - {desc:40s} - Verified: {verified}")
        except Exception as e:
            print(f"✗ {algo:10s} - {desc:40s} - Not installed")

    print()


if __name__ == "__main__":
    example_bcrypt()
    example_argon2()
    example_scrypt()
    example_pbkdf2()
    example_auto_detection()
    example_set_default()
    example_comparison()
