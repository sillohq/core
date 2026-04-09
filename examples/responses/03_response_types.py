from nexios import NexiosApp

app = NexiosApp()


@app.get("/text")
async def test_handler(req, res):
    return res.text("Hello, World!")


@app.get("/html")
async def html_handler(req, res):
    return res.html("<h1>Hello, World!</h1>")


@app.get("/json")
async def json_handler(req, res):
    return res.json({"message": "Hello, World!"})


@app.get("/file")
async def file_handler(req, res):
    return res.file("examples/respons/index.html")


@app.get("/raw")
async def raw_handler(req, res):
    return res.resp(b"Hello, World!", content_type="text/plain")
