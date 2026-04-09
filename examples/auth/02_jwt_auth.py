from nexios import NexiosApp
from nexios.auth.backends.jwt import JWTAuthBackend, create_jwt
from nexios.auth.base import BaseUser
from nexios.auth.middleware import AuthenticationMiddleware
from nexios.http import Request, Response


class User(BaseUser):
    def __init__(self, id: str, username: str, email: str):
        self.id = id
        self.username = username
        self.email = email

    @property
    def identity(self) -> str:
        return self.id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @classmethod
    async def load_user(cls, identity: str):
        # Load user by ID - replace with your database logic
        user_data = await db.get_user(identity)
        if user_data:
            return cls(
                id=user_data["id"],
                username=user_data["username"],
                email=user_data["email"],
            )
        return None


class db:
    @classmethod
    async def get_user(cls, user_id):
        # Mock database - replace with your actual database
        return {"id": user_id, "username": "admin", "email": "admin@example.com"}


app = NexiosApp()

# JWT backend - no authenticate_func needed
jwt_backend = JWTAuthBackend()

app.add_middleware(AuthenticationMiddleware(user_model=User, backend=jwt_backend))


@app.route("/login", methods=["GET", "POST"])
async def login(req: Request, res: Response):
    if req.method == "GET":
        return """
        <form action="/login" method="post">
            <label>Username: <input type="text" name="username"></label>
            <label>Password: <input type="password" name="password"></label>
            <input type="submit" value="Login">
        </form>
        """
    else:
        form_data = await req.form
        username = form_data.get("username")
        password = form_data.get("password")

        # Validate credentials (replace with your logic)
        if username == "admin" and password == "password":

            token = create_jwt({"sub": "123"})
            return res.json({"token": token})

        return res.html("Invalid username or password", status_code=401)


@app.route("/logout", methods=["POST"])
async def logout(req: Request, res: Response):
    return res.redirect("/login")


@app.route("/protected")
async def protected(req: Request, res: Response):
    if req.user and req.user.is_authenticated:
        return res.html(f"Hello, {req.user.display_name}!")
    return res.redirect("/login")
