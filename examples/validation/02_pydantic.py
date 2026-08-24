from pydantic import BaseModel, EmailStr, ValidationError

from sillo import SilloApp
from sillo.core.http import Request, Response

app = SilloApp()


class UserRegistration(BaseModel):
    username: str
    email: EmailStr
    age: int


@app.post("/register")
async def register_user(req: Request, res: Response) -> Response:
    try:
        data = await req.json
        user = UserRegistration(**data)
        return res.json({"status": "success", "user": user.model_dump()})
    except ValidationError as e:
        return res.json({"error": str(e)}, status_code=422)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
