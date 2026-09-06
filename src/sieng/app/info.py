"""What the ui is allowed to say about the system, gathered in one place.

The ui may not import crypto (import-linter, "ui never holds raw keys"), so it cannot ask
the crypto layer what its own limitations are. It should not have to: a screen that
described those limitations in its own words would drift from the code the first time the
code changed, and the drift would be in the direction of claiming more than is true.

So the text comes from the modules that own it, and this file is the counter it is handed
over at.
"""

from typing import Any

from sieng import CRYPTO_SUITE, __version__
from sieng.crypto import zeroize
from sieng.crypto.kem import mlkem768
from sieng.crypto.ratchet import rollback_guard


def system_info(container: Any) -> dict[str, Any]:
    """Version, what is wired up, and what this build cannot do.

    The three limitation entries are read from the modules that implement them rather than
    written here, so a screen showing them cannot promise something the code does not do.
    """
    return {
        "version": __version__,
        "crypto_suite": CRYPTO_SUITE,
        "engines": container.engines.ids(),
        "cost_models": container.costs.names(),
        "carriers": container.carriers.suffixes(),
        "post_quantum_available": mlkem768.is_available(),
        "limitations": [
            zeroize.limitations(),
            (
                "Ratchet rollback is detected, not prevented. Anyone who can write the "
                "session file can restore an older copy; SIENG3 refuses to continue when "
                "it notices, which is the next time you send."
            )
            if not rollback_guard.prevention_is_possible()
            else "",
            (
                "A .sess file on disk is itself evidence that this program was used. It "
                "proves nothing about any image, but it answers the question that usually "
                "matters most."
            ),
        ],
    }


def readiness(container: Any) -> tuple[bool, str]:
    """Whether the build can actually do post-quantum work, and what to say if not.

    Checked once at startup so a user finds out before choosing a file, rather than in the
    middle of an embed.
    """
    if mlkem768.is_available():
        return True, "Post-quantum key establishment is available"
    return False, mlkem768.UNAVAILABLE
