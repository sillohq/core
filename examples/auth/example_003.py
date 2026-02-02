from nexios import NexiosApp
from nexios.auth.base import AuthenticationBackend
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.users.base import BaseUser
from nexios.auth.users.simple import UnauthenticatedUser
from nexios.http import Request, Response


class CustomUser(BaseUser):
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
        # Load user by token - replace with your database logic
        user_data = await db.get_user_by_token(identity)
        if user_data:
            return cls(id=user_data["id"], username=user_data["username"])
        return None


class db:
    @classmethod
    async def get_user_by_token(cls, token):
        # Mock database - replace with your actual database
        # In real implementation, you'd validate the token and get user data
        if token == "valid-token-123":
            return {"id": "123", "username": "example_user"}
        return None


class CustomAuthBackend(AuthenticationBackend):
    async def authenticate(self, request: Request, response: Response):
        custom_token = request.headers.get("X-Custom-Token")

        if not custom_token:
            return UnauthenticatedUser(), "no-auth"

        # Validate token and return identity for middleware to load user
        if custom_token == "valid-token-123":
            return "123", "custom-auth"  # Return identity, let middleware load user

        return UnauthenticatedUser(), "no-auth"


app = NexiosApp()

# Custom backend
custom_backend = CustomAuthBackend()

app.add_middleware(
    AuthenticationMiddleware(user_model=CustomUser, backend=custom_backend)
)


@app.get("/")
async def home(req: Request, res: Response):
    return res.html("""
    <h1>Custom Authentication Example</h1>
    <p>Try adding the header: <code>X-Custom-Token: valid-token-123</code></p>
    <a href="/secure">Go to secure endpoint</a>
    """)


@app.get("/secure")
async def secure_endpoint(req: Request, res: Response):
    if req.user and req.user.is_authenticated:
        return res.json(
            {"message": f"Welcome to the secure endpoint, {req.user.display_name}!"}
        )
    return res.html(
        """
    <h1>Access Denied</h1>
    <p>Add the header <code>X-Custom-Token: valid-token-123</code> to access this page.</p>
    <a href="/">Go back</a>
    """,
        status_code=401,
    )


@app.get("/login")
async def login_form(req: Request, res: Response):
    return res.html("""
    <h1>Login</h1>
    <form action="/login" method="post">
        <label>Token: <input type="text" name="token" placeholder="valid-token-123"></label>
        <input type="submit" value="Login">
    </form>
    """)


@app.post("/login")
async def login_post(req: Request, res: Response):
    form_data = await req.form
    token = form_data.get("token")

    if token == "valid-token-123":
        # In a real app, you'd set the token in a cookie or redirect to a page
        # that sets the X-Custom-Token header
        return res.html(f"""
        <h1>Login Successful!</h1>
        <p>Add this header to your requests: <code>X-Custom-Token: {token}</code></p>
        <a href="/secure">Go to secure endpoint</a>
        """)

    return res.html("Invalid token", status_code=401)
