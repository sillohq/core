# Getting Started Examples

These examples will help you get up and running with Nexios quickly.

## Examples

| File | Description |
|------|-------------|
| [01_hello_world.py](./01_hello_world.py) | Basic "Hello World" application |
| [02_basic_rest.py](./02_basic_rest.py) | Simple REST API with CRUD operations |
| [03_enhanced_api.py](./03_enhanced_api.py) | Full-featured API with docs, WebSockets, DI |
| [04_lifespan.py](./04_lifespan.py) | Application lifespan management |
| [05_streaming_middleware.py](./05_streaming_middleware.py) | Request streaming and middleware |

## Running

```bash
# Run individual example
python 01_hello_world.py

# Or with uvicorn
uvicorn 01_hello_world:app --reload --port 8000
```

## What's Next?

After these basics, explore:
- [](../routing/) - Learn about routing patterns
- [](../middleware/) - Add middleware to your app
- [](../auth/) - Add authentication
- [](../database/) - Connect to databases