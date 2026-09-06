"""Key derivation. Every key in the project is made here or not at all.

Three modules, and the split is by what the input is rather than by what the output is for.

    hkdf     key -> key. The whole derivation tree of FORMAT_SPEC.md 2.1.
    argon2   password -> key. Only for things written to disk.
    labels   the domain separation strings, which are what keep the keys apart.
"""

from sieng.crypto.kdf.argon2 import derive_key, new_salt
from sieng.crypto.kdf.hkdf import KEY_BYTES, expand, expand_key, extract, length_prefixed

__all__ = [
    "KEY_BYTES",
    "derive_key",
    "expand",
    "expand_key",
    "extract",
    "length_prefixed",
    "new_salt",
]
