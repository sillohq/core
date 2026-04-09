from nexios import NexiosApp
from nexios.routing import Router

app = NexiosApp()

v1_router = Router(prefix="/v1")
v2_router = Router(prefix="/v2")


@v1_router.get("/")
async def v1_index(req, res):
    return res.text("Hello from v1")


@v2_router.get("/")
async def v2_index(req, res):
    return res.text("Hello from v2")


app.mount_router(v1_router)
app.mount_router(v2_router)
