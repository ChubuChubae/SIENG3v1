"""Readable names for the identifiers the registries use.

`juniward_stc` is a key in a registry. It is a fine key and a bad thing to show someone,
because it reads like a variable name and tells a user nothing they can act on. The
mapping lives here rather than in a page so that every screen calls the same engine the
same thing.

An id with no entry is shown as itself. That is a missing name, which is a small problem,
rather than a crash or a silently wrong one.
"""

ENGINE_NAMES = {
    "juniward_stc": "J-UNIWARD + STC",
    "hill_stc": "HILL + STC",
    "uerd_stc": "UERD + STC",
}

ENGINE_NOTES = {
    "juniward_stc": "Adaptive JPEG embedding with syndrome-trellis codes. Recommended.",
    "hill_stc": "Spatial-domain cost model with syndrome-trellis codes.",
    "uerd_stc": "Faster JPEG cost model. Slightly easier to detect than J-UNIWARD.",
}

ENGINE_DETAILS = {
    "juniward_stc": [
        ("Domain", "Quantised DCT"),
        ("Cost model", "J-UNIWARD"),
        ("Coding", "Syndrome-trellis codes"),
        ("Encryption", "AES-256-GCM-SIV, one key per message"),
    ],
}


def engine_name(engine_id: str) -> str:
    return ENGINE_NAMES.get(engine_id, engine_id)
