"""SIENG3 - adaptive JPEG/PNG steganography with hybrid post-quantum cryptography.

Layer structure and the reasoning behind it: docs/PROJECT_STRUCTURE.md
"""

__version__ = "3.0.0.dev0"

# Identifies the crypto this build produces. Bump it whenever the format changes (8.4).
CRYPTO_SUITE = "x25519-mlkem768-gcmsiv/v1"

__all__ = ["CRYPTO_SUITE", "__version__"]
