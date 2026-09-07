"""Remembering the boring choices, but only when asked to.

Someone hiding a series of messages picks the same session file and the same output folder
every time, and making them find both again on every message is friction that pushes people
towards shortcuts. So the paths can be remembered.

They are not remembered by default. A list of the images and session files someone last
worked with is a list of exactly what an examiner would want, sitting in the registry on
Windows or a plain file elsewhere, readable by anything running as the user. Convenience
that costs that much has to be asked for rather than assumed, so `is_on()` is false until
the user turns it on, every write checks it, and `forget_everything()` removes the lot.

What is stored is only paths, in any case. Never a password, never a payload, never
anything derived from a key.

A remembered path is offered, not imposed: if the file has since moved, the field comes up
empty rather than pointing at something that no longer exists.
"""

from pathlib import Path

from PyQt6.QtCore import QSettings

ORGANISATION = "SIENG3"
APPLICATION = "sieng"

# Keys. Named for what they are so a stray value is obvious in the settings store.
REMEMBER = "paths/remember"
LAST_SESSION = "paths/last_session"
LAST_OUTPUT_DIR = "paths/last_output_dir"
LAST_COVER_DIR = "paths/last_cover_dir"

PATH_KEYS = (LAST_SESSION, LAST_OUTPUT_DIR, LAST_COVER_DIR)


def _store() -> QSettings:
    return QSettings(ORGANISATION, APPLICATION)


def is_on() -> bool:
    """Off until the user turns it on. The default is the private one."""
    return str(_store().value(REMEMBER, "false")).lower() == "true"


def set_on(on: bool) -> None:
    """Turning it off also throws away what was already kept."""
    _store().setValue(REMEMBER, "true" if on else "false")
    if not on:
        forget_everything()


def forget_everything() -> None:
    """Remove every remembered path. Used by the switch and by the button on About."""
    store = _store()
    for key in PATH_KEYS:
        store.remove(key)


def remember(key: str, path: Path | None) -> None:
    """Store a path, if the user asked for that. Passing None forgets it."""
    store = _store()
    if path is None:
        store.remove(key)
    elif is_on():
        store.setValue(key, str(path))


def recall(key: str) -> Path | None:
    """The remembered path, if there is one and it is still there.

    A path that has moved comes back as None rather than as a broken value, because a
    field pre-filled with something that does not exist is worse than an empty one.
    """
    if not is_on():
        return None
    value = _store().value(key)
    if not value:
        return None
    path = Path(str(value))
    return path if path.exists() else None


def recall_dir(key: str) -> str:
    """A starting directory for a file dialog. Empty string means the system default."""
    path = recall(key)
    if path is None:
        return ""
    return str(path if path.is_dir() else path.parent)
