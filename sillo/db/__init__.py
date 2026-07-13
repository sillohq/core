"""
sillo.db — Database toolkit for sillo.

Wraps Tortoise ORM with a sillo-native developer experience:

- :class:`Model` — enhanced base with soft-delete, serialization, bulk ops
- :class:`DatabaseManager` — connection lifecycle via ``app.state``
- :func:`setup_db` — one-call wiring with startup/shutdown hooks
- :class:`MigrationManager` — schema migrations powered by aerich
- :mod:`sillo.db.queries` — pagination, async iteration, explain plans
- :mod:`sillo.db.fields` — custom field types and shortcuts
"""

from .fields import (
    BigIntField,
    BoolField,
    CharField,
    CreatedAtField,
    DateTimeField,
    DateField,
    DecimalField,
    EncryptedField,
    FloatField,
    ForeignKey,
    IntField,
    JSONListField,
    ManyToMany,
    OneToOne,
    SlugField,
    SmallIntField,
    SoftDeleteField,
    TextField,
    TimeDeltaField,
    ULIDField,
    UpdatedAtField,
)
from .manager import DatabaseManager, get_db, setup_db
from .migration import MigrationManager
from .models import Model
from .types import (
    DatabaseBackend,
    DatabaseConfig,
    DatabaseError,
    IndexType,
    IntegrityAction,
)

__all__ = [
    "Model",
    "DatabaseManager",
    "setup_db",
    "get_db",
    "MigrationManager",
    "DatabaseConfig",
    "DatabaseBackend",
    "DatabaseError",
    "IndexType",
    "IntegrityAction",
    # Fields
    "CreatedAtField", "UpdatedAtField", "SoftDeleteField",
    "SlugField", "EncryptedField", "JSONListField", "ULIDField",
    "IntField", "BigIntField", "SmallIntField", "FloatField",
    "DecimalField", "BoolField", "CharField", "TextField",
    "DateTimeField", "DateField", "TimeDeltaField",
    "ForeignKey", "OneToOne", "ManyToMany",
]
