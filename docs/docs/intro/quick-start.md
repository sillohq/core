# 🚀 Quick Start

Get up and running with Nexios in minutes ⏱️. This guide will walk you through creating your first Nexios application.

## 📋 Prerequisites

- Python 3.8+ 🐍
- pip (Python package manager)

## 📦 Installation

1. Create a new virtual environment (recommended) 🏠:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install Nexios 📥:
   ```bash
   pip install nexios
   ```

## 🎯 Your First Application
A simple Nexios one file application will look like this:

```python
from nexios import Nexios
from nexios.http import Response,Request

app = Nexios()

@app.get("/")
async def home(request:Request,response:Response):
    return response.json({"message": "Welcome to Nexios!"})

if __name__ == "__main__":
    import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

2. Run your application ▶️:
   ```bash
   python main.py
   ```

3. Open your browser and visit `http://localhost:8000` 🌐
   You should see: `{"message": "Welcome to Nexios!"}`

## 🛣️ Adding More Route

```python
from nexios import Nexios
from nexios.http import Response,Request

app = Nexios()

@app.get("/")
async def home(request:Request,response:Response):
    return response.json({"message": "Welcome to Nexios!"})

@app.get("/hello/{name}")
async def greeting(request:Request,response:Response,name: str):
    return response.html(f"<h1>Hello, {name}!</h1>")

@app.post("/data")
async def create_data(request:Request,response:Response):
    data = await request.json
    return response.json({"received": data, "status": "success"})
```

## 📖 Interactive API Documentation

Nexios automatically generates interactive API documentation:
- Swagger UI: `http://localhost:8000/docs` 📋
- ReDoc: `http://localhost:8000/redoc` 📄

## 👣 Next Steps

- [What is Nexios?](../intro) - Learn more about Nexios 🤔
- [Nexios and FastAPI](./nexios-and-fastapi) - Understand the relationship ⚖️
- [Nexios and ASGI](./nexios-and-asgi) - Learn about the ASGI foundation 🌐
- [Async Python](./nexios-and-async-python) - Master async/await in Nexios 🔄

## 🆘 Need Help?

- Check out the [GitHub repository](https://github.com/nexios-labs/nexios) 🔗
- Join our [Discussions](https://github.com/orgs/nexios-labs/discussions) 💬
- Report issues on [GitHub Issues](https://github.com/nexios-labs/nexios/issues) 🚨
