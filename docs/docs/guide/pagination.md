---
title: Pagination
description: Comprehensive guide to Nexios pagination system with flexible strategies, custom data handlers, and seamless API integration for managing large datasets efficiently.
head:
  - - meta
    - property: og:title
      content: Pagination
  - - meta
    - property: og:description
      content: Comprehensive guide to Nexios pagination system with flexible strategies, custom data handlers, and seamless API integration for managing large datasets efficiently.
---
# 📄 Pagination

Nexios provides a powerful, flexible pagination system that supports multiple strategies, custom data handlers, and seamless integration with your existing APIs. Whether you're building simple list pagination or complex cursor-based navigation, Nexios has you covered.

## 🚀 Quick Start

Here's a quick example of how to paginate a list of items using `response.paginate()`:

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data)
```

For async endpoints, use `response.apaginate()`:

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.apaginate(sample_data)
```

## 📊 Response Format

The pagination response includes both the data and comprehensive metadata:

```json
{
  "items": [
    {"id": 1, "content": "Item 1"},
    {"id": 2, "content": "Item 2"},
    "...more items..."
  ],
  "pagination": {
    "total_items": 100,
    "total_pages": 5,
    "page": 1,
    "page_size": 20,
    "links": {
      "next": "http://127.0.0.1:8000/items?page=2&page_size=20",
      "first": "http://127.0.0.1:8000/items?page=1&page_size=20",
      "last": "http://127.0.0.1:8000/items?page=5&page_size=20"
    }
  }
}
```

::: tip 💡 **Navigation Links**
The `links` section provides ready-to-use URLs for navigating between pages. The `prev` link appears only when not on the first page.
:::

## 🗂️ Pagination Strategies

Nexios supports three main pagination strategies, each suited for different use cases:

### 1. Page Number Pagination (Default)

The most common pagination style, using page numbers and page sizes. Perfect for traditional web applications.

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data, strategy="page_number")
```

**Parameters:**
- `page_param`: Query parameter name for page number (default: "page")
- `page_size_param`: Query parameter name for page size (default: "page_size")
- `default_page`: Default page number (default: 1)
- `default_page_size`: Default page size (default: 20)
- `max_page_size`: Maximum allowed page size (default: 100)

**Example URLs:**
- `/items?page=2&page_size=10` - Page 2 with 10 items per page
- `/items?page_size=50` - First page with 50 items per page
- `/items` - Uses defaults (page 1, 20 items per page)

### 2. Limit-Offset Pagination

Traditional SQL-style pagination using limit and offset. Ideal for database queries and APIs that follow REST conventions.

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data, strategy="limit_offset")
```

**Parameters:**
- `limit_param`: Query parameter name for limit (default: "limit")
- `offset_param`: Query parameter name for offset (default: "offset")
- `default_limit`: Default limit value (default: 20)
- `max_limit`: Maximum allowed limit value (default: 100)

**Example URLs:**
- `/items?limit=10&offset=20` - Items 21-30
- `/items?limit=50` - First 50 items
- `/items?offset=100` - Items starting from 101 (uses default limit)

### 3. Cursor Pagination

Cursor-based pagination for consistent pagination with changing datasets. Perfect for real-time feeds, infinite scroll, and large datasets.

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data, strategy="cursor")
```

**Parameters:**
- `cursor_param`: Query parameter name for cursor (default: "cursor")
- `page_size_param`: Query parameter name for page size (default: "page_size")
- `default_page_size`: Default page size (default: 20)
- `max_page_size`: Maximum allowed page size (default: 100)
- `sort_field`: Field to use for cursor sorting (default: "id")

**Example URLs:**
- `/items?cursor=eyJpZCI6IDEwfQ%3D%3D&page_size=10` - Items after ID 10
- `/items?page_size=50` - First 50 items
- `/items` - Uses defaults (first page, 20 items per page)

::: tip 💡 **Cursor Encoding**
Cursors are base64-encoded JSON objects containing the sort field value. This makes them URL-safe and opaque to clients.
:::

## 🔧 Advanced Configuration

### Custom Strategy Parameters

You can customize pagination strategies by passing strategy instances instead of strings:

```python{6}
from nexios import NexiosApp
from nexios.pagination import PageNumberPagination, CursorPagination

app = NexiosApp()

# Custom page number pagination
@app.get("/items-page")
async def get_items_page(request, response):
    data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
    strategy = PageNumberPagination(
        page_param="p",
        page_size_param="size",
        default_page=1,
        default_page_size=10,
        max_page_size=50
    )
    return response.paginate(data, strategy=strategy)

# Custom cursor pagination with timestamp sorting
@app.get("/items-cursor")
async def get_items_cursor(request, response):
    data = [
        {"id": i, "name": f"Item {i}", "created_at": f"2023-01-{i:02d}T00:00:00Z"}
        for i in range(1, 31)
    ]
    strategy = CursorPagination(
        sort_field="created_at",
        default_page_size=5
    )
    return response.paginate(data, strategy=strategy)
```

### Error Handling

Nexios provides built-in error handling for invalid pagination parameters:

```python{6}
from nexios import NexiosApp
from nexios.pagination import InvalidPageError, InvalidPageSizeError, InvalidCursorError
from nexios.http import HTTPException

app = NexiosApp()

@app.get("/items")
async def get_items(request, response):
    try:
        data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
        return response.paginate(data)
    except InvalidPageError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidPageSizeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InvalidCursorError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Common Errors:**
- `InvalidPageError`: Page number < 1 or offset < 0
- `InvalidPageSizeError`: Page size < 1 or limit < 0
- `InvalidCursorError`: Malformed cursor encoding

### Filtering and Sorting

Pagination works seamlessly with filtering and sorting:

```python{6}
from nexios import NexiosApp

app = NexiosApp()

@app.get("/products")
async def get_products(request, response):
    # Sample data with categories
    all_products = [
        {"id": i, "name": f"Product {i}", "category": "electronics" if i % 2 == 0 else "books", "price": i * 10}
        for i in range(1, 101)
    ]
    
    # Apply filters
    category = request.query_params.get("category")
    min_price = request.query_params.get("min_price")
    
    filtered_products = all_products
    if category:
        filtered_products = [p for p in filtered_products if p["category"] == category]
    if min_price:
        filtered_products = [p for p in filtered_products if p["price"] >= float(min_price)]
    
    # Sort results
    sort_by = request.query_params.get("sort", "id")
    reverse = request.query_params.get("order") == "desc"
    filtered_products.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)
    
    return response.paginate(filtered_products)
```

**Example URLs:**
- `/products?category=electronics&sort=price&order=desc`
- `/products?min_price=50&page=2&page_size=20`
- `/products?category=books&sort=name`

::: tip 💡 **Preserving Query Parameters**
Pagination links automatically preserve non-pagination query parameters, so filters and sorting persist across page navigation.
:::

## 🔄 Data Handlers

Data handlers abstract the data source, allowing pagination to work with any type of data storage. Nexios provides built-in handlers for in-memory lists and async operations.

### Built-in Data Handlers

#### SyncDataHandler
Base class for synchronous data handlers with two required methods:
- `get_total_items() -> int`: Returns total item count
- `get_items(offset: int, limit: int) -> List[Any]`: Returns paginated items

**Built-in Implementation:**
- `SyncListDataHandler`: Handles in-memory lists

#### AsyncDataHandler  
Base class for asynchronous data handlers with two required methods:
- `async get_total_items() -> int`: Returns total item count
- `async get_items(offset: int, limit: int) -> List[Any]`: Returns paginated items

**Built-in Implementation:**
- `AsyncListDataHandler`: Handles in-memory lists asynchronously

::: info 💡 **Automatic Selection**
By default, `.paginate()` uses `AsyncListDataHandler` for async functions and `SyncListDataHandler` for sync functions.
:::

## 🏗️ Custom Data Handlers

Create custom data handlers to integrate with databases, external APIs, or any data source:

### Database Integration Examples


#### Tortoise ORM Example
```python{6}
from nexios import NexiosApp
from nexios.pagination import AsyncDataHandler
from tortoise.models import Model
from .models import Item

app = NexiosApp()

class TortoiseDataHandler(AsyncDataHandler):
    def __init__(self, query):
        self.query = query
    
    async def get_total_items(self) -> int:
        return await self.query.count()
    
    async def get_items(self, offset: int, limit: int) -> List[Any]:
        return await self.query.offset(offset).limit(limit).all()

@app.get("/items")
async def get_items(request, response):
    # Apply filters from query parameters
    query = Item.all()
    return response.paginate(query, data_handler=TortoiseDataHandler(query))
```


## ⚙️ Custom Pagination Strategies

Create custom pagination strategies by subclassing `BasePaginationStrategy`:

### Custom Strategy Example
```python{6}
from nexios import NexiosApp
from nexios.pagination import BasePaginationStrategy
from typing import Any, Dict, Tuple

app = NexiosApp()

class SeekPagination(BasePaginationStrategy):
    """Custom seek-based pagination similar to Facebook's API"""
    def __init__(self, seek_param: str = "seek", page_size_param: str = "limit", default_page_size: int = 20):
        self.seek_param = seek_param
        self.page_size_param = page_size_param
        self.default_page_size = default_page_size
    
    def parse_parameters(self, request_params: Dict[str, Any]) -> Tuple[Optional[str], int]:
        seek_value = request_params.get(self.seek_param)
        page_size = int(request_params.get(self.page_size_param, self.default_page_size))
        return seek_value, page_size
    
    def calculate_offset_limit(self, seek_value: Optional[str], page_size: int) -> Tuple[int, int]:
        # For seek pagination, we'd typically use this in the database query
        # Here we simulate with offset calculation
        if seek_value:
            # In real implementation, you'd find the position of seek_value
            return int(seek_value), page_size
        return 0, page_size
    
    def generate_metadata(self, total_items: int, items: List[Any], 
                        base_url: str, request_params: Dict[str, Any]) -> Dict[str, Any]:
        seek_value, page_size = self.parse_parameters(request_params)
        
        # Generate next seek value
        next_seek = str(int(seek_value or 0) + len(items)) if items else None
        
        links = {}
        if next_seek and len(items) == page_size:
            links["next"] = f"{base_url}?{self.seek_param}={next_seek}&{self.page_size_param}={page_size}"
        
        return {
            "total_items": total_items,
            "page_size": page_size,
            "seek_value": seek_value,
            "has_more": len(items) == page_size,
            "links": links
        }

@app.get("/items-seek")
async def get_items_seek(request, response):
    data = [{"id": i, "name": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(data, strategy=SeekPagination())
```

### Overridable Methods

When creating custom strategies, you can override these methods:

- `parse_parameters(request_params: Dict[str, Any]) -> Any`: Extract pagination parameters from request
- `calculate_offset_limit(*args) -> Tuple[int, int]`: Convert parameters to offset/limit
- `generate_metadata(total_items, items, base_url, request_params) -> Dict[str, Any]`: Create pagination metadata

### Advanced Custom Strategy
```python{6}
from nexios.pagination import BasePaginationStrategy, LinkBuilder
from typing import Any, Dict, Tuple
import math

class HybridPagination(BasePaginationStrategy):
    """Hybrid strategy that supports both page and cursor-based pagination"""
    def __init__(self, page_param: str = "page", cursor_param: str = "cursor", 
                 page_size_param: str = "page_size", default_page_size: int = 20):
        self.page_param = page_param
        self.cursor_param = cursor_param
        self.page_size_param = page_size_param
        self.default_page_size = default_page_size
    
    def parse_parameters(self, request_params: Dict[str, Any]) -> Dict[str, Any]:
        page = request_params.get(self.page_param)
        cursor = request_params.get(self.cursor_param)
        page_size = int(request_params.get(self.page_size_param, self.default_page_size))
        
        return {
            "page": int(page) if page else None,
            "cursor": cursor,
            "page_size": page_size,
            "is_cursor_based": cursor is not None
        }
    
    def calculate_offset_limit(self, params: Dict[str, Any]) -> Tuple[int, int]:
        if params["is_cursor_based"]:
            # Cursor-based logic (simplified)
            return int(params["cursor"] or 0), params["page_size"]
        else:
            # Page-based logic
            page = params["page"] or 1
            return (page - 1) * params["page_size"], params["page_size"]
    
    def generate_metadata(self, total_items: int, items: List[Any], 
                        base_url: str, request_params: Dict[str, Any]) -> Dict[str, Any]:
        params = self.parse_parameters(request_params)
        
        metadata = {
            "total_items": total_items,
            "page_size": params["page_size"],
            "strategy": "cursor" if params["is_cursor_based"] else "page"
        }
        
        if params["is_cursor_based"]:
            # Cursor metadata
            next_cursor = str(int(params["cursor"] or 0) + len(items)) if items else None
            metadata.update({
                "cursor": params["cursor"],
                "next_cursor": next_cursor,
                "has_more": len(items) == params["page_size"]
            })
        else:
            # Page metadata
            page = params["page"] or 1
            total_pages = math.ceil(total_items / params["page_size"]) if params["page_size"] else 1
            metadata.update({
                "page": page,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            })
        
        return metadata
```