---
title: The OAuth Security Model
description: How sillo-oauth protects a login without a state store — signed state cookies, PKCE verifiers derived rather than stored, reserved parameters that cannot be overridden, and credentials kept out of logs.
head:
- tag: meta
  attrs:
    property: og:title
    content: The sillo-oauth security model
- tag: meta
  attrs:
    property: og:description
    content: Signed state instead of a state store, PKCE verifiers derived from the state, and the guarantees that follow.
---

#  The OAuth Security Model

An OAuth callback arrives as a bare `GET` from the provider, carrying values an
attacker can also send. Everything below exists to answer one question: did
*this* server start *this* login, for *this* browser?

##  State is signed, not stored

The usual answer is a random value kept server-side and echoed through the
provider. `sillo-oauth` does the same job with an HMAC-signed cookie, so
nothing needs a session store, a database row, or sticky routing between
instances.

The cookie carries a random value, an expiry, the provider name, and whatever
`return_to` you passed. It is **signed, not encrypted** — readable by whoever
holds it, unforgeable without your `state_secret`. Nothing secret is put in it.

`verify_state` refuses a callback that fails any of:

| Check | Failure |
| --- | --- |
| A state cookie was sent | `state_mismatch` |
| A `state` query parameter was returned | `state_mismatch` |
| The two match, compared in constant time | `state_mismatch` |
| The cookie's signature verifies | `state_mismatch` |
| The cookie was minted for **this** provider | `state_mismatch` |
| The cookie has not expired (default 10 minutes) | `state_expired` |

The first five collapse to one code deliberately. Each is either a forgery or
an unusable callback, and telling an attacker which half of the check they
cleared helps only them. Expiry is separate because it has a blameless cause —
someone left the consent screen open — and deserves "try again" rather than a
security-flavoured message.

<aside>

**The provider binding matters more than it looks.** Without it, an
application offering two providers could have a login started at the weaker one
completed at the stronger one's callback. The provider name is signed into the
state, so a GitHub cookie cannot satisfy a Google callback.

</aside>

##  State is verified before the provider is contacted

Nothing is sent to the token endpoint until the callback has been proven to be
yours. If state were checked afterwards, a forged callback could make your
server spend an authorization code — or redeem one an attacker planted.

Provider-reported errors (`?error=access_denied`) are handled first, before
even that, since there is no code to exchange in the first place.

##  PKCE verifiers are derived, never stored

PKCE requires a secret at the redirect step and again at the exchange. Writing
it into the cookie would put a secret somewhere readable; keeping it
server-side would reintroduce the state store this design avoids.

Instead it is recomputed at exchange time:

```
verifier = base64url(HMAC-SHA256(state_secret, "sillo-oauth/pkce/v1:" + state))
```

Deterministic, so both steps reach the same value without either storing it.
Unguessable, because `state` is 32 random bytes and `state_secret` never leaves
your server. The provider only ever sees the SHA-256 challenge; an attacker who
intercepts the authorization code still cannot redeem it.

Knowing the state is not enough — the verifier depends on the secret too. That
is what makes derivation safe rather than theatre.

##  `state_secret` is not `client_secret`

They protect different things and can be rotated independently:

| | |
| --- | --- |
| `client_secret` | Your relationship with the provider. Issued by them. |
| `state_secret` | Your own cookies. Any high-entropy application key; one can be shared across providers. |

##  Managed parameters cannot be overridden

`extra_params` and a provider's `authorize_params` are merged into the
authorize URL, but the parameters the package computes are refused rather than
overwritten:

`state`, `code_challenge`, `code_challenge_method`, `response_type`,
`client_id`, `redirect_uri`, `scope`.

```python
authorize_url(google, extra_params={"state": "chosen"})
# ProviderMisconfigured: These authorize parameters are managed by sillo-oauth
# and cannot be overridden: state (it is generated and signed into the state cookie)
```

Silently ignoring them would be worse than failing: an application that
believes it is setting `state` and is not has a security expectation the code
no longer meets. `redirect_uri` and `scope` point at their proper arguments in
the error.

##  Credentials stay out of logs

`OAuthTokens` has a redacted `repr`. Every field on it is a live credential,
and `logger.info("signed in %s", profile)` is an ordinary line to write — as is
shipping tracebacks to an error tracker, where a profile sits in a frame.

```python
repr(profile.tokens)
# OAuthTokens(access_token=<redacted>, token_type='Bearer', expires_in=3600,
#             scope='openid email', also_holds=['refresh_token'])
```

Which tokens exist, and their scope and lifetime, is what anyone debugging
wants. Attribute access is unaffected — `tokens.access_token` still returns it.

Providers redact too: a provider's `repr` shows its name and client id, never
`client_secret` or `state_secret`.

##  Cookie attributes

`cookie_kwargs()` states every attribute rather than leaving any to a
framework default:

| Attribute | Value | Why |
| --- | --- | --- |
| `httponly` | `True` | Nothing in the browser needs to read it. |
| `samesite` | `"lax"` | `"strict"` would stop the browser sending the cookie on the provider's cross-site redirect back — the one request that needs it. |
| `secure` | `True` | A live redirect URI is HTTPS. Local `http://` development needs `cookie_kwargs(secure=False)`, or the browser accepts the cookie and never returns it. |
| `max_age` | the state TTL | Expires with the value it carries. |
| `path` | `"/"` | |

Nothing is left unstated because sillo's `Responder.set_cookie` defaults
`secure` on while `BaseResponse.set_cookie` defaults it off — an unstated
attribute would make this cookie's security depend on which object the caller
happened to hold.

##  What is deliberately not protected

Worth being explicit about the edges:

- **`return_to` is signed, not validated.** It cannot be tampered with in
  transit, but you chose its value — if you build it from user input, check it
  is a local path before redirecting, or you have an open redirect.
- **`id_token` is not verified.** It is captured and handed to you as opaque.
  The identity in `OAuthProfile` comes from the userinfo endpoint, reached with
  the access token, not from an unverified JWT.
- **Nothing here authenticates later requests.** Once you have persisted the
  login, the credential is an ordinary session cookie or JWT, and its security
  is that mechanism's — see [Persisting the login](/guides/oauth/persisting-logins/).
