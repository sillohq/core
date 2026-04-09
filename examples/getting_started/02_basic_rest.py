from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


@app.get("/api/items")
async def get_items(req: Request, res: Response) -> Response:
    items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
    return res.json(items)


@app.get("/api/items/{item_id:int}")
async def get_item(req: Request, res: Response) -> Response:
    item_id = req.path_params.item_id
    return res.json({"id": item_id, "name": f"Item {item_id}"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
