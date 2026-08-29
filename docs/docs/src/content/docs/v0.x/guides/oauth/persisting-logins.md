---
title: Persisting the Login
description: What to do with a verified OAuthProfile (a session cookie, a JWT, a linked account, or nothing at all) and how to protect the routes behind it with useAuth.
head:
- tag: meta
  attrs:
    property: og:title
    content: Persisting an OAuth login in sillo
- tag: meta
  attrs:
    property: og:description
    content: sillo-oauth returns a verified identity and stops. Session, JWT, account linking or nothing is your handler's decision.
---

#  Persisting the Login

`exchange` returns a verified external identity and stops there. Turning that
into a logged-in user is your application's decision, so there is no
`on_success` hook and no user model to configure, only the few lines you write
after the call.

Every recipe below is the same flow with a different ending.

##  Session cookie

The common case for a server-rendered or Inertia application.

```python
from sillo.auth.session_auth import login

@app.get("/auth/google/callback", exclude_from_schema=True)
async def finish(request, response):
    profile = await exchange(google, request)
    user = await User.objects.get_or_create_from_oauth("google", profile)
    login(request, user)
    return response.redirect(profile.return_to or "/dashboard")
```

Protect what follows with the cookie scheme:

```python
@app.get("/dashboard", auth=useAuth(schemes=["sessionCookie"]))
async def dashboard(request, response):
    return response.json({"user": request.user.display_name})
```

This needs `SessionMiddleware` installed and `SessionAuthBackend` declared. See
[wiring](#wiring) below.

##  JWT, for an SPA or mobile client

No session anywhere. The callback mints a token and hands it over.

```python
from sillo.auth.jwt_auth import create_jwt

@app.get("/auth/google/callback", exclude_from_schema=True)
async def finish(request, response):
    profile = await exchange(google, request)
    user = await User.objects.get_or_create_from_oauth("google", profile)
    token = create_jwt({"id": str(user.id)}, settings.jwt_secret)
    return response.json({"access_token": token})
```

For a native app, redirect to a custom scheme instead so the OS hands the
token back to the application:

```python
    return response.redirect(f"myapp://oauth-complete?token={token}")
```

Then gate on the bearer scheme:

```python
@app.get("/api/me", auth=useAuth(schemes=["bearerAuth"]))
async def me(request, response):
    return response.json({"identity": request.user.identity})
```

##  Account linking

Connecting a second provider to someone who is already signed in. The
difference is that you do *not* look up a user by the profile. You attach it to
the one already on the request. (`OAuthIdentity` here is a model you define;
see [resolving a profile](#resolving-a-profile-onto-a-user).)

```python
@app.get("/settings/connect/github", exclude_from_schema=True)
async def start(request, response):
    authorize = authorize_url(github)
    return response.redirect(authorize.url).set_cookie(**authorize.cookie_kwargs())


@app.get("/settings/connect/github/callback", exclude_from_schema=True)
async def finish(request, response):
    profile = await exchange(github, request)
    if not request.user.is_authenticated:
        return response.redirect("/login")
    await OAuthIdentity.objects.link(request.user, "github", profile.subject)
    return response.redirect("/settings?connected=github")
```

Because each provider gets its own state cookie (`oauth_state_github`,
`oauth_state_google`), a linking flow started in one tab cannot clobber a login
started in another.

##  No persistence at all

Sometimes OAuth is identity verification, not login:

```python
@app.get("/verify/google/callback", exclude_from_schema=True)
async def verify(request, response):
    profile = await exchange(google, request)
    return response.json({
        "email": profile.email,
        "verified": profile.email_verified,
    })
```

No session middleware, no user model, no auth backend required.

##  Resolving a profile onto a user

`sillo-oauth` ships no user model and no link table. `User` and `OAuthIdentity`
below are **your** models, and this is a sketch to adapt, not an API to call.
It is the one piece worth thinking about rather than copying.

```python
async def get_or_create_from_oauth(provider: str, profile: OAuthProfile) -> User:
    identity = await OAuthIdentity.filter(
        provider=provider, subject=profile.subject
    ).first()
    if identity:
        return await identity.user

    # Only ever match an existing account on a verified address.
    user = None
    if profile.email and profile.email_verified:
        user = await User.objects.get_by_email(profile.email)

    if user is None:
        user = await User.objects.create_user(
            email=profile.email,
            username=profile.username or profile.key,
        )

    await OAuthIdentity.create(provider=provider, subject=profile.subject, user=user)
    return user
```

:::danger
**Never match an existing account on an unverified email.** If a provider will
issue a profile for `admin@yourcompany.com` without proving control of it,
matching on that address hands over the account. `profile.email_verified` is
`False` both when the provider says "no" and when it says nothing, so the check
above is the safe one either way.

Creating users with `create_user` and no password leaves the password unusable,
which is what you want: the account exists but cannot be signed into with a
password nobody set.
:::

##  Wiring

Declare your backends on the application rather than installing the middleware
by hand. This is what makes the OpenAPI document describe the credential you
actually check. See [OAuth in OpenAPI](/v0.x/guides/oauth/openapi/).

```python
from sillo import SilloApp
from sillo.auth.jwt_auth import JWTAuthBackend
from sillo.auth.session_auth import SessionAuthBackend
from sillo.session import SessionMiddleware

app = SilloApp(
    title="My API",
    auth=[
        JWTAuthBackend(
            secret_key=settings.jwt_secret,
            description="Issued by /auth/google/callback.",
        ),
        SessionAuthBackend(description="Set by /auth/google/callback."),
    ],
    auth_user_model=User,
    strict_security=True,
)
app.use(SessionMiddleware(secret_key=settings.secret_key))
```

`SilloApp(auth=[...])` installs `AuthenticationMiddleware` for you, in the
right place. If you install it yourself instead, register it *before*
`SessionMiddleware`: `app.use` builds the chain inside-out, so the last
registered runs first, and a session backend that runs before the session
middleware finds no session and reports every request as anonymous.

##  Protecting what comes after

Nothing in route protection is OAuth-specific: once the login has been
persisted, the credential is an ordinary session cookie or JWT, and
[`useAuth`](/v0.x/guides/protecting-routes/) gates on it.

```python
@app.get("/me", auth=useAuth())                                     # any credential
@app.get("/dash", auth=useAuth(schemes=["sessionCookie"]))          # browser only
@app.get("/api/me", auth=useAuth(schemes=["bearerAuth"]))           # token only
@app.get("/admin", auth=useAuth(permissions=["admin"]))             # 401 anon, 403 no perm
@app.get("/feed", auth=useAuth(required=False))                     # optional
```

**Leave the OAuth routes themselves ungated.** An anonymous browser has to
reach both of them, and a gate on the callback turns every login into a 401.
