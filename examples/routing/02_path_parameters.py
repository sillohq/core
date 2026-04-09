from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


@app.get("/items/{item_id}")
async def get_item(req: Request, res: Response):
    item_id = req.path_params["item_id"]
    return {"item_id": item_id}


@app.post("/items/{item_id}")
async def create_item(req: Request, res: Response):
    item_id = req.path_params["item_id"]
    item_data = await req.json
    return res.json({"item_id": item_id, "data": item_data}, status_code=201)


@app.get("/products/{product_id:int}")
async def get_product(req: Request, res: Response):
    product_id = req.path_params["product_id"]
    return res.json({"product_id": product_id, "type": "integer"})


@app.get("/categories/{category_name:str}")
async def get_category(req: Request, res: Response):
    category_name = req.path_params["category_name"]
    return res.json({"category_name": category_name, "type": "string"})


@app.get("/prices/{price:float}")
async def get_price(req: Request, res: Response):
    price = req.path_params["price"]
    return res.json({"price": price, "type": "float"})


@app.get("/uuids/{uuid_value:uuid}")
async def get_uuid(req: Request, res: Response):
    uuid_value = req.path_params["uuid_value"]
    return res.json({"uuid": str(uuid_value), "type": "UUID"})


@app.get("/slugs/{slug_value:slug}")
async def get_slug(req: Request, res: Response):
    slug_value = req.path_params["slug_value"]
    return res.json({"slug": slug_value, "type": "slug"})


@app.get("/wildcard/{wildcard_path:path}")
async def get_wildcard(req: Request, res: Response):
    wildcard_path = req.path_params["wildcard_path"]
    return res.json({"wildcard_path": wildcard_path, "type": "path"})
