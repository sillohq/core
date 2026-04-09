import mimetypes
import os
import uuid
from pathlib import Path

import aiofiles

from nexios import NexiosApp
from nexios.http import Request, Response
from nexios.responses import FileResponse, StreamingResponse

app = NexiosApp()

# Configure upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_safe_filename(filename: str) -> str:
    """Generate a safe filename with UUID to prevent conflicts"""
    ext = Path(filename).suffix
    return f"{uuid.uuid4()}{ext}"


async def save_upload_file(file, filename: str) -> Path:
    """Save an uploaded file to disk"""
    filepath = UPLOAD_DIR / filename
    async with aiofiles.open(filepath, "wb") as f:
        while chunk := await file.read(8192):
            await f.write(chunk)
    return filepath


@app.post("/upload")
async def upload_file(request: Request, response: Response) -> Response:
    # Get uploaded files
    files = await request.files

    if not files:
        return response.json({"error": "No files uploaded"}, status_code=400)

    uploaded_files = []
    for file_field, file in files.items():
        # Generate safe filename
        safe_filename = get_safe_filename(file.filename)

        # Save file
        filepath = await save_upload_file(file, safe_filename)

        uploaded_files.append(
            {
                "original_name": file.filename,
                "saved_name": safe_filename,
                "content_type": file.content_type,
                "size": os.path.getsize(filepath),
            }
        )

    return response.json(
        {
            "message": f"Successfully uploaded {len(uploaded_files)} files",
            "files": uploaded_files,
        }
    )


@app.get("/files")
async def list_files(request: Request, response: Response) -> Response:
    files = []
    for filepath in UPLOAD_DIR.glob("*"):
        if filepath.is_file():
            files.append(
                {
                    "name": filepath.name,
                    "size": filepath.stat().st_size,
                    "content_type": mimetypes.guess_type(filepath)[0],
                    "uploaded_at": datetime.fromtimestamp(
                        filepath.stat().st_mtime
                    ).isoformat(),
                }
            )

    return response.json({"files": files, "total": len(files)})


@app.get("/files/{filename}")
async def download_file(request: Request, response: Response) -> FileResponse:
    filename = request.path_params["filename"]
    filepath = UPLOAD_DIR / filename

    if not filepath.exists():
        return response.json({"error": "File not found"}, status_code=404)

    return FileResponse(
        filepath, filename=filename, content_type=mimetypes.guess_type(filepath)[0]
    )


@app.get("/stream/{filename}")
async def stream_file(request: Request, response: Response) -> StreamingResponse:
    filename = request.path_params["filename"]
    filepath = UPLOAD_DIR / filename

    if not filepath.exists():
        return response.json({"error": "File not found"}, status_code=404)

    async def file_streamer():
        async with aiofiles.open(filepath, "rb") as f:
            while chunk := await f.read(8192):
                yield chunk

    return StreamingResponse(
        file_streamer(), media_type=mimetypes.guess_type(filepath)[0]
    )


@app.delete("/files/{filename}")
async def delete_file(request: Request, response: Response) -> Response:
    filename = request.path_params["filename"]
    filepath = UPLOAD_DIR / filename

    if not filepath.exists():
        return response.json({"error": "File not found"}, status_code=404)

    try:
        filepath.unlink()
        return response.json({"message": f"Successfully deleted {filename}"})
    except Exception as e:
        return response.json(
            {"error": f"Failed to delete file: {str(e)}"}, status_code=500
        )


# Serve a simple upload form
@app.get("/")
async def upload_form(request: Request, response: Response) -> Response:
    html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>File Upload Example</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .upload-form { border: 2px dashed #ccc; padding: 20px; margin: 20px 0; }
                .file-list { margin-top: 20px; }
                .file-item { border: 1px solid #eee; padding: 10px; margin: 5px 0; }
            </style>
        </head>
        <body>
            <h1>File Upload Example</h1>
            
            <div class="upload-form">
                <h2>Upload Files</h2>
                <form action="/upload" method="post" enctype="multipart/form-data">
                    <input type="file" name="files" multiple>
                    <button type="submit">Upload</button>
                </form>
            </div>
            
            <div class="file-list">
                <h2>Uploaded Files</h2>
                <div id="files"></div>
            </div>
            
            <script>
                // Fetch and display uploaded files
                async function loadFiles() {
                    const response = await fetch('/files');
                    const data = await response.json();
                    
                    const filesDiv = document.getElementById('files');
                    filesDiv.innerHTML = data.files.map(file => `
                        <div class="file-item">
                            <strong>${file.name}</strong>
                            <br>
                            Size: ${(file.size / 1024).toFixed(2)} KB
                            <br>
                            Type: ${file.content_type || 'unknown'}
                            <br>
                            <a href="/files/${file.name}" target="_blank">Download</a>
                            |
                            <a href="/stream/${file.name}" target="_blank">Stream</a>
                            |
                            <button onclick="deleteFile('${file.name}')">Delete</button>
                        </div>
                    `).join('');
                }
                
                async function deleteFile(filename) {
                    if (!confirm('Are you sure you want to delete this file?')) return;
                    
                    await fetch(`/files/${filename}`, { method: 'DELETE' });
                    loadFiles();
                }
                
                // Load files on page load
                loadFiles();
            </script>
        </body>
    </html>
    """
    return response.html(html)
