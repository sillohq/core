from nexios import NexiosApp
from nexios.auth.backends.session import SessionAuthBackend, login
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.auth.users.base import BaseUser


class User(BaseUser):
    def __init__(self, id: str, username: str, password: str):
        self.id = id
        self.username = username
        self.password = password

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def identity(self) -> str:
        return self.id

    @property
    def display_name(self) -> str:
        return self.username

    def check_password(self, password: str) -> bool:
        return self.password == password

    @classmethod
    async def load_user(cls, identity: str):
        # Load user by ID - replace with your database logic
        user_data = await db.get_user(identity)
        if user_data:
            return cls(
                id=user_data["id"],
                username=user_data["username"],
                password=user_data["password"],
            )
        return None


class db:
    @classmethod
    async def get_user(cls, user_id):
        # Mock database - replace with your actual database
        return {"id": user_id, "username": "user", "password": "password"}

    @classmethod
    async def get_by_email(cls, email):
        return {"id": "123", "username": "user", "password": "password"}


app = NexiosApp()

# Session backend - no authenticate_func needed
session_backend = SessionAuthBackend()

app.add_middleware(AuthenticationMiddleware(user_model=User, backend=session_backend))


@app.get("/login")
async def login(req, res):
    return """
    <form action="/login" method="post">
        <label>Username: <input type="text" name="username"></label>
        <label>Password: <input type="password" name="password"></label>
        <input type="submit" value="Login">
    </form>
    """


@app.post("/login")
async def login_post(req, res):
    form_data = await req.form
    username = form_data.get("username")
    password = form_data.get("password")

    # Validate credentials (replace with your logic)
    if username == "admin" and password == "password":
        login(req, User(id="123", username="user", password="password"))
        return res.redirect("/protected")

    return res.html("Invalid username or password", status_code=401)


@app.get("/protected")
async def protected(req, res):
    if req.user and req.user.is_authenticated:
        return res.html(f"Hello, {req.user.display_name}!")
    return res.redirect("/login")


@app.get("/logout")
async def logout(req, res):
    from nexios.auth.backends.session import logout

    logout(req)
    return res.redirect("/login")
