---
title: OAuth Providers
description: The four providers sillo-oauth ships with, how to point them at self-hosted installations, and how to configure any other OAuth 2.0 provider with OAuthProvider.
head:
- tag: meta
  attrs:
    property: og:title
    content: OAuth Providers in sillo
- tag: meta
  attrs:
    property: og:description
    content: Google, GitHub, Discord and Microsoft ship configured. Everything else is one OAuthProvider call.
---

#  OAuth Providers

A provider is inert configuration: endpoints, credentials, scopes, and how to
read a profile out of the response. It registers nothing and holds no
per-request state, so build one at startup and reuse it for every request.

##  The shipped providers

```python
from sillo_oauth import (
    GoogleOAuthProvider,
    GithubOAuthProvider,
    DiscordOAuthProvider,
    MicrosoftOAuthProvider,
)

google = GoogleOAuthProvider(
    client_id=..., client_secret=..., state_secret=..., redirect_uri=...,
)
```

Each fills in its authorize, token and userinfo endpoints, its default scopes,
and its profile mapping. Every one of those is overridable per instance.

| Provider | Default scopes | Notes |
| --- | --- | --- |
| `GoogleOAuthProvider` | `openid email profile` | `email_verified` is meaningful: Google states it. |
| `GithubOAuthProvider` | `read:user user:email` | PKCE off; makes a second call for a private email. |
| `DiscordOAuthProvider` | `identify email` | Builds the avatar CDN URL from the hash. |
| `MicrosoftOAuthProvider` | `openid email profile` | Tenant-scoped endpoints. |

###  GitHub's two departures

Both are GitHub's, not the package's, and both are handled for you:

- **PKCE is off.** GitHub's OAuth app flow does not implement it, so the
  parameters are not sent.
- **A profile can come back with `email: null`**, because GitHub honours the
  "keep my address private" setting on `/user`. When that happens and the
  `user:email` scope was granted, a second call finds the primary verified
  address. If that call fails (the scope was refused, the endpoint is down) the
  login still succeeds with `email` left as `None`, because a missing address
  is not a reason to refuse someone entry.

###  Microsoft tenants

```python
microsoft = MicrosoftOAuthProvider(
    tenant="contoso-tenant-id",   # or "common" (default), "organizations", "consumers"
    client_id=..., client_secret=..., state_secret=..., redirect_uri=...,
)
```

The tenant is substituted into both the authorize and token endpoints.
Microsoft's userinfo endpoint states no `email_verified` claim, so
`profile.email_verified` is always `False` there, meaning "not stated", which
is the safe reading.

##  Self-hosted and Enterprise installations

Override the endpoint, and everything derived from it follows:

```python
github = GithubOAuthProvider(
    ...,
    userinfo_endpoint="https://github.acme-corp.test/api/v3/user",
)
```

GitHub's address lookup is derived from `userinfo_endpoint`, so this moves it
to the Enterprise host too. That matters: a hardcoded fallback would send an
Enterprise access token to the public API. Set `emails_endpoint=` explicitly if
your installation does not follow the `/emails` convention.

##  Any other provider

`OAuthProvider` handles anything not listed above. Give it the endpoints:

```python
from sillo_oauth import OAuthProvider

gitlab = OAuthProvider(
    name="gitlab",
    client_id=..., client_secret=..., state_secret=..., redirect_uri=...,
    authorize_endpoint="https://gitlab.com/oauth/authorize",
    token_endpoint="https://gitlab.com/oauth/token",
    userinfo_endpoint="https://gitlab.com/api/v4/user",
    scopes=["read_user"],
)
```

`name` is not decoration. It appears in profiles and errors, it names the
default state cookie (`oauth_state_gitlab`), and it is signed into the state,
so a cookie minted for one provider cannot complete another's callback.

###  Mapping the profile

Without an explicit mapping, the base provider looks for the subject under
`sub`, `id`, `user_id` and `uid`, in that order, and picks up `email`, `name`,
`username`/`preferred_username` and `picture`/`avatar_url` when present.

When that is not enough, pass `profile_mapper`:

```python
acme = OAuthProvider(
    ...,
    profile_mapper=lambda raw: {
        "subject": raw["employee_number"],
        "email": raw["work_email"],
        "name": raw["full_name"],
    },
)
```

Or subclass, which is what you want if the provider needs more than one call:

```python
class AcmeProvider(OAuthProvider):
    name = "acme"
    authorize_endpoint = "https://acme.test/oauth/authorize"
    token_endpoint = "https://acme.test/oauth/token"
    userinfo_endpoint = "https://acme.test/api/me"

    def map_profile(self, raw):
        return {"subject": raw["uuid"], "name": raw["display"]}
```

A mapping cannot set `provider`. That is the package's to state, so a mapper
cannot claim an identity came from somewhere it did not. A response with no
determinable subject raises `profile_failed` rather than producing a profile
with a blank id, because there would be nothing stable to key an account on.

##  Constructor reference

| Argument | Effect |
| --- | --- |
| `client_id` | Public client identifier from the provider. |
| `client_secret` | Client secret. Defaults to empty, for public clients relying on PKCE alone: an empty value is omitted from the token request rather than sent blank. |
| `state_secret` | Signs state cookies and derives PKCE verifiers. Unrelated to `client_secret`; see [the security model](/v1.0/guides/oauth/security/). |
| `redirect_uri` | Callback URL. Can also be given per call. |
| `scopes` | Replaces the provider's defaults. |
| `name` | Overrides the provider name. |
| `authorize_endpoint`, `token_endpoint`, `userinfo_endpoint` | Override the endpoints. |
| `use_pkce` | Force PKCE on or off. |
| `authorize_params` | Extra query parameters on every authorize URL, e.g. `{"access_type": "offline"}`. |
| `token_headers`, `userinfo_headers` | Merged over the provider's defaults, so adding one header does not drop the `Accept` several providers need. |
| `profile_mapper` | Replaces the field mapping. |
| `transport` | An `httpx` transport, for tests and proxies. |
| `timeout` | Per-request timeout for token and userinfo calls. |

##  Refresh tokens

Most providers only issue one when asked for offline access:

```python
google = GoogleOAuthProvider(..., authorize_params={"access_type": "offline"})

tokens = await refresh_tokens(google, refresh_token=stored)
```

Providers that reuse a refresh token simply omit it from the response;
`refresh_tokens` carries the one you passed in onto the result in that case, so
storing `tokens.refresh_token` unconditionally is safe and cannot overwrite a
working token with `None`.

##  Testing against a provider

Every provider accepts an `httpx` transport, which is the seam to use instead
of a live account:

```python
import httpx
from sillo import HttpContext

def handler(ctx: HttpContext):
    if "token" in str(ctx.url):
        return httpx.Response(200, json={"access_token": "test-token"})
    return httpx.Response(200, json={"sub": "1", "email": "ada@example.com"})

google = GoogleOAuthProvider(..., transport=httpx.MockTransport(handler))
```

The package's own suite runs entirely this way (no network, no credentials) and
breaks httpx's real transport during tests so a missing stub fails loudly
rather than reaching out to Google.
