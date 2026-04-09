from nexios import NexiosApp
from nexios.http.response import (
    BaseResponse,
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
)

app = NexiosApp()


@app.get("/json")
async def json_handler(req, res):
    return JSONResponse({"message": "Hello, World!"})


@app.get("/html")
async def html_handler(req, res):
    return HTMLResponse("<h1>Hello, World!</h1>")


@app.get("/text")
async def text_handler(req, res):
    return PlainTextResponse("Hello, World!", content_type="text/plain")


@app.get("/file")
async def file_handler(req, res):
    return FileResponse(
        "examples/respons/example_004.py", content_disposition_type="attachment"
    )


@app.get("/raw")
async def raw_handler(req, res):
    return BaseResponse(b"Hello, World!", content_type="text/plain")
