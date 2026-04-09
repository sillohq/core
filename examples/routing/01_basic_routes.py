from typing import Any, Dict

from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


@app.get("/")
async def index(request: Request, response: Response) -> Dict[str, Any]:
    return {"message": "Hello World", "method": request.method}


@app.post("/")
async def post_index(request: Request, response: Response) -> Dict[str, Any]:
    return {"message": "Hello World", "method": request.method}


@app.put("/")
async def put_index(request: Request, response: Response) -> Dict[str, Any]:
    return {"message": "Hello World", "method": request.method}


@app.delete("/")
async def delete_index(request: Request, response: Response) -> Dict[str, Any]:
    return {"message": "Hello World", "method": request.method}


@app.route("/custom", methods=["PATCH"])
async def patch_index(request: Request, response: Response) -> Dict[str, Any]:
    return {"message": "Hello World", "method": request.method}
