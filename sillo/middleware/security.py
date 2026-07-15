# Backward-compatibility: SecurityMiddleware has been renamed to Shield
# and moved to sillo.security.shield
from sillo.security.shield import Shield

SecurityMiddleware = Shield  # backward-compat alias

__all__ = ["SecurityMiddleware", "Shield"]
