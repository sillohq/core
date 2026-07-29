# Password Hashing with Sillo

Simple, secure password hashing using passlib. Supports bcrypt, argon2, scrypt, and PBKDF2.

## Installation

```bash
# Bcrypt (default, lightweight)
uv add bcrypt

# Argon2 (most secure, recommended)
uv add argon2-cffi

# Scrypt (memory-hard)
uv add scrypt

# Install all
uv add "sillo[hashing-all]"
```

## Quick Start

```python
from sillo.hashing import hash_password, verify_password

# Hash a password
hashed = hash_password("my_password")

# Verify a password
if verify_password("my_password", hashed):
    print("Password is correct!")
```

## Different Schemes

```python
from sillo.hashing import hash_password, verify_password

# Use bcrypt (default)
bcrypt_hash = hash_password("password")

# Use argon2 (recommended)
argon2_hash = hash_password("password", scheme="argon2")

# Use scrypt
scrypt_hash = hash_password("password", scheme="scrypt")

# Use PBKDF2
pbkdf2_hash = hash_password("password", scheme="pbkdf2_sha256")

# Automatic detection on verification
if verify_password("password", bcrypt_hash):
    print("Valid!")
```

## Set Default Scheme

```python
from sillo.hashing import hash_password, set_default_scheme

# Use argon2 by default
set_default_scheme("argon2")

# Now all hashing uses argon2
hashed = hash_password("password")
```

## Available Schemes

| Scheme | Security | Speed | Memory | Notes |
|--------|----------|-------|--------|-------|
| **bcrypt** | Good | Slower | Low | Default, widely adopted |
| **argon2** | Excellent | Slow | High | Most secure, recommended |
| **scrypt** | Very Good | Medium | High | Memory-hard, GPU-resistant |
| **pbkdf2_sha256** | Good | Fast | Low | Built-in, no extra dependency |
| **pbkdf2_sha512** | Good | Fast | Low | Built-in, no extra dependency |

## In a Sillo App

```python
from sillo import silloApp, Query
from sillo.hashing import hash_password, verify_password

app = silloApp()

@app.post("/register")
async def register(request, response, username: str = Query(...), password: str = Query(...)):
    # Hash password
    hashed = hash_password(password)
    
    # Save to database
    user = await User.create(username=username, password_hash=hashed)
    
    return response.json({"user_id": user.id}, status_code=201)


@app.post("/login")
async def login(request, response, username: str = Query(...), password: str = Query(...)):
    user = await User.get_or_none(username=username)
    
    # Verify password (auto-detects scheme)
    if user and verify_password(password, user.password_hash):
        token = generate_jwt_token(user)
        return response.json({"token": token})
    
    return response.json({"error": "Invalid credentials"}, status_code=401)
```

## API Reference

### `hash_password(password: str, scheme: str = "bcrypt") -> str`

Hash a password.

**Parameters:**
- `password`: Plaintext password
- `scheme`: Hashing scheme (bcrypt, argon2, scrypt, pbkdf2_sha256, pbkdf2_sha512)

**Returns:** Hashed password string

**Raises:** `InvalidSchemeError` if scheme not available

### `verify_password(password: str, hashed: str) -> bool`

Verify a password against a hash. Auto-detects scheme.

**Parameters:**
- `password`: Plaintext password
- `hashed`: Previously hashed password

**Returns:** `True` if valid, `False` otherwise

### `needs_update(hashed: str) -> bool`

Check if hash needs regeneration with stronger settings.

**Parameters:**
- `hashed`: Previously hashed password

**Returns:** `True` if should be rehashed, `False` otherwise

### `set_default_scheme(scheme: str) -> None`

Set the default scheme for the application.

**Parameters:**
- `scheme`: Scheme name

**Raises:** `InvalidSchemeError` if scheme not available

### `get_available_schemes_list() -> list[str]`

Get list of available schemes.

**Returns:** List of scheme names

## Examples

### Basic Usage

```bash
uv run python examples/hashing/01_basic_usage.py
```

Output:
```
PASSWORD: my_secure_password
HASH: $2b$12$R9h7cIPz0gi.URNNX3kh2O...
VERIFY CORRECT: True
VERIFY WRONG: False
```

### Multiple Schemes

```bash
uv run python examples/hashing/02_schemes.py
```

### Web API

```bash
uv run uvicorn examples/hashing/03_web_api:app --reload
```

Then:
```bash
# Register
curl "http://localhost:8000/register?username=john&password=secret123"

# Login
curl "http://localhost:8000/login?username=john&password=secret123"

# Change password
curl -X POST "http://localhost:8000/change-password?username=john&old_password=secret123&new_password=newpass456"
```

## Best Practices

1. **Always hash passwords** - Never store plaintext
2. **Use argon2 for new apps** - Most secure algorithm
3. **Use bcrypt if needed for compatibility** - Proven, widely adopted
4. **Verify on every login** - Never skip verification
5. **Use HTTPS** - Always encrypt in transit
6. **Rate limit** - Protect against brute-force
7. **Enforce password strength** - Minimum length/complexity
8. **Rehash on migration** - Upgrade schemes on next login

## Error Handling

```python
from sillo.hashing import hash_password, InvalidSchemeError

try:
    hashed = hash_password("password", scheme="argon2")
except InvalidSchemeError:
    print("Install argon2-cffi: pip install argon2-cffi")
    hashed = hash_password("password", scheme="bcrypt")
```

## FAQ

**Q: Which scheme should I use?**
A: Use argon2 for new apps. Use bcrypt for compatibility.

**Q: Can I mix schemes in one app?**
A: Yes! `verify_password()` auto-detects. Rehash on next login to migrate.

**Q: Is PBKDF2 secure?**
A: Yes, but argon2 is better due to memory hardness.

**Q: Why is argon2 slow?**
A: Intentionally slow to resist brute-force. This is a feature.

**Q: Can I change schemes later?**
A: Yes. Rehash when users log in: `if needs_update(hash): hash = hash_password(password)`

## Powered by Passlib

This implementation uses [passlib](https://passlib.readthedocs.io/), a battle-tested Python password hashing library. It provides:

- Multiple algorithms
- Automatic scheme detection
- Best-practice defaults
- Well-maintained and secure

Sillo's wrapper makes it even simpler to use!
