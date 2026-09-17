from datetime import datetime

from sillo import HttpContext
from sillo.middleware import BaseMiddleware
from sillo.responses import json


class ComplexMiddleware(BaseMiddleware):
    async def dispatch(self, ctx: HttpContext, call_next):
        # Pre-processing: log request details
        print(f"Request received: {ctx.method} {ctx.url}")

        # Authentication check
        if not ctx.headers.get("Authorization"):
            return json({"error": "Unauthorized"}, status_code=401)

        # Store request time
        ctx.state.request_time = datetime.now()

        # Proceed to the rest of the chain
        response = await call_next()

        # Post-processing: add response headers
        elapsed = datetime.now() - ctx.state.request_time
        response.set_header("X-Processed-Time", str(elapsed))

        # Log response status
        print(f"Response sent with status: {response.status_code}")

        return response
