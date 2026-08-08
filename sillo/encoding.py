"""Response encoding utilities.

This is the import path the serialization guide documents, and it re-exports
the encoder that lives in :mod:`sillo.core.encoding`. Both paths refer to the
same registry object, so an encoder registered through either is visible to the
other.

    from sillo.encoding import register_encoder

    register_encoder(MyType, lambda value: str(value))
"""

from sillo.core.encoding import (
    CUSTOM_ENCODERS,
    ENCODERS_BY_TYPE,
    encoders_by_class_tuples,
    generate_encoders_by_class_tuples,
    get_custom_encoders,
    jsonable_encoder,
    register_encoder,
)

__all__ = [
    "CUSTOM_ENCODERS",
    "ENCODERS_BY_TYPE",
    "encoders_by_class_tuples",
    "generate_encoders_by_class_tuples",
    "get_custom_encoders",
    "jsonable_encoder",
    "register_encoder",
]
