from nexios import NexiosApp
from nexios.auth import BaseUser
from nexios.auth.backends.jwt import JWTAuthBackend, create_jwt
from nexios.auth.backends.session import SessionAuthBackend, login
from nexios.auth.decorator import auth
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.http import Request, Response


class User(BaseUser):
    def __init__(self, id: str, username: str):
        self.id = id
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def identity(self) -> str:
        return self.id

    @property
    def display_name(self) -> str:
        return self.username

    @classmethod
    async def load_user(cls, identity: str):
        # Replace with your database lookup
        user_data = await db.get_user(identity)
        if user_data:
            return cls(id=user_data["id"], username=user_data["username"])
        return None


class db:
    @classmethod
    async def get_user(cls, user_id):
        # Mock database - replace with your actual database
        return {"id": user_id, "username": "admin"}


app = NexiosApp()

# Multiple backends - JWT and Session
jwt_backend = JWTAuthBackend()
session_backend = SessionAuthBackend()

app.add_middleware(
    AuthenticationMiddleware(
        user_model=User,
        backend=[jwt_backend, session_backend],  # Try JWT first, then session
    )
)


@app.get("/login")
async def login_form(req: Request, res: Response):
    return res.html("""
    <h1>Login</h1>
    <div>
        <h2>JWT Login</h2>
        <form action="/login/jwt" method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <input type="submit" value="Login with JWT">
        </form>
    </div>
    <div>
        <h2>Session Login</h2>
        <form action="/login/session" method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <input type="submit" value="Login with Session">
        </form>
    </div>
    """)


@app.post("/login/jwt")
async def jwt_login(req: Request, res: Response):
    form_data = await req.form
    username = form_data.get("username")
    password = form_data.get("password")

    # Validate credentials (replace with your logic)
    if username == "admin" and password == "password":

        token = create_jwt({"sub": "123"})
        return res.html(f"""
            <h1>JWT Login Successful!</h1>
            <p>Your JWT token: <code>{token}</code></p>
            <p>Add this to your request headers: <code>Authorization: Bearer {token}</code></p>
            <a href="/dashboard">Go to Dashboard</a>
            """)

    return res.html("Invalid credentials", status_code=401)


@app.post("/login/session")
async def session_login(req: Request, res: Response):
    form_data = await req.form
    username = form_data.get("username")
    password = form_data.get("password")

    # Validate credentials (replace with your logic)
    if username == "admin" and password == "password":

        login(req, User(id="123", username="user", password="password"))
        return res.redirect("/dashboard")

    return res.html("Invalid credentials", status_code=401)


@app.get("/dashboard")
@auth()  # Accepts any authenticated user (JWT or Session)
async def admin_dashboard(req: Request, res: Response):
    auth_method = req.scope.get("auth", "unknown")
    return res.html(f"""
    <h1>Admin Dashboard</h1>
    <p>Welcome, {req.user.display_name}!</p>
    <p>Authentication method: {auth_method}</p>
    <p><a href="/user-profile">User Profile</a> | <a href="/logout">Logout</a></p>
    """)


@app.get("/user-profile")
@auth()  # Accepts any authenticated user
async def user_profile(req: Request, res: Response):
    auth_method = req.scope.get("auth", "unknown")
    return res.html(f"""
    <h1>User Profile</h1>
    <p>Hello, {req.user.display_name}!</p>
    <p>User ID: {req.user.identity}</p>
    <p>Authentication method: {auth_method}</p>
    <p><a href="/dashboard">Dashboard</a> | <a href="/logout">Logout</a></p>
    """)


@app.get("/jwt-only")
@auth(["jwt"])  # Only accepts JWT authentication
async def jwt_only(req: Request, res: Response):
    return res.html(f"""
    <h1>JWT Only Page</h1>
    <p>This page requires JWT authentication!</p>
    <p>Authenticated via: {req.scope.get("auth", "unknown")}</p>
    <p><a href="/dashboard">Dashboard</a></p>
    """)


@app.get("/session-only")
@auth(["session"])  # Only accepts session authentication
async def session_only(req: Request, res: Response):
    return res.html(f"""
    <h1>Session Only Page</h1>
    <p>This page requires session authentication!</p>
    <p>Authenticated via: {req.scope.get("auth", "unknown")}</p>
    <p><a href="/dashboard">Dashboard</a></p>
    """)


@app.get("/logout")
async def logout(req: Request, res: Response):
    from nexios.auth.backends.session import logout

    logout(req)
    return res.redirect("/login")
