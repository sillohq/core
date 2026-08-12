"""Basic password hashing example.

This demonstrates simple password hashing and verification using the default bcrypt algorithm.

Run with:
    uv run python 01_basic_password_hashing.py

Or with uvicorn:
    uv run uvicorn 01_basic_password_hashing:app --reload
"""

from sillo import SilloApp, Query
from sillo.core.http import Request, Response
from sillo.hashing import hash_password, verify_password

app = SilloApp(title="Password Hashing Example")


@app.post("/register")
async def register(
    request: Request,
    response: Response,
    username: str = Query(...),
    password: str = Query(...),
):
    """Register a new user with password hashing."""
    if len(password) < 8:
        return response.json(
            {"error": "Password must be at least 8 characters"},
            status_code=400,
        )

    hashed_password = hash_password(password)

    user = {
        "id": "user_123",
        "username": username,
        "password_hash": hashed_password,
    }

    print(f"User registered: {username}")
    print(f"Password hash: {hashed_password}")

    return response.json({
        "message": "User registered successfully",
        "user_id": "user_123",
    }, status_code=201)


@app.post("/login")
async def login(
    request: Request,
    response: Response,
    username: str = Query(...),
    password: str = Query(...),
):
    """Login with password verification."""
    stored_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUi"

    if verify_password(password, stored_hash):
        return response.json({
            "message": "Login successful",
            "token": "jwt_token_here",
        })
    else:
        return response.json(
            {"error": "Invalid credentials"},
            status_code=401,
        )


@app.get("/")
async def home(request: Request, response: Response):
    """Home endpoint."""
    return response.json({
        "message": "Password Hashing Example",
        "endpoints": [
            "POST /register?username=john&password=secret123",
            "POST /login?username=john&password=secret123",
        ],
    })


if __name__ == "__main__":
    password = "my_secure_password"
    hashed = hash_password(password)
    print(f"Password: {password}")
    print(f"Hash: {hashed}")
    print(f"Verify correct password: {verify_password(password, hashed)}")
    print(f"Verify wrong password: {verify_password('wrong_password', hashed)}")
