from sillo import silloApp

app = silloApp()


@app.post("/upload")
async def upload_file(req, res):
    data = b""
    async for chunk in req.stream():
        data += chunk
    print(data.decode())
    return {"status": "stream received"}
