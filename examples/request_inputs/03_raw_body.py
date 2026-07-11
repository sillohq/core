from sillo import silloApp

app = silloApp()


@app.post("/upload")
async def process_raw_input(req, res):
    data = await req.body
    print(data.decode())
    return {"status": "success"}
