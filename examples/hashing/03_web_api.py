"""Password hashing in a web API example.

Run with:
    uv run uvicorn examples/hashing/03_web_api:app --reload
"""

from sillo import SilloApp, Query
from sillo.objects.http import Request, Response
from sillo.hashing import hash_password, verify_password, needs_update

app = SilloApp(title="Password Hashing API Example")


@app.get("/")
async def home(request: Request, response: Response):
    """Home endpoint."""
    return response.json({
        "title": "Password Hashing API",
        "endpoints": [
            "POST /register?username=user&password=pass123",
            "POST /login?username=user&password=pass123",
            "POST /change-password?username=user&old_password=pass123&new_password=newpass456",
        ],
    })


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

    if len(username) < 3:
        return response.json(
            {"error": "Username must be at least 3 characters"},
            status_code=400,
        )

    hashed_password = hash_password(password)

    print(f"User registered: {username}")
    print(f"Password hash (bcrypt): {hashed_password}")

    return response.json({
        "message": "User registered successfully",
        "user_id": "user_123",
        "username": username,
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
            "username": username,
        })
    else:
        return response.json(
            {"error": "Invalid credentials"},
            status_code=401,
        )


@app.post("/change-password")
async def change_password(
    request: Request,
    response: Response,
    username: str = Query(...),
    old_password: str = Query(...),
    new_password: str = Query(...),
):
    """Change user password."""
    stored_hash = "$2b$12$R9h7cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jKMUi"

    if not verify_password(old_password, stored_hash):
        return response.json(
            {"error": "Current password is incorrect"},
            status_code=401,
        )

    if len(new_password) < 8:
        return response.json(
            {"error": "New password must be at least 8 characters"},
            status_code=400,
        )

    if old_password == new_password:
        return response.json(
            {"error": "New password must be different from current password"},
            status_code=400,
        )

    new_hash = hash_password(new_password)

    print(f"Password changed for user: {username}")
    print(f"New password hash: {new_hash}")

    return response.json({
        "message": "Password updated successfully",
        "username": username,
    })


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
