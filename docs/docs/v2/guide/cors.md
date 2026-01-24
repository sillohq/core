---
title: Cors in Nexios
description: Learn how to use cors utilities in Nexios
head:
  - - meta
    - property: og:title
      content: Cors in Nexios
  - - meta
    - property: og:description
      content: Learn how to use cors utilities in Nexios
---
# cors

Got it! I'll go through each CORS configuration setting in **Nexios**, explaining what it does and how it impacts requests.

***

#### **Basic CORS Configuration in Nexios**

Before diving into individual settings, here's a simple CORS setup using `CorsConfig`:

```python
from nexios import NexiosApp, MakeConfig
from nexios.middleware.cors import CorsConfig
from nexios.middleware.cors import CORSMiddleware

config = MakeConfig(
    cors=CorsConfig(
        allow_origins=["https://example.com"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-Requested-With"],
        allow_credentials=True,
        max_age=600,
        debug=True
    )
)
app = NexiosApp(config=config)
app.add_middleware(CORSMiddleware())
```

we can break it down further:

***

### allow\_origins

* **Purpose:** Specifies which domains can access the API.
* **Example:**

    ```python
    # Using CorsConfig
    config = MakeConfig(
        cors=CorsConfig(
            allow_origins=["https://example.com", "https://another-site.com"]
        )
    )
    ```

* **Special cases:**
  * Use `["*"]` to allow requests from **any** origin (not safe if credentials are enabled).
  * If an origin is not listed here, the request will be blocked.

***

### blacklist\_origins

* **Purpose:** Specifies which origins should be **blocked**, even if they match `allow_origins`.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            blacklist_origins=["https://bad-actor.com"]
        )
    )
    ```

* **Use case:** If you allow all origins (`["*"]`), but want to exclude specific ones.

***

### allow\_methods

* **Purpose:** Defines which HTTP methods (GET, POST, etc.) are allowed in cross-origin requests.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            allow_methods=["GET", "POST", "PUT"]
        )
    )
    ```

* **Default:** All methods (`["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]`) are allowed.

***

### allow\_headers

* **Purpose:** Specifies which request headers are permitted in cross-origin requests.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            allow_headers=["Authorization", "X-Custom-Header"]
        )
    )
    ```

* **Default:** Basic headers like `Accept`, `Content-Type`, etc., are always allowed.

***

### blacklist\_headers

* **Purpose:** Defines headers that should **not** be allowed in requests.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            blacklist_headers=["X-Disallowed-Header"]
        )
    )
    ```

* **Use case:** If you allow most headers but want to restrict specific ones.

***

### allow\_credentials

* **Purpose:** Determines whether credentials (cookies, authorization headers) are allowed in requests.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            allow_credentials=True
        )
    )
    ```

* **Important:**
  * If `True`, the browser allows requests with credentials (e.g., session cookies).
  * If `True`, `allow_origins` **cannot** be `"*"` (security restriction).
  * If `False`, credentials are blocked.

***

### allow\_origin\_regex

* **Purpose:** Uses a regex pattern to match allowed origins dynamically.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            allow_origin_regex=r"https://.*\.trusted-site\.com"
        )
    )
    ```

* **Use case:** When you want to allow multiple subdomains without listing them individually.

***

### expose\_headers

* **Purpose:** Specifies which response headers the client is allowed to access.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            expose_headers=["X-Response-Time"]
        )
    )
    ```

* **Default:** Only basic headers are exposed unless configured.

***

### max\_age

* **Purpose:** Defines how long the preflight (OPTIONS) response can be cached.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            max_age=600  # Cache for 10 minutes
        )
    )
    ```

* **Impact:** Reduces unnecessary preflight requests for frequent API calls.

***

### strict\_origin\_checking

* **Purpose:** If enabled, requests **must** include an `Origin` header.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            strict_origin_checking=True
        )
    )
    ```

* **Use case:** When you want to strictly enforce CORS checks, especially for security.

***

### debug

* **Purpose:** Enables logging to troubleshoot CORS issues.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            debug=True
        )
    )
    ```

* **Impact:**
  * Prints logs when a request is blocked due to CORS.
  * Useful for debugging in development.

***

### custom\_error\_status \u0026 custom\_error\_messages

* **Purpose:** Allows custom error handling for CORS failures.
* **Example:**

    ```python
    config = MakeConfig(
        cors=CorsConfig(
            custom_error_status=403,
            custom_error_messages={
                "disallowed_origin": "This origin is not allowed.",
                "missing_origin": "The request is missing an origin."
            }
        )
    )
    ```

* **Use case:** When you want meaningful error messages instead of generic CORS errors.
