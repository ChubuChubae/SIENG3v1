"""Identity and key binding. Closes the MITM hole that a KEM alone cannot.

A KEM only proves you share a secret with someone. It does not prove that someone is
who you meant to talk to.
"""

AUTH_IMPLICIT = 0x01     # 0 B overhead, the default
AUTH_PQ_EXPLICIT = 0x02  # 3373 B overhead, used when the envelope is external

__all__ = ["AUTH_IMPLICIT", "AUTH_PQ_EXPLICIT"]
