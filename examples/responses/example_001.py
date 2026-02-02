from typing import Any, Dict, List, Union

from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


@app.route("/")
def index(req: Request, res: Response) -> Dict[str, str]:
    return {"message": "Hello, World!"}


@app.route("/list")
def list_items(req: Request, res: Response) -> List[str]:
    return ["item1", "item2", "item3"]


@app.route("/string")
def string(req: Request, res: Response) -> str:
    return "Hello, World!"
