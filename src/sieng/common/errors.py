"""Every exception the project raises, in one hierarchy.

Catching SiengError catches everything this project throws and nothing it does not.
A bare ValueError escaping from our code is a bug, not a design choice.

    SiengError
    |-- ConfigError
    |     `-- SettingsError            (raised by app.settings)
    |-- CarrierError
    |     |-- UnsupportedCarrierError
    |     |-- LossyCarrierError
    |     `-- CorruptCarrierError
    |-- CapacityError
    |-- CryptoError
    |     |-- DecryptError
    |     |-- RatchetLimitError
    |     |-- ReplayError
    |     `-- RollbackDetected
    `-- PipelineError
          |-- IncompatibleEngineError
          `-- PipelineValidationError
"""


class SiengError(Exception):
    """Root of every error this project raises."""


# ---- config ----------------------------------------------------------------


class ConfigError(SiengError):
    """Bad configuration. The message must say what is wrong and what is accepted."""


# ---- carrier ---------------------------------------------------------------


class CarrierError(SiengError):
    """Something is wrong with the cover or stego file."""


class UnsupportedCarrierError(CarrierError):
    """File type is outside the Phase 1 scope. Never guess, never fall back."""


class LossyCarrierError(CarrierError):
    """The format cannot round trip byte exact, so embedding in it is not safe."""


class CorruptCarrierError(CarrierError):
    """The file claims to be a format it does not actually follow."""


# ---- capacity --------------------------------------------------------------


class CapacityError(SiengError):
    """Payload does not fit. Carries the real ceiling so callers can report it."""

    def __init__(self, requested_bits: int, max_bits: int, max_bpnzac: float) -> None:
        self.requested_bits = requested_bits
        self.max_bits = max_bits
        self.max_bpnzac = max_bpnzac
        super().__init__(
            f"Payload needs {requested_bits} bits but this carrier holds at most "
            f"{max_bits} bits ({max_bpnzac:.4f} bpnzAC). "
            f"Use a larger cover, raise the payload rate, or send less data."
        )


# ---- crypto ----------------------------------------------------------------


class CryptoError(SiengError):
    """Anything that goes wrong inside the crypto layer."""


class DecryptError(CryptoError):
    """Decryption failed.

    Takes no arguments on purpose. Wrong key, tampered ciphertext, wrong carrier and
    a corrupt header must all look identical to the caller, otherwise the error itself
    becomes an oracle. Callers that need to know why must not exist.
    """

    MESSAGE = "Decryption failed"

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


class RatchetLimitError(CryptoError):
    """Counter is further ahead than max_ratchet_skip allows.

    Without this cap a forged counter makes the receiver run millions of HKDF steps,
    which is a free denial of service.
    """


class ReplayError(CryptoError):
    """This counter was already consumed in this session."""


class RollbackDetected(CryptoError):
    """Ratchet state moved backwards.

    Detection only, not prevention. Anyone who can write the state file can also
    restore an old copy. See THREAT_MODEL.md 4.
    """


# ---- pipeline --------------------------------------------------------------


class PipelineError(SiengError):
    """Something went wrong while orchestrating a run."""


class IncompatibleEngineError(PipelineError):
    """The chosen engine does not support this carrier's domain."""


class PipelineValidationError(PipelineError):
    """The pipeline config is not runnable. Raised before any work starts."""
