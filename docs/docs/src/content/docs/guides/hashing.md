---
title: Password Hashing
description: Secure password hashing with multiple algorithms (bcrypt, argon2, scrypt, pbkdf2)
---

Sillo provides a comprehensive password hashing system powered by [passlib](https://passlib.readthedocs.io/), with support for multiple algorithms and automatic scheme detection.

## Overview

The hashing system provides:

- **Multiple algorithms** - bcrypt, argon2, scrypt, pbkdf2
- **Automatic detection** - Verify passwords regardless of which algorithm was used
- **Optional dependencies** - Install only the algorithms you need
- **Best-practice defaults** - Secure settings out of the box
- **Password utilities** - Validation, strength checking, comparison
- **User integration** - Seamless integration with `sillo.users.User`

## Installation

Passlib is included as a core dependency. Install algorithm support as needed:

```bash
# Bcrypt (default, lightweight, widely adopted)
uv add bcrypt

# Argon2 (most secure, memory-hard, recommended)
uv add argon2-cffi

# Scrypt (memory-hard, GPU-resistant)
uv add scrypt

# PBKDF2 (built-in to Python, no extra dependency needed)

# Install all algorithms
uv add "sillo[hashing-all]"
```

## Quick Start

### Basic Hashing and Verification

The most common pattern:

```python
from sillo.hashing import hash_password, verify_password

# Hash a password
hashed = hash_password("my_secure_password")

# Verify a password (auto-detects algorithm)
if verify_password("my_secure_password", hashed):
    print("Password is correct!")
```

### With Sillo User Model

```python
from sillo.users import User

# Create user with password
user = User(username="john", email="john@example.com")
user.set_password("my_secure_password")
await user.save()

# Verify password
if user.check_password("my_secure_password"):
    print("Login successful!")
```

## Detailed API Reference

### Core Hashing Functions

#### `hash_password(password: str, scheme: str = "bcrypt") -> str`

Hash a password using the specified algorithm.

**Parameters:**
- `password` (str): The plaintext password to hash
- `scheme` (str, optional): Hashing algorithm to use. Default is "bcrypt"
  - Valid schemes: `"bcrypt"`, `"argon2"`, `"scrypt"`, `"pbkdf2_sha256"`, `"pbkdf2_sha512"`

**Returns:**
- Hashed password string with algorithm prefix, salt, and parameters encoded

**Raises:**
- `InvalidSchemeError`: If the requested scheme is not installed

**Examples:**

```python
from sillo.hashing import hash_password

# Use default (bcrypt)
hashed = hash_password("password")

# Use argon2 (most secure)
hashed = hash_password("password", scheme="argon2")

# Use scrypt
hashed = hash_password("password", scheme="scrypt")

# Use PBKDF2
hashed = hash_password("password", scheme="pbkdf2_sha256")
```

**Hash Formats:**
- Bcrypt: `$2b$12$R9h7cIPz0gi.URNNX3kh2O...`
- Argon2: `$argon2id$v=19$m=65536,t=2,p=4$...`
- Scrypt: `scrypt$base64salt$base64hash`
- PBKDF2: `pbkdf2$sha256$600000$base64salt$base64hash`

#### `verify_password(password: str, hashed: str) -> bool`

Verify a plaintext password against a hash. **Automatically detects which algorithm was used**.

**Parameters:**
- `password` (str): The plaintext password to verify
- `hashed` (str): The previously hashed password

**Returns:**
- `True` if password matches, `False` otherwise
- Returns `False` (safe) if hash is invalid, rather than raising an exception

**Examples:**

```python
from sillo.hashing import hash_password, verify_password

# Hash with bcrypt
bcrypt_hash = hash_password("password")

# Verify (auto-detects bcrypt)
verify_password("password", bcrypt_hash)  # True

# Hash with argon2
argon2_hash = hash_password("password", scheme="argon2")

# Verify (auto-detects argon2)
verify_password("password", argon2_hash)  # True

# Both work even though they use different algorithms!
verify_password("wrong", bcrypt_hash)     # False
verify_password("wrong", argon2_hash)     # False
```

#### `needs_update(hashed: str) -> bool`

Check if a hash should be regenerated according to passlib's policy.

**Parameters:**
- `hashed` (str): The previously hashed password

**Returns:**
- `True` if the hash is using deprecated settings or schemes, `False` otherwise

**Examples:**

```python
from sillo.hashing import needs_update

if needs_update(user.password_hash):
    # Hash is using old settings, should regenerate
    user.set_password(plaintext_password)
    await user.save()
```

#### `needs_rehash(hashed: str, rounds: int = 12) -> bool`

Check if a hash should be regenerated with stronger settings.

**Parameters:**
- `hashed` (str): The previously hashed password
- `rounds` (int): Minimum acceptable bcrypt rounds (default 12)

**Returns:**
- `True` if hash should be regenerated, `False` otherwise

**Details:**
- For bcrypt hashes: Checks if the cost factor (rounds) is below the specified minimum
- For other schemes: Uses passlib's `needs_update()` logic
- Returns `True` for invalid hashes or no hash

**Examples:**

```python
from sillo.hashing import needs_rehash, hash_password

# Weak hash with only 4 rounds (old, insecure)
weak = hash_password("password")  # By default uses 12 rounds

if needs_rehash(weak, rounds=12):
    # Need to rehash
    strong = hash_password(plaintext)
```

**Use in Login Flow:**

```python
@app.post("/login")
async def login(request, response, username: str, password: str):
    user = await User.get_or_none(username=username)
    
    if user and user.check_password(password):
        # Optionally rehash old passwords to new algorithm
        if needs_rehash(user.password_hash):
            user.set_password(password)
            await user.save()
        
        return response.json({"token": generate_jwt_token(user)})
    
    return response.json({"error": "Invalid credentials"}, status_code=401)
```

#### `set_default_scheme(scheme: str) -> None`

Set the default hashing algorithm for the application. All future `hash_password()` calls without an explicit scheme will use this.

**Parameters:**
- `scheme` (str): The scheme name to use by default

**Raises:**
- `InvalidSchemeError`: If the scheme is not installed

**Examples:**

```python
from sillo.hashing import set_default_scheme, hash_password

# Set argon2 as default
set_default_scheme("argon2")

# Now these use argon2
hash1 = hash_password("password")
hash2 = hash_password("password")

# Both start with $argon2...
```

#### `get_available_schemes_list() -> list[str]`

Get the list of currently available hashing schemes.

**Returns:**
- List of scheme names (e.g., `["bcrypt", "argon2", "pbkdf2_sha256"]`)

**Examples:**

```python
from sillo.hashing import get_available_schemes_list

schemes = get_available_schemes_list()
print(f"Available: {schemes}")

# Conditionally use better algorithm
if "argon2" in schemes:
    set_default_scheme("argon2")
```

### Password Utilities

#### `is_password_usable(encoded: str) -> bool`

Check if a password hash is usable (not marked as unusable/disabled).

**Parameters:**
- `encoded` (str): The hashed password to check

**Returns:**
- `True` if password is usable, `False` if it's marked as unusable

**Details:**
- Unusable passwords start with `!` (the `UNUSABLE_PASSWORD_PREFIX`)
- Used for disabled accounts, unset passwords, etc.

**Examples:**

```python
from sillo.hashing import is_password_usable, make_unusable_password

# Disable a user's password
unusable = make_unusable_password()
user.password_hash = unusable
await user.save()

# Later, check if password is usable
if is_password_usable(user.password_hash):
    # Can log in with password
    pass
else:
    # Account is disabled
    pass
```

#### `make_unusable_password() -> str`

Create an unusable/disabled password marker.

**Returns:**
- A string that will fail password verification

**Details:**
- Used for accounts that shouldn't authenticate with a password
- E.g., disabled accounts, SSO-only accounts, invite-only flows

**Examples:**

```python
from sillo.hashing import make_unusable_password

# Create an invited user without password
user = User(username="john")
user.password_hash = make_unusable_password()
await user.save()

# Later, user sets password
user.set_password("password")  # Now usable
await user.save()
```

#### `validate_password(password: str, user=None, min_length: int = 8) -> list[str]`

Validate password against common strength requirements.

**Parameters:**
- `password` (str): The plaintext password to validate
- `user` (optional): User object (unused, for API compatibility)
- `min_length` (int): Minimum password length (default 8)

**Returns:**
- List of error messages (empty list if valid)

**Validation Rules:**
- At least `min_length` characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one digit (0-9)
- At least one special character (!@#$%^&*(),.?":{}|<>)

**Examples:**

```python
from sillo.hashing import validate_password

# Valid password
errors = validate_password("MyPass123!")
print(errors)  # []

# Too short
errors = validate_password("Pass1!")
print(errors)  # ["Password must be at least 8 characters."]

# Missing uppercase
errors = validate_password("mypass123!")
print(errors)  # ["Password must contain at least one uppercase letter."]

# Use in registration
@app.post("/register")
async def register(request, response, password: str = Query(...)):
    errors = validate_password(password)
    if errors:
        return response.json({"errors": errors}, status_code=400)
    
    user = User(username="john")
    user.set_password(password)
    await user.save()
    return response.json({"user_id": user.id}, status_code=201)
```

#### `password_strength(password: str) -> dict`

Analyze password strength and provide feedback.

**Parameters:**
- `password` (str): The plaintext password to analyze

**Returns:**
- Dictionary with:
  - `score` (int): 0-6 points
  - `strength` (str): "weak", "medium", or "strong"
  - `feedback` (list): Suggestions for improvement

**Scoring:**
- +2 points: At least 12 characters
- +1 point: 8-11 characters
- +1 point: Contains uppercase letters
- +1 point: Contains lowercase letters
- +1 point: Contains digits
- +1 point: Contains special characters

**Strength Classification:**
- 5-6 points: "strong"
- 3-4 points: "medium"
- 0-2 points: "weak"

**Examples:**

```python
from sillo.hashing import password_strength

result = password_strength("MySecurePass123!@#")
print(result)
# {
#     "score": 6,
#     "strength": "strong",
#     "feedback": []
# }

result = password_strength("weak")
print(result)
# {
#     "score": 1,
#     "strength": "weak",
#     "feedback": ["Too short", "Low character diversity"]
# }

# Use for real-time feedback
@app.post("/check-password-strength")
async def check_strength(request, response, password: str = Query(...)):
    result = password_strength(password)
    return response.json(result)
```

#### `constant_time_compare(val1: str, val2: str) -> bool`

Compare two values in constant time (timing-safe comparison).

**Parameters:**
- `val1` (str): First value to compare
- `val2` (str): Second value to compare

**Returns:**
- `True` if values match, `False` otherwise

**Details:**
- Uses Python's `secrets.compare_digest()` under the hood
- Prevents timing attacks by comparing all characters, not stopping early
- Already used internally by `verify_password()`

**Examples:**

```python
from sillo.hashing import constant_time_compare

# Comparing tokens or secrets (not passwords - use verify_password for that)
user_token = "abc123..."
provided_token = "abc123..."

if constant_time_compare(user_token, provided_token):
    print("Token matches!")
```

### Constants

#### `UNUSABLE_PASSWORD_PREFIX`

The prefix used to mark passwords as unusable.

```python
from sillo.hashing import UNUSABLE_PASSWORD_PREFIX

# Default value: "!"
# Unusable passwords start with this prefix
```

#### `UNUSABLE_PASSWORD_SUFFIX_LENGTH`

The length of the random suffix appended to the prefix.

```python
from sillo.hashing import UNUSABLE_PASSWORD_SUFFIX_LENGTH

# Default value: 40
```

## Algorithm Comparison

### Bcrypt

**Best For:** General purpose, compatibility, wide adoption

```python
hashed = hash_password("password", scheme="bcrypt")
# $2b$12$R9h7cIPz0gi.URNNX3kh2O...
```

**Characteristics:**
- Time-based security (intentionally slow)
- Limited to 72-character passwords
- Proven and battle-tested (since 2006)
- Default choice for compatibility
- ~100ms per hash with 12 rounds

**Installation:** `uv add bcrypt`

**Pros:**
- Widely adopted across Python ecosystem
- Battle-tested and proven secure
- Simple and reliable
- Good default choice

**Cons:**
- No memory hardness (can be parallelized on GPUs)
- Character length limitation (72 bytes)
- Slower than necessary for modern hardware

**When to Use:**
- Existing applications (backward compatible)
- Need maximum compatibility
- When unsure which to choose

### Argon2 (Recommended)

**Best For:** New applications, high security requirements

```python
hashed = hash_password("password", scheme="argon2")
# $argon2id$v=19$m=65536,t=2,p=4$...
```

**Characteristics:**
- Memory-hard (resistant to GPU/ASIC attacks)
- Time-based security
- Won PHC (Password Hashing Competition) in 2015
- No character length limitations
- ~50ms per hash with default settings

**Installation:** `uv add argon2-cffi`

**Pros:**
- Most secure modern algorithm
- Resistant to GPU and ASIC attacks
- No character length limits
- Customizable time/memory/parallelism parameters
- Future-proof

**Cons:**
- Requires external library
- Uses more memory (~64MB default)
- Slightly slower than bcrypt

**When to Use:**
- New applications
- High-security requirements
- You want the best modern algorithm
- Willing to accept slight performance overhead

### Scrypt

**Best For:** Memory-hard requirements, GPU-resistant hashing

```python
hashed = hash_password("password", scheme="scrypt")
# scrypt$base64salt$base64hash
```

**Characteristics:**
- Memory-hard and GPU-resistant
- Time-based security
- Proven design (since 2009)
- Good performance/security tradeoff
- ~30ms per hash with default settings

**Installation:** `uv add scrypt`

**Pros:**
- GPU-resistant (memory-hard)
- Fast and efficient
- Proven security
- Good middle ground

**Cons:**
- Less widely adopted than bcrypt
- Requires external library
- Fewer implementation options

**When to Use:**
- Need GPU-resistance
- Want lighter memory usage than argon2
- Performance is a concern

### PBKDF2

**Best For:** Lightweight applications, no extra dependencies

```python
hashed = hash_password("password", scheme="pbkdf2_sha256")
# pbkdf2$sha256$600000$base64salt$base64hash
```

**Characteristics:**
- Key derivation function (not designed for passwords, but usable)
- Time-based security (600,000 iterations)
- Built into Python (no external dependency)
- Fast (~5ms per hash)
- NIST-approved

**Installation:** None (built-in)

**Pros:**
- No external dependency
- Lightweight
- NIST approved
- Fast
- Simple implementation

**Cons:**
- Not memory-hard (can be parallelized)
- Iteration count must increase over time
- Not designed specifically for passwords

**When to Use:**
- Embedded systems with dependency constraints
- Lightweight applications
- No extra dependencies acceptable
- Performance critical

### Quick Decision Matrix

| Requirement | Algorithm | Reason |
|---|---|---|
| **New app** | Argon2 | Most secure, future-proof |
| **Best compatibility** | Bcrypt | Industry standard |
| **GPU-resistant** | Scrypt | Memory-hard |
| **No dependencies** | PBKDF2 | Built-in |
| **Not sure** | Bcrypt | Safe default |
| **Highest security** | Argon2 | Resistant to all attacks |
| **Performance priority** | PBKDF2 | Fastest |

## Usage Examples

### User Registration

```python
from sillo import silloApp, Query
from sillo.hashing import validate_password
from sillo.users import User

app = silloApp()

@app.post("/register")
async def register(
    request,
    response,
    username: str = Query(...),
    email: str = Query(...),
    password: str = Query(...),
):
    """Register a new user."""
    
    # Validate password strength
    errors = validate_password(password)
    if errors:
        return response.json(
            {"errors": errors},
            status_code=400,
        )
    
    # Check if user exists
    existing = await User.get_or_none(email=email)
    if existing:
        return response.json(
            {"error": "Email already registered"},
            status_code=400,
        )
    
    # Create user with hashed password
    user = User(username=username, email=email)
    user.set_password(password)  # Hashes automatically
    await user.save()
    
    return response.json(
        {"user_id": user.id, "username": username},
        status_code=201,
    )
```

### User Login with Progressive Rehashing

```python
from sillo.hashing import needs_rehash, get_available_schemes_list, set_default_scheme

# Setup: use argon2 if available
if "argon2" in get_available_schemes_list():
    set_default_scheme("argon2")

@app.post("/login")
async def login(
    request,
    response,
    email: str = Query(...),
    password: str = Query(...),
):
    """Login user and optionally rehash old passwords."""
    
    user = await User.get_or_none(email=email)
    
    # Check password
    if not user or not user.check_password(password):
        return response.json(
            {"error": "Invalid email or password"},
            status_code=401,
        )
    
    # Progressive rehashing: upgrade old hashes to new algorithm
    if needs_rehash(user.password_hash):
        user.set_password(password)  # Rehashes with new algorithm
        await user.save()
    
    # Generate JWT token
    token = generate_jwt_token(user)
    return response.json({"token": token})
```

### Change Password

```python
@app.post("/change-password")
async def change_password(
    request,
    response,
    old_password: str = Query(...),
    new_password: str = Query(...),
    user_id: str = Query(...),  # From JWT
):
    """Change user password."""
    
    user = await User.get_or_none(id=user_id)
    if not user:
        return response.json({"error": "User not found"}, status_code=404)
    
    # Verify old password
    if not user.check_password(old_password):
        return response.json(
            {"error": "Current password is incorrect"},
            status_code=401,
        )
    
    # Validate new password
    errors = validate_password(new_password)
    if errors:
        return response.json({"errors": errors}, status_code=400)
    
    # Check it's different
    if old_password == new_password:
        return response.json(
            {"error": "New password must be different"},
            status_code=400,
        )
    
    # Update password
    user.set_password(new_password)
    await user.save()
    
    return response.json({"message": "Password updated"})
```

### Password Reset

```python
from sillo.hashing import make_unusable_password

@app.post("/request-password-reset")
async def request_reset(request, response, email: str = Query(...)):
    """Request password reset."""
    
    user = await User.get_or_none(email=email)
    if not user:
        # Don't reveal if user exists
        return response.json({"message": "If email exists, reset link sent"})
    
    # Generate reset token (JWT or other)
    reset_token = generate_reset_token(user)
    
    # Save token (in cache or database)
    await cache.set(f"reset:{reset_token}", user.id, ttl=3600)
    
    # Send email with reset link
    await send_password_reset_email(user.email, reset_token)
    
    return response.json({"message": "Reset link sent to email"})

@app.post("/reset-password")
async def reset_password(
    request,
    response,
    token: str = Query(...),
    new_password: str = Query(...),
):
    """Complete password reset."""
    
    # Verify token
    user_id = await cache.get(f"reset:{token}")
    if not user_id:
        return response.json(
            {"error": "Reset link expired or invalid"},
            status_code=400,
        )
    
    # Validate new password
    errors = validate_password(new_password)
    if errors:
        return response.json({"errors": errors}, status_code=400)
    
    # Update password
    user = await User.get(id=user_id)
    user.set_password(new_password)
    await user.save()
    
    # Invalidate token
    await cache.delete(f"reset:{token}")
    
    return response.json({"message": "Password reset successfully"})
```

### Admin User Creation

```python
from sillo.users import UserManager

@app.post("/create-admin")
async def create_admin(
    request,
    response,
    username: str = Query(...),
    email: str = Query(...),
    password: str = Query(...),
):
    """Create admin user (validates password)."""
    
    # Use UserManager for validation
    try:
        admin = await User.objects.create_superuser(
            username=username,
            email=email,
            password=password,
        )
        return response.json({
            "admin_id": admin.id,
            "username": admin.username,
        }, status_code=201)
    except ValueError as e:
        # Password validation failed
        return response.json({"error": str(e)}, status_code=400)
```

## Configuration

### Setting Default Algorithm

```python
from sillo.hashing import set_default_scheme

# In your app startup
set_default_scheme("argon2")

# All subsequent hash_password() calls use argon2
```

### Checking Available Algorithms

```python
from sillo.hashing import get_available_schemes_list

schemes = get_available_schemes_list()
print(f"Installed: {schemes}")

# Use this to enable features conditionally
if "argon2" in schemes:
    use_argon2 = True
```

### Advanced: Custom Password Strength Requirements

```python
from sillo.hashing import validate_password

def my_validate_password(password: str) -> list[str]:
    """Custom validation with stricter requirements."""
    
    errors = []
    
    # Use default validation
    errors.extend(validate_password(password, min_length=12))
    
    # Add custom rules
    if password.count(password[0]) > len(password) * 0.3:
        errors.append("Password has too many repeated characters")
    
    return errors

# Use in registration
@app.post("/register")
async def register(request, response, password: str = Query(...)):
    errors = my_validate_password(password)
    if errors:
        return response.json({"errors": errors}, status_code=400)
    # ... continue registration
```

## Best Practices

### Security

1. **Always hash passwords** - Never store plaintext
2. **Use argon2 for new apps** - Most secure modern algorithm
3. **Verify on login** - Don't skip the verification step
4. **Use HTTPS** - Always encrypt in transit
5. **Rate limit logins** - Protect against brute-force
6. **Enforce complexity** - Use `validate_password()`
7. **Progressive rehashing** - Upgrade old hashes on login
8. **Keep algorithms updated** - Install new packages as they're released

### Performance

1. **Hash only passwords** - Don't hash other data
2. **Cache user lookups** - Don't query DB per hash check
3. **Rehash asynchronously** - Don't make login slower
4. **Use defaults** - They're tuned for balance
5. **Monitor login times** - Alert if times increase unexpectedly

### Maintenance

1. **Test password reset** - Ensure the flow works
2. **Log auth failures** - For security monitoring
3. **Document requirements** - Tell users password rules
4. **Plan migrations** - How to upgrade algorithms
5. **Backup user data** - In case of emergency reset

## FAQ

**Q: Which algorithm should I use?**
A: Use argon2 for new applications. Use bcrypt if you need maximum compatibility.

**Q: Can I change algorithms?**
A: Yes! Use `needs_rehash()` to detect old hashes and upgrade them on login.

**Q: What about password length limits?**
A: Bcrypt has a 72-byte limit. Argon2 and scrypt don't. PBKDF2 doesn't.

**Q: Is PBKDF2 secure?**
A: Yes, but argon2 and scrypt are better due to memory hardness.

**Q: Why does argon2 take so long?**
A: Intentionally slow to resist brute-force attacks. This is a feature.

**Q: Can I use multiple algorithms?**
A: Yes! `verify_password()` auto-detects. Mix algorithms freely.

**Q: How do I handle older hashes?**
A: Use progressive rehashing: detect with `needs_rehash()`, rehash on next login.

**Q: What if a user forgets their password?**
A: Use `make_unusable_password()` temporarily, send reset link, have them set new password.

**Q: Is timing attack protection important?**
A: Yes, use `constant_time_compare()` for secrets. Already used in `verify_password()`.

**Q: How often should I rehash?**
A: Gradually as users log in. Don't force immediate rehashing.

## Migration Guide

### From Other Frameworks

**Django:**
```python
# Old Django code
from django.contrib.auth.hashers import make_password, check_password

# New Sillo code
from sillo.hashing import hash_password, verify_password

# Compatible API!
hashed = hash_password("password")
verify_password("password", hashed)
```

**Flask-Security:**
```python
# Old Flask-Security code
from flask_security import hash_password, verify_password

# New Sillo code
from sillo.hashing import hash_password, verify_password

# Same names and behavior!
```

### From Bcrypt Only

```python
# Old code (bcrypt only)
import bcrypt

hash = bcrypt.hashpw(b"password", bcrypt.gensalt())

# New code (multi-algorithm)
from sillo.hashing import hash_password, verify_password

hash = hash_password("password")  # Still bcrypt by default

# Opt in to argon2 when ready
set_default_scheme("argon2")
hash = hash_password("password")  # Now argon2
```

## Troubleshooting

**Problem: `InvalidSchemeError: Scheme 'argon2' is not available`**

Solution: Install argon2-cffi
```bash
uv add argon2-cffi
```

**Problem: Password verification always fails**

Check:
1. Is `verify_password()` being used? (not `check_password()` on wrong hash)
2. Is the hash valid? (not corrupted or truncated)
3. Are there leading/trailing whitespace characters?

```python
# Debug
from sillo.hashing import verify_password

print(f"Hash: '{user.password_hash}'")
print(f"Length: {len(user.password_hash)}")
print(f"Verifies: {verify_password('password', user.password_hash)}")
```

**Problem: Login is slow**

Causes:
1. Hash computation is slow by design (use case: password is correct, need to verify)
2. Database query is slow (add indexing)
3. Rehashing on every login (use `needs_rehash()` to avoid unnecessary work)

**Problem: `verify_password()` returns False but password is correct**

Check:
1. Is there a typo in the password?
2. Did you copy the hash correctly (no truncation)?
3. Is the hash corrupted (invalid characters)?
4. Did the hash algorithm change (e.g., plaintext stored)?

## See Also

- [User Authentication](/guides/authentication) - Complete auth guide
- [User Model](/guides/users) - sillo.users documentation
- [Permissions](/guides/permissions) - Access control
- [Sessions](/guides/sessions) - Session management
- [Security](/guides/security) - Security best practices
