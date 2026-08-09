from sillo import SilloApp

app = SilloApp()


@app.route("/")
async def index(req, res):
    return res.json(
        {"message": "Hello, World!"},
        status_code=200,
        headers={"X-Custom-Header": "sillo"},
    )
