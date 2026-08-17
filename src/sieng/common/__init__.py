"""Cross-cutting utilities. Depends on the standard library only, so every layer may import it."""

from sieng.common.errors import (
    CapacityError,
    CarrierError,
    ConfigError,
    CorruptCarrierError,
    CryptoError,
    DecryptError,
    IncompatibleEngineError,
    LossyCarrierError,
    PipelineError,
    PipelineValidationError,
    RatchetLimitError,
    ReplayError,
    RollbackDetected,
    SiengError,
    UnsupportedCarrierError,
)
from sieng.common.logging import configure_logging, get_logger
from sieng.common.progress import ProgressReporter
from sieng.common.types import BLOCK_SIZE, DCT_DOMAIN, SPATIAL_DOMAIN

__all__ = [
    "BLOCK_SIZE",
    "DCT_DOMAIN",
    "SPATIAL_DOMAIN",
    "CapacityError",
    "CarrierError",
    "ConfigError",
    "CorruptCarrierError",
    "CryptoError",
    "DecryptError",
    "IncompatibleEngineError",
    "LossyCarrierError",
    "PipelineError",
    "PipelineValidationError",
    "ProgressReporter",
    "RatchetLimitError",
    "ReplayError",
    "RollbackDetected",
    "SiengError",
    "UnsupportedCarrierError",
    "configure_logging",
    "get_logger",
]
