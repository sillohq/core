from datetime import datetime

from nexios.http import Request, Response
from nexios.middleware.base import BaseMiddleware


class ComplexMiddleware(BaseMiddleware):
    async def process_request(self, req: Request, res: Response, cnext):
        # Pre-processing: Log request details
        print(f"Request received: {req.method} {req.url}")

        # Authentication check
        if not req.headers.get("Authorization"):
            return res.json({"error": "Unauthorized"}, status_code=401)

        # Store request time
        req.state.request_time = datetime.now()

        # Proceed to next middleware or handler
        await cnext(req, res)

    async def process_response(self, req: Request, res: Response):
        # Post-processing: Add response headers
        res.headers["X-Processed-Time"] = str(datetime.now() - req.state.request_time)

        # Log response status
        print(f"Response sent with status: {res.status_code}")

        return res  # Return the modified response
