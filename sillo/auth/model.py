from dataclasses import dataclass


@dataclass
class AuthResult:
    """Result of an authentication backend's attempt to resolve a caller's identity.

    This dataclass is returned by every ``AuthenticationBackend.authenticate``
    implementation to communicate whether authentication succeeded and, if so,
    what identity and scope were resolved. The middleware and ``useAuth`` gate
    inspect the ``success`` flag to decide whether to accept or reject the
    request.

    Attributes:
        identity: The resolved user identifier string. On success this is a
            non-empty string (e.g. a user ID, email, or API key token). On
            failure it is an empty string.
        scope: A label identifying the authentication method that succeeded
            (e.g. ``"jwt"``, ``"session"``, ``"apikey"``). On failure this
            is an empty string. Used by scope-checking gates to restrict
            routes to specific authentication methods.
        success: Boolean flag indicating whether authentication succeeded.
            ``True`` means the backend resolved a valid identity; ``False``
            means the backend could not authenticate the request and the
            next backend should be tried.

    Example:
        Create a successful auth result from a backend::

            return AuthResult(success=True, identity="user_123", scope="jwt")
    """

    identity: str
    scope: str
    success: bool
