"""
Example of getting and processing JSON data
"""

from pydantic import BaseModel, ValidationError

from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


class User(BaseModel):
    name: str
    age: int


@app.route("/json", methods=["POST"])
async def process_json(req: Request, res: Response) -> Response:
    try:
        data = await req.json
        user = User(**data)
        return res.json({"status": "success", "user": user.dict()})
    except ValidationError as e:
        return res.json({"error": str(e)}, status_code=422)
