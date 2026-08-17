"""Central config. Precedence: argument > SIENG_* env var > TOML file > default.

Settings is frozen because default_stc_height and max_ratchet_skip affect security.
If they could change mid-run, the system's behaviour would be unpredictable.
Use with_overrides() to get a different value.
"""

import os
from dataclasses import dataclass, replace
from pathlib import Path

from sieng.common.errors import ConfigError

# Rationale for these values: docs/PROJECT_STRUCTURE.md 4.1
DEFAULT_STC_HEIGHT = 10  # STC constraint height, use 12 for numbers in the paper
DEFAULT_PAYLOAD_RATE = 0.1  # bpnzAC
DEFAULT_MAX_RATCHET_SKIP = 1000  # caps how far the receiver will ratchet forward
DEFAULT_LOG_LEVEL = "INFO"

ENV_PREFIX = "SIENG_"
STC_HEIGHT_RANGE = (6, 14)
PAYLOAD_RATE_RANGE = (0.001, 1.0)
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# field name -> how to parse it from the raw env string
ENV_FIELDS = {
    "workspace_dir": Path,
    "temp_dir": Path,
    "docker_enabled": lambda text: text.strip().lower() in ("1", "true", "yes", "on"),
    "default_stc_height": int,
    "default_payload_rate": float,
    "max_ratchet_skip": int,
    "log_level": lambda text: text.strip().upper(),
}


class SettingsError(ConfigError):
    """Bad config. The message must say what is wrong and what values are accepted."""


@dataclass(frozen=True)
class Settings:
    """Everything SIENG3 can be configured with."""

    workspace_dir: Path
    temp_dir: Path
    docker_enabled: bool = True
    default_stc_height: int = DEFAULT_STC_HEIGHT
    default_payload_rate: float = DEFAULT_PAYLOAD_RATE
    max_ratchet_skip: int = DEFAULT_MAX_RATCHET_SKIP
    log_level: str = DEFAULT_LOG_LEVEL

    def __post_init__(self):
        """Reject out-of-range values instead of clamping them, so typos surface immediately."""
        low, high = STC_HEIGHT_RANGE
        if not low <= self.default_stc_height <= high:
            raise SettingsError(
                f"Invalid default_stc_height={self.default_stc_height}: "
                f"must be between {low} and {high} "
                f"(higher = better coding efficiency but exponentially slower)"
            )

        low, high = PAYLOAD_RATE_RANGE
        if not low <= self.default_payload_rate <= high:
            raise SettingsError(
                f"Invalid default_payload_rate={self.default_payload_rate}: "
                f"must be between {low} and {high} bpnzAC "
                f"(research payload rates are 0.05 / 0.1 / 0.2 / 0.4)"
            )

        if self.max_ratchet_skip < 1:
            raise SettingsError(
                f"Invalid max_ratchet_skip={self.max_ratchet_skip}: must be at least 1 "
                f"(this cap stops a forged counter from making the receiver ratchet forever)"
            )

        if self.log_level not in LOG_LEVELS:
            raise SettingsError(
                f"Invalid log_level='{self.log_level}': must be one of {', '.join(LOG_LEVELS)}"
            )

    def with_overrides(self, **changes):
        """Copy with some fields changed, e.g. settings.with_overrides(log_level="DEBUG")."""
        return replace(self, **changes)


def default_workspace():
    """Work folder lives in the user's home, not next to the program."""
    return Path.home() / ".sieng" / "workspace"


def read_env():
    """Read SIENG_* vars that are actually set, e.g. SIENG_LOG_LEVEL=debug -> log_level="DEBUG"."""
    values = {}
    for field, convert in ENV_FIELDS.items():
        raw = os.environ.get(ENV_PREFIX + field.upper())
        if raw is None:
            continue
        try:
            values[field] = convert(raw)
        except (TypeError, ValueError) as error:
            raise SettingsError(
                f"Cannot parse {ENV_PREFIX}{field.upper()}='{raw}': "
                f"expected a value convertible to "
                f"{getattr(convert, '__name__', 'the expected type')}"
            ) from error
    return values


def read_toml(path: Path):
    """Read a TOML config. Accepts keys under [sieng] or at the top level.

    tomllib is imported here so this module still imports on runtimes without it.
    """
    import tomllib

    with path.open("rb") as file:
        data = tomllib.load(file)
    section = data.get("sieng", data)
    return section if isinstance(section, dict) else {}


def load_settings(config_path: Path | None = None, **overrides):
    """Build Settings from every source. Call once at startup and pass the result around.

    Calling this from other modules gives you a second, possibly different config.
    """
    values = {"workspace_dir": default_workspace(), "temp_dir": default_workspace() / "tmp"}

    if config_path is not None:
        if not Path(config_path).is_file():
            raise SettingsError(
                f"Config file not found: {config_path} "
                f"(pass no path at all to use defaults, instead of pointing at a missing file)"
            )
        values.update(read_toml(Path(config_path)))

    values.update(read_env())
    values.update(overrides)

    values["workspace_dir"] = Path(values["workspace_dir"]).expanduser()
    values["temp_dir"] = Path(values["temp_dir"]).expanduser()

    # A silently ignored typo means running on defaults while believing the config applied
    unknown = sorted(set(values) - set(Settings.__dataclass_fields__))
    if unknown:
        known = ", ".join(sorted(Settings.__dataclass_fields__))
        raise SettingsError(f"Unknown config key(s): {', '.join(unknown)}. Valid keys are: {known}")

    return Settings(**values)
