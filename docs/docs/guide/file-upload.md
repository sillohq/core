---
title: File Upload Documentation for Nexios Framework
description: This document provides a comprehensive guide to handling file uploads in the Nexios framework, covering both single and multiple file upload scenarios with proper validation and security considerations.
head:
  - - meta
    - property: og:title
      content: File Upload Documentation for Nexios Framework
  - - meta
    - property: og:description
      content: This document provides a comprehensive guide to handling file uploads in the Nexios framework, covering both single and multiple file upload scenarios with proper validation and security considerations.
---
# 📁 File Upload Documentation

### Single File Upload

To handle a single file upload in Nexios:

```python
from nexios.http import Request, Response

@app.post("/upload")
async def upload_file(request: Request, response: Response):
    files = await request.files
    if not files:
        return response.status(400).json({"error": "No files uploaded"})
    
    file = files["file"]  # 'file' is the field name in the form
    file_content = await file.read()
    
    # Save file or process it
    # ...
    
    return response.json({"filename": file.filename, "size": len(file_content)})
```

### Multiple File Uploads

For handling multiple files from the same field:

```python
@app.post("/uploads")
async def upload_files(request: Request, response: Response):
    files = await request.files
    if not files:
        return response.status(400).json({"error": "No files uploaded"})
    
    results = []
    for file in files.getlist("files"):  # 'files' is the field name
        file_content = await file.read()
        # Process each file
        results.append({
            "filename": file.filename,
            "size": len(file_content)
        })
    
    return response.json({"files": results})
```

## 🔒 Security Considerations



### File Type Validation

Validate file extensions and MIME types:

```python
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif"}

@app.post("/upload-image")
async def upload_image(request: Request, response: Response):
    files = await request.files
    if not files:
        return response.status(400).json({"error": "No file uploaded"})
    
    file = files["image"]
    
    # Validate extension
    file_ext = file.filename.split(".")[-1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return response.status(400).json({"error": "Invalid file type"})
    
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        return response.status(400).json({"error": "Invalid MIME type"})
    
    # Process valid file
    # ...
```

## 📋 Form Data with Files

Handle mixed form data and file uploads:

```python
@app.post("/profile")
async def update_profile(request: Request, response: Response):
    form_data = await request.form
    files = await request.files
    
    name = form_data.get("name")
    avatar = files.get("avatar")
    
    if avatar:
        avatar_content = await avatar.read()
        # Save avatar
        # ...
    
    return response.json({"name": name, "avatar_uploaded": bool(avatar)})
```

## ⚙️ Advanced Configuration

### Custom Upload Handlers

Create middleware for file upload processing:

```python
async def file_upload_middleware(request: Request, response: Response, call_next):
    if request.method == "POST" and "multipart/form-data" in request.headers.get("Content-Type", ""):
        # Pre-process uploads
        request.state.upload_dir = "/path/to/uploads"
    
    return await call_next(request, response)

app.add_middleware(file_upload_middleware)
```

### Streaming Large Files

For handling very large files without memory issues:

```python
@app.post("/upload-large")
async def upload_large_file(request: Request, response: Response):
    files = await request.files
    file = files.get("file")
    
    if not file:
        return response.status(400).json({"error": "No file uploaded"})
    
    # Process in chunks
    chunk_size = 1024 * 1024  # 1MB chunks
    total_size = 0
    
    async with open(f"/uploads/{file.filename}", "wb") as f:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            await f.write(chunk)
            total_size += len(chunk)
    
    return response.json({
        "filename": file.filename,
        "size": total_size,
        "status": "uploaded"
    })
```

## 🔧 Troubleshooting

Common issues and solutions:

1. **File size too large**:
   - Increase `max_file_size` in config
   - Use streaming for very large files

2. **Memory errors**:
   - Process files in chunks
   - Use `request.stream()` for direct access to the upload stream

3. **File validation failures**:
   - Always check both filename extension and MIME type
   - Consider scanning uploaded files for malware

## ✅ Best Practices

1. Always validate file types and sizes
2. Never trust original filenames - sanitize or generate new ones
3. Store files outside web root when possible
4. Set appropriate permissions on upload directories
5. Consider virus scanning for user uploads
6. Use CSRF protection for upload forms

This documentation covers the essential aspects of file upload handling in the Nexios framework. For more advanced scenarios, refer to the framework's multipart parsing and streaming capabilities.