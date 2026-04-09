from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


async def log_request(req: Request, res: Response, next) -> None:
    print(f"Request received: {req.method} {req.path}")
    await next()
    print(f"Response sent: {res.status_code}")


app.add_middleware(log_request)


@app.post("/stream")
async def handle_stream(req: Request, res: Response) -> Response:
    total_size = 0
    async for chunk in req.stream():
        total_size += len(chunk)

    return res.json({"status": "success", "bytes_received": total_size})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
