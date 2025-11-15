---
title: Pagination
description: Nexios provides a flexible and customizable pagination system that makes managing large datasets a breeze. With support for dynamic page sizes, custom query parameters, and seamless API integration, you can create efficient, user-friendly paginated experiences with minimal code.
head:
  - - meta
    - property: og:title
      content: Pagination
  - - meta
    - property: og:description
      content: Nexios provides a flexible and customizable pagination system that makes managing large datasets a breeze. With support for dynamic page sizes, custom query parameters, and seamless API integration, you can create efficient, user-friendly paginated experiences with minimal code.
---
## Simple Pagination

Here's a quick example of how to paginate a list of items using `response.paginate()`:

```python{6}
from nexios import NexiosApp
app = NexiosApp()
@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data)
```

you can also use async pagination

```python{6}
from nexios import NexiosApp
app = NexiosApp()
@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.apaginate(sample_data)
```

Output:

```py
{
  "items": [
    {
      "id": 1,
      "content": "Item 1"
    },
    {
      "id": 2,
      "content": "Item 2"
    },
    {
      "id": 3,
      "content": "Item 3"
    },
    {
      "id": 4,
      "content": "Item 4"
    },
    {
      "id": 5,
      "content": "Item 5"
    },
    {
      "id": 6,
      "content": "Item 6"
    },
    {
      "id": 7,
      "content": "Item 7"
    },
    {
      "id": 8,
      "content": "Item 8"
    },
    {
      "id": 9,
      "content": "Item 9"
    },
    {
      "id": 10,
      "content": "Item 10"
    },
    {
      "id": 11,
      "content": "Item 11"
    },
    {
      "id": 12,
      "content": "Item 12"
    },
    {
      "id": 13,
      "content": "Item 13"
    },
    {
      "id": 14,
      "content": "Item 14"
    },
    {
      "id": 15,
      "content": "Item 15"
    },
    {
      "id": 16,
      "content": "Item 16"
    },
    {
      "id": 17,
      "content": "Item 17"
    },
    {
      "id": 18,
      "content": "Item 18"
    },
    {
      "id": 19,
      "content": "Item 19"
    },
    {
      "id": 20,
      "content": "Item 20"
    }
  ],
  "pagination": {
    "total_items": 100,
    "total_pages": 5,
    "page": 1,
    "page_size": 20,
    "links": {
      "next": "http://127.0.0.1:8000/3?cursor=eyJpZCI6IDIwfQ%3D%3D&page_size=20?cursor=eyJpZCI6IDIwfQ%3D%3D&page=2&page_size=20",
      "first": "http://127.0.0.1:8000/3?cursor=eyJpZCI6IDIwfQ%3D%3D&page_size=20?cursor=eyJpZCI6IDIwfQ%3D%3D&page=1&page_size=20",
      "last": "http://127.0.0.1:8000/3?cursor=eyJpZCI6IDIwfQ%3D%3D&page_size=20?cursor=eyJpZCI6IDIwfQ%3D%3D&page=5&page_size=20"
    }
  }
}

```


## Pagination Strategies

You can also use other pagination strategies based on your requirements

```python{6}
from nexios import NexiosApp
app = NexiosApp()
@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data, strategy="cursor")

```

You can also pass the pagination class directly

```py
from nexios import NexiosApp
from nexios.pagination 
app = NexiosApp()
@app.get("/get-items")
async def get_items(request, response):
    sample_data = [{"id": i, "content": f"Item {i}"} for i in range(1, 101)]
    return response.paginate(sample_data, strategy="cursor")

```


### 1. Page Number Pagination
The most common pagination style, using page numbers and page sizes.

**Parameters:**
- `page_param`: Query parameter name for page number (default: "page")
- `page_size_param`: Query parameter name for page size (default: "page_size")
- `default_page`: Default page number (default: 1)
- `default_page_size`: Default page size (default: 20)
- `max_page_size`: Maximum allowed page size (default: 100)

**Example URL:** `/items?page=2&page_size=10`

### 2. Limit-Offset Pagination
Traditional SQL-style pagination using limit and offset.

**Parameters:**
- `limit_param`: Query parameter name for limit (default: "limit")
- `offset_param`: Query parameter name for offset (default: "offset")
- `default_limit`: Default limit value (default: 20)
- `max_limit`: Maximum allowed limit value (default: 100)

**Example URL:** `/items?limit=10&offset=20`

### 3. Cursor Pagination
Cursor-based pagination for consistent pagination with changing datasets.

**Parameters:**
- `cursor_param`: Query parameter name for cursor (default: "cursor")
- `page_size_param`: Query parameter name for page size (default: "page_size")
- `default_page_size`: Default page size (default: 20)
- `max_page_size`: Maximum allowed page size (default: 100)
- `sort_field`: Field to use for cursor sorting (default: "id")

**Example URL:** `/items?cursor=eyJpZCI6IDEwfQ%3D%3D&page_size=10`

## Data Handlers

Nexios provides both synchronous and asynchronous data handlers:
This is an abstract base class that defines the interface for fetching data. You must implement two methods:

Nexios Provide the following data handlers:
### SyncDataHandler
Base class for synchronous data handlers with two required methods:
- `get_total_items() -> int`: Returns total item count
- `get_items(offset: int, limit: int) -> List[Any]`: Returns paginated items

**Built-in Implementations:**
- `SyncListDataHandler`: Handles in-memory lists

### AsyncDataHandler
Base class for asynchronous data handlers with two required methods:
- `async get_total_items() -> int`: Returns total item count
- `async get_items(offset: int, limit: int) -> List[Any]`: Returns paginated items

**Built-in Implementations:**
- `AsyncListDataHandler`: Handles in-memory lists asynchronously


by default `.paginate()` uses the `AsyncListDataHandler` for async functions and `SyncListDataHandler` for sync functions.

## Custom Data Handler

You can also create your own data handler by subclassing the `SyncDataHandler` or `AsyncDataHandler` classes.

```python
from nexios.pagination import AsyncDataHandler
class DatabaseDataHandler(AsyncDataHandler):
    async def get_total_items(self) -> int:
        return await Model.count()
    async def get_items(self, offset: int, limit: int) -> List[Any]:
        return await self.data.offset(offset).limit(limit).all()

@app.get("/get-items")
async def get_items(request, response):
    return response.paginate(data = Items.all(), strategy="cursor", data_handler=DatabaseDataHandler)

``` 

In this example , we use `DatabaseDataHandler` to fetch data from a database using TortoiseORM.

## Custom Pagination Strategy

You can also create your own pagination strategy by subclassing the `BasePaginationStrategy` class.

```python
from nexios.pagination import PaginationStrategy
class CustomPaginationStrategy(BasePaginationStrategy):
    def calculate_offset_limit(self, page, page_size):
        return (page - 1) * page_size, page_size

@app.get("/get-items")
async def get_items(request, response):
    return response.paginate(data = [...], strategy=CustomPaginationStrategy)


```

You can override the following methods:
- `parse_parameters(request_params: Dict[str, Any]) -> Tuple[int, int]`
- `generate_metadata(total_items: int, items: List[Any], base_url: str, request_params: Dict[str, Any]) -> Dict[str, Any]`
- `calculate_offset_limit(self, page, page_size)`


## Manual Integration 

While Nexios provides a convenient way to use pagination, you can also manually integrate pagination into your app.

```python
from nexios import NexiosApp
fromnexios.pagination import SyncListDataHandler, PageNumberPagination, SyncPaginator
app = NexiosApp()

@app.get("/get-items")
async def get_items(request, response):

    data_handler = SyncListDataHandler(data=[...])
    pagination_strategy = PageNumberPagination(page_param="page", page_size_param="page_size", default_page=1, default_page_size=20, max_page_size=100)
    paginator = SyncPaginator(data_handler=data_handler, strategy=pagination_strategy)
    return paginator.paginate()
```

::: tip 💡Tip
Use this only if you know what you are doing.
::: 