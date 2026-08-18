"""``.env`` support, without a dependency.

Sillo reads ``.env`` files itself — ``python-dotenv`` is not required, not
installed, and not imported anywhere in the framework.

Most projects never call anything here. :class:`sillo.SilloApp` and
:class:`sillo.config.Config` load the project's ``.env`` on their own, so
``os.environ`` is already populated by the time application code runs::

    from sillo.config import Config

    class Settings(Config):
        database_url: str
        debug: bool = False

    settings = Settings()   # .env has already been read

The functions are here for the times that is not enough — a second file, a
different precedence, or one value read straight out of the environment::

    from sillo.env import env, find_env, load_env, parse_env

    load_env(".env.local", override=True)   # layer a local file on top
    port = env("PORT", 8000, cast=int)      # one typed read
    values = parse_env(text)                # parse without touching os.environ
"""

from sillo.env._loader import (
    DEFAULT_ENV_FILE,
    ENV_FILE_VARIABLE,
    autoload,
    env,
    find_env,
    load_env,
    parse_env,
)

__all__ = [
    "DEFAULT_ENV_FILE",
    "ENV_FILE_VARIABLE",
    "autoload",
    "env",
    "find_env",
    "load_env",
    "parse_env",
]
