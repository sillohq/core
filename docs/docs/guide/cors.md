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
# 🌐 CORS in Nexios

Got it! I’ll go through each CORS configuration setting in **Nexios**, explaining what it does and how it impacts requests.

***

### 🚀 Basic CORS Configuration in Nexios

Before diving into individual settings, here’s a simple CORS setup using `MakeConfig`:

```python
from nexios import MakeConfig
from nexios.middleware.cors import CORSMiddleware
config = MakeConfig({
    "cors": {
        "allow_origins": ["https://example.com"],
    "allow_methods": ["GET", "POST"],
    "allow_headers": ["Authorization", "X-Requested-With"],
    "allow_credentials": True,
    "max_age": 600,
    "debug": True
    }
})
app = NexiosApp(config = config)

```

we can break it down further:

***

### 🔓 allow_origins

* **Purpose:** Specifies which domains can access the API.
*   **Example:**

    ```python
    config.cors["allow_origins"] = ["https://example.com", "https://another-site.com"]
    ```
* **Special cases:**
  * Use `["*"]` to allow requests from **any** origin (not safe if credentials are enabled).
  * If an origin is not listed here, the request will be blocked.

***

### 🚫 blacklist_origins

* **Purpose:** Specifies which origins should be **blocked**, even if they match `allow_origins`.
*   **Example:**

    ```python
    config.cors["blacklist_origins"] = ["https://bad-actor.com"]
    ```
* **Use case:** If you allow all origins (`["*"]`), but want to exclude specific ones.

***

### 🔧 allow_methods

* **Purpose:** Defines which HTTP methods (GET, POST, etc.) are allowed in cross-origin requests.
*   **Example:**

    ```python
    config.cors["allow_methods"] = ["GET", "POST", "PUT"]
    ```
* **Default:** All methods (`["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]`) are allowed.

***

### 📝 allow_headers

* **Purpose:** Specifies which request headers are permitted in cross-origin requests.
*   **Example:**

    ```python
    config.cors["allow_headers"] = ["Authorization", "X-Custom-Header"]
    ```
* **Default:** Basic headers like `Accept`, `Content-Type`, etc., are always allowed.

***

### 🚫 blacklist_headers

* **Purpose:** Defines headers that should **not** be allowed in requests.
*   **Example:**

    ```python
    config.cors["blacklist_headers"] = ["X-Disallowed-Header"]
    ```
* **Use case:** If you allow most headers but want to restrict specific ones.

***

### 🔑 allow_credentials

* **Purpose:** Determines whether credentials (cookies, authorization headers) are allowed in requests.
*   **Example:**

    ```python
    config.cors["allow_credentials"] = True
    ```
* **Important:**
  * If `True`, the browser allows requests with credentials (e.g., session cookies).
  * If `True`, `allow_origins` **cannot** be `"*"` (security restriction).
  * If `False`, credentials are blocked.

***

### 🎯 allow_origin_regex

* **Purpose:** Uses a regex pattern to match allowed origins dynamically.
*   **Example:**

    ```python
    config.cors["allow_origin_regex"] = r"https://.*\.trusted-site\.com"
    ```
* **Use case:** When you want to allow multiple subdomains without listing them individually.

***

### 👁️ expose_headers

* **Purpose:** Specifies which response headers the client is allowed to access.
*   **Example:**

    ```python
    config.cors["expose_headers"] = ["X-Response-Time"]
    ```
* **Default:** Only basic headers are exposed unless configured.

***

### ⏱️ max_age

* **Purpose:** Defines how long the preflight (OPTIONS) response can be cached.
*   **Example:**

    ```python
    config.cors["max_age"] = 600  # Cache for 10 minutes
    ```
* **Impact:** Reduces unnecessary preflight requests for frequent API calls.

***

### 🔍 strict_origin_checking

* **Purpose:** If enabled, requests **must** include an `Origin` header.
*   **Example:**

    ```python
    config.cors["strict_origin_checking"] = True
    ```
* **Use case:** When you want to strictly enforce CORS checks, especially for security.

***

### 🐛 debug

* **Purpose:** Enables logging to troubleshoot CORS issues.
*   **Example:**

    ```python
    config.cors["debug"] = True
    ```
* **Impact:**
  * Prints logs when a request is blocked due to CORS.
  * Useful for debugging in development.

***

### ❌ custom_error_status & custom_error_messages

* **Purpose:** Allows custom error handling for CORS failures.
*   **Example:**

    ```python
    config.cors["custom_error_status"] = 403
    config.cors["custom_error_messages"] = {
        "disallowed_origin": "This origin is not allowed.",
        "missing_origin": "The request is missing an origin."
    }
    ```
* **Use case:** When you want meaningful error messages instead of generic CORS errors.
