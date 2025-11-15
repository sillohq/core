---
title: Handling Request Inputs
description: In Nexios, processing inputs from HTTP requests is a fundamental aspect of building web applications. This document provides an overview of how to handle and process various types of inputs, such as JSON data, form data, files, and streaming request data.
head:
  - - meta
    - property: og:title
      content: Handling Request Inputs
  - - meta
    - property: og:description
      content: In Nexios, processing inputs from HTTP requests is a fundamental aspect of building web applications. This document provides an overview of how to handle and process various types of inputs, such as JSON data, form data, files, and streaming request data.
---
# 📨 Handling Request Inputs 

To handle JSON data in a request, you can use the `json` property of the `Request` object. This property asynchronously parses the request body as JSON and returns it as a dictionary.



```python
from nexios import NexiosApp

app = NexiosApp()

@app.post("/submit")
async def submit_data(req, res):
    data = await req.json
    return {"received": data}
```

::: tip 💡Tip
Nexios only process `application/json` content types for JSON data.
:::

## 📋 Form Data

Nexios provides built-in support for parsing form data, including `multipart/form-data` and `application/x-www-form-urlencoded`. You can access the parsed form data using the `form_data` property of the `Request` object.

**Example**

```python
@app.post("/submit-form")
async def submit_form(req, res):
    form_data = await req.form_data
    return {"received": form_data}
```



## 📁 Handling File Uploads

When handling file uploads, the `form_data` property also provides access to the uploaded files. You can iterate over the form data to extract files.


```python
@app.post("/upload")
async def upload_file(req, res):
    files = await req.files
    for name, file in files.items():
        # Process the uploaded file
        pass
    return {"status": "files received"}
```



## 🌊 Handling Streaming Request Data

For large payloads or real-time data, you might need to handle streaming request data. Nexios supports streaming data using the `req.stream` property.



```python
@app.post("/stream")
async def stream_data(req, res):
    data = b""
    async for chunk in req.stream():
        data += chunk
    print(data.decode())
    return {"status": "stream received"}
```

## ✅ Validating Inputs

Nexios integrates with Pydantic for input validation. You can define Pydantic models to validate and parse request data.

**Example**

```python
from pydantic import BaseModel, EmailStr, ValidationError

class UserSchema(BaseModel):
    name: str
    email: EmailStr

@app.post("/create-user")
async def create_user(req, res):
    try:
        user_data = await req.json
        user = UserSchema(**user_data)
        return res.json({"user": user.dict()})
    except ValidationError as e:
        return res.json({"error": e.errors()}, status_code=422)
```

