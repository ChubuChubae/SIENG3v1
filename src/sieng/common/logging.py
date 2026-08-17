"""Logging with a filter that strips anything that looks like key material.

A key that reaches a log file is the most common way crypto systems leak in practice.
The filter runs on the logger itself, not on a handler, so it applies no matter where
the record ends up: file, console, or a test harness that installs its own handler.

Annotated in full because the strict layers import it (PROJECT_CONTEXT.md 2.2.1).
"""

import logging
import re
from typing import IO

LOGGER_ROOT = "sieng"
REDACTED = "<redacted>"

# Anything long and hex-ish is a key, nonce, digest or ciphertext.
# 32 hex chars is 16 bytes, the smallest thing worth hiding.
HEX_RUN = re.compile(r"\b[0-9a-fA-F]{32,}\b")

# Byte literals as they appear in repr(), e.g. b'\x9f\x12...' or b"..."
BYTES_LITERAL = re.compile(r"b(['\"])(?:\\x[0-9a-fA-F]{2}|[^'\"\\]){8,}?\1")

# name = value and name: value where the name suggests a secret.
# fingerprint is deliberately not in this list, it is meant to be shown to users.
SECRET_NAMES = ("key", "nonce", "secret", "password", "passphrase", "token", "seed", "chain")
NAMED_SECRET = re.compile(
    r"(?i)\b(\w*(?:" + "|".join(SECRET_NAMES) + r")\w*)\s*([=:])\s*(\S+)",
)


def redact(text: str) -> str:
    """Replace anything that looks like key material with <redacted>.

    Order matters: named secrets first, because the value may be short enough that the
    other two patterns would miss it.
    """
    text = NAMED_SECRET.sub(rf"\1\2{REDACTED}", text)
    text = BYTES_LITERAL.sub(REDACTED, text)
    return HEX_RUN.sub(REDACTED, text)


class RedactingFilter(logging.Filter):
    """Renders the record, redacts the result, and clears the arguments.

    Rendering first is deliberate. logger.debug("key=%s", key) keeps the secret in args,
    so filtering msg alone would leak it once the handler formats the record. Filtering
    msg and args separately does not work either: the pattern for "name = value" matches
    the placeholder itself, turning "key=%s" into "key=<redacted>" while args still holds
    one item, which makes logging raise TypeError at format time.

    Redacting the rendered text also catches secrets that only appear after formatting.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except (TypeError, ValueError):
            # Broken format string. Log something rather than swallowing the record.
            rendered = f"{record.msg!r} {record.args!r}"

        record.msg = redact(rendered)
        record.args = ()
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a logger that redacts secrets.

    Use this everywhere instead of logging.getLogger. The filter is attached per logger
    because Python does not inherit filters from parent loggers.
    """
    logger = logging.getLogger(name)
    if not any(isinstance(f, RedactingFilter) for f in logger.filters):
        logger.addFilter(RedactingFilter())
    return logger


def configure_logging(level: str = "INFO", stream: IO[str] | None = None) -> logging.Logger:
    """Install one console handler on the sieng root logger. Call once at startup."""
    root = get_logger(LOGGER_ROOT)
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)
    return root
