---
title: OAuth2 Overview
description: "Sign in with Google, GitHub, Discord or Microsoft using sillo-oauth: two plain functions that return a URL and a verified profile, with no router, no middleware and no opinion about how you store the login."
head:
- tag: meta
  attrs:
    property: og:title
    content: OAuth2 and OpenID Connect in sillo
- tag: meta
  attrs:
    property: og:description
    content: "sillo-oauth is two functions: authorize_url returns a URL, exchange returns a verified profile. Everything else stays in your handlers."
---

#  OAuth2 Overview

`sillo-oauth` adds "Sign in with Google" (and GitHub, Discord, Microsoft, or
anything else speaking OAuth 2.0) to a sillo application.

It is a separate package, and a deliberately small one. There is no router to
mount, no middleware to install, and no configuration object that owns your
login flow. There are two functions:

| | |
| --- | --- |
| `authorize_url(provider)` | Returns the URL to send someone to, plus the state you need to store. Pure: no request, no I/O. |
| `await exchange(provider, request)` | Reads the callback request and returns a verified `OAuthProfile`. |

Neither takes a response, builds one, or registers a route. That is the whole
design: the package handles the parts of OAuth that are fiddly and
security-sensitive, and hands you a verified identity. What that identity
*means* (a new user, a session, a JWT, a linked account, or nothing) stays in
your handler.

##  Installation

```bash
pip install sillo-oauth
```

It needs no ORM extra of its own. If you resolve profiles onto database-backed
users you will already have `sillo-framework[record]` installed for that.

##  A complete login

```python
from sillo import SilloApp
from sillo.auth.session_auth import login
from sillo_oauth import GoogleOAuthProvider, OAuthError, authorize_url, exchange

google = GoogleOAuthProvider(
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    state_secret=settings.secret_key,
    redirect_uri="https://example.com/auth/google/callback",
)


@app.get("/auth/google/redirect", exclude_from_schema=True)
async def start(request, response):
    authorize = authorize_url(google, return_to=request.query_params.get("next"))
    return response.redirect(authorize.url).set_cookie(**authorize.cookie_kwargs())


@app.get("/auth/google/callback", exclude_from_schema=True)
async def finish(request, response):
    try:
        profile = await exchange(google, request)
    except OAuthError as exc:
        return response.redirect(f"/login?error={exc.code}")

    user = await User.objects.get_or_create_from_oauth("google", profile)
    login(request, user)
    return response.redirect(profile.return_to or "/")
```

That is the entire integration. Two routes you wrote, at paths you chose,
returning responses you built.

:::caution
**Set the cookie *after* the redirect.** `response.redirect(...).set_cookie(...)`
works; `response.set_cookie(...)` followed by `return response.redirect(...)`
raises `AttributeError`, because sillo's `Responder` has no response to attach
a cookie to until `redirect()` or `json()` has been called.
:::

##  What happens, in order

1. Someone hits `/auth/google/redirect`. `authorize_url` mints a random state,
   signs it, and builds the provider URL, including a PKCE challenge.
2. You set the state cookie and redirect. The browser goes to Google.
3. Google sends the browser back to `/auth/google/callback?code=...&state=...`.
4. `exchange` verifies the returned `state` against the signed cookie, refuses
   anything that does not match, then trades the code for tokens and fetches
   the profile.
5. You get an `OAuthProfile` and decide what it means.

Nothing is stored server-side at any point. See
[The security model](/guides/oauth/security/) for why, and what that buys.

##  The profile

```python
profile.provider        # "google"
profile.subject         # the provider's stable id for this account
profile.key             # "google:112233" — unique across providers
profile.email
profile.email_verified  # False also means "the provider did not say"
profile.name
profile.username
profile.avatar_url
profile.raw             # the untouched userinfo payload
profile.tokens          # access/refresh tokens, for calling the provider later
profile.return_to       # whatever you passed to authorize_url(return_to=...)
```

Key local accounts on `subject`, never on `email`. Addresses get reassigned
between people, and an address the provider has not verified is an
account-takeover vector. `email_verified` is `False` both when the provider
says "no" and when it says nothing at all.

##  Errors

Every failure raises a subclass of `OAuthError` carrying a stable, URL-safe
`.code`, so one `except` is enough and the code can go straight into a
redirect.

| `.code` | Raised when |
| --- | --- |
| `denied` | The person declined consent. Not a fault: send them back to the login page. |
| `provider_error` | The provider reported some other `error` parameter. |
| `state_mismatch` | The callback does not match a redirect this server issued: no cookie, no `state`, a forged or tampered cookie, or one minted for another provider. |
| `state_expired` | Genuine state, but older than the TTL. Worth a "that took too long, try again". |
| `exchange_failed` | The provider would not trade the code for a token. |
| `profile_failed` | A token was issued but no usable profile came back. |
| `provider_misconfigured` | A programming error: a missing secret, redirect URI, or endpoint. |

##  Local development

A live OAuth redirect URI is HTTPS, so `cookie_kwargs()` sets `secure=True`.
Over plain `http://localhost` the browser will accept that cookie and then
never send it back, and every callback fails as `state_mismatch` with nothing
obviously wrong at the redirect step. In local development:

```python
response.redirect(authorize.url).set_cookie(**authorize.cookie_kwargs(secure=False))
```

##  Where next

- [Providers](/guides/oauth/providers/): the four shipped, and how to add any
  other.
- [Persisting the login](/guides/oauth/persisting-logins/): session, JWT,
  account linking, or nothing.
- [OAuth in OpenAPI](/guides/oauth/openapi/): what your API reference should
  say about all this.
- [The security model](/guides/oauth/security/): state, PKCE, and what is
  deliberately not stored.
