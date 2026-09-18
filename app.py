"""Example: CSRF-protected app, and a script that proves the fix.

Run the demo:

    python app.py

Or serve it for real and poke at it with curl:

    uvicorn app:app --reload
    curl -i http://127.0.0.1:8000/protected -X POST                 # 403, but now carries a Set-Cookie
    curl -i http://127.0.0.1:8000/protected -X POST -b cookies.txt \\
        -H "X-CSRFToken: <token from the cookie above>"              # 200

The demo below simulates the case that used to loop forever: a client
whose very first request is a POST with no CSRF cookie at all (an XHR
call before any page GET, or a CDN that dropped an earlier Set-Cookie).
Before the fix, the 403 response for that request carried no cookie
either, so every retry failed the exact same way. Now the rejection
itself hands back a fresh token.
"""

from __future__ import annotations

from sillo import SilloApp, json
from sillo.core.http import HttpContext
from sillo.security.csrf import CSRFConfig, CSRFMiddleware
from sillo.testclient import TestClient

app = SilloApp(title="csrf-example")
app.use(
    CSRFMiddleware(
        config=CSRFConfig(enabled=True, secret_key="replace-me-with-a-real-secret")
    )
)


@app.get("/token")
async def get_token(ctx: HttpContext):
    """Anything can read the current token off ctx.state -- no header dance."""
    return json({"csrf_token": ctx.state.csrf_token})


@app.post("/protected")
async def protected(ctx: HttpContext):
    return json({"status": "ok"})


def demo() -> None:
    with TestClient(app) as client:
        print("1. POST with no cookie at all (first-ever request, no prior GET):")
        first = client.post("/protected")
        print(f"   status={first.status_code}")
        cookie = client.cookies.get("csrftoken")
        print(f"   csrf cookie set on the 403? {'yes' if cookie else 'NO -- bug'}")
        assert cookie, "the rejection must still hand back a usable token"

        print("2. Retry immediately with that token:")
        second = client.post("/protected", headers={"X-CSRFToken": cookie})
        print(f"   status={second.status_code}")
        assert second.status_code == 200, "the token from the 403 must actually work"

    print("\nOK: a client that starts with no cookie can recover from the first 403.")


if __name__ == "__main__":
    demo()
