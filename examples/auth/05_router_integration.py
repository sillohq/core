from sillo import SilloApp
from sillo.auth import BaseUser, useAuth
from sillo.auth import JWTAuthBackend, create_jwt
from sillo.auth.middleware import AuthenticationMiddleware
from sillo.core.http import Request, Response
from sillo.core.routing import Router


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
        user_data = await db.get_user(identity)
        if user_data:
            return cls(id=user_data["id"], username=user_data["username"])
        return None


class db:
    @classmethod
    async def get_user(cls, user_id):
        return {"id": user_id, "username": "admin"}


jwt_backend = JWTAuthBackend()
app = SilloApp()
app.add_middleware(AuthenticationMiddleware(user_model=User, backend=jwt_backend))

auth_router = Router()


@auth_router.post("/login")
async def login(req: Request, res: Response) -> Response:
    credentials = await req.json
    if (
        credentials.get("username") == "admin"
        and credentials.get("password") == "secret"
    ):
        user = await User.load_user("123")
        if user:
            token = create_jwt({"sub": user.identity})
            return res.json({"token": token})

    return res.json({"error": "Invalid credentials"}, status_code=401)


@auth_router.get("/profile", auth=useAuth())
async def profile(req: Request, res: Response) -> Response:
    return res.json(
        {
            "message": f"Welcome, {req.user.display_name}!",
            "user_id": req.user.identity,
            "authenticated": req.user.is_authenticated,
        }
    )


@auth_router.get("/admin", auth=useAuth(schemes=["bearerAuth"]))
async def admin(req: Request, res: Response) -> Response:
    return res.json({"message": "Admin access granted", "user": req.user.display_name})


@auth_router.get("/feed", auth=useAuth(required=False))
async def feed(req: Request, res: Response) -> Response:
    return res.json({"authenticated": req.user.is_authenticated})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
