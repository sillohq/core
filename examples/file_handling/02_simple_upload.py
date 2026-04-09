from nexios import NexiosApp
from nexios.http import Request, Response

app = NexiosApp()


@app.post("/upload")
async def upload_files(req: Request, res: Response) -> Response:
    files = await req.files
    uploaded = []

    for name, file in files.items():
        # Simulate file processing
        uploaded.append(
            {
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(await file.read()),
            }
        )

    return res.json({"uploaded": uploaded})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5000, reload=True)
