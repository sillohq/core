#  Quick Start

Get up and running with sillo in minutes ⏱️. This guide will walk you through creating your first sillo application.

##  Prerequisites

- Python 3.8+ 
- pip (Python package manager)

##  Installation

1. Create a new virtual environment (recommended) :
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. Install sillo :
   ```bash
   pip install sillo
   ```

##  Your First Application
A simple sillo one file application will look like this:

```python
from sillo import silloApp
from sillo.http import Response,Request

app = silloApp()

@app.get("/")
async def home(request:Request,response:Response):
    return response.json({"message": "Welcome to sillo!"})

if __name__ == "__main__":
    import uvicorn
       uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

2. Run your application ▶️:
   ```bash
   python main.py
   ```

3. Open your browser and visit `http://localhost:8000` 
   You should see: `{"message": "Welcome to sillo!"}`

##  Adding More Route

```python
from sillo import silloApp
from sillo.http import Response,Request

app = silloApp()

@app.get("/")
async def home(request:Request,response:Response):
    return response.json({"message": "Welcome to sillo!"})

@app.get("/hello/{name}")
async def greeting(request:Request,response:Response,name: str):
    return response.html(f"<h1>Hello, {name}!</h1>")

@app.post("/data")
async def create_data(request:Request,response:Response):
    data = await request.json
    return response.json({"received": data, "status": "success"})
```

##  Interactive API Documentation

sillo automatically generates interactive API documentation:
- Swagger UI: `http://localhost:8000/docs` 
- ReDoc: `http://localhost:8000/redoc` 

##  Next Steps

- [What is sillo?](../intro) - Learn more about sillo 
- [sillo and FastAPI](./sillo-and-fastapi) - Understand the relationship ⚖️
- [sillo and ASGI](./sillo-and-asgi) - Learn about the ASGI foundation 
- [Async Python](./sillo-and-async-python) - Master async/await in sillo 

##  Need Help?

- Check out the [GitHub repository](https://github.com/sillo-labs/sillo) 
- Join our [Discussions](https://github.com/orgs/sillo-labs/discussions) 
- Report issues on [GitHub Issues](https://github.com/sillo-labs/sillo/issues) 
