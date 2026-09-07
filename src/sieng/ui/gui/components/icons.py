"""Loading the SVGs in assets/ at the colour the theme wants them.

The icon set is drawn with `stroke="currentColor"`, which is a CSS idea. Qt has no such
notion: handed one of these files it paints black, and black on #0A0B10 is nothing at all.
So the colour is substituted into the source before it is rendered, which is why these come
back as pixmaps rather than as a plain QIcon over the file.

Two colours per icon, not one. A sidebar entry that is selected should look selected in the
icon as well as in the bar beside it, and Qt already has the mechanism: State.Off for the
resting look, State.On for the checked one.

An icon is decoration. A missing or unreadable file gives back an empty QIcon, because a
window that opens without a picture is better than one that does not open.
"""

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "svg"

# Matches the sidebar rules in default.qss: resting text is paper at 62%, selected is full.
RESTING = "#9FB2C4"
SELECTED = "#F5F9FC"

# Drawn at twice the requested size so the icon stays sharp on a scaled display.
SUPERSAMPLE = 2


def _pixmap(name: str, colour: str, size: int) -> QPixmap | None:
    """Render one SVG at one colour, or None if it cannot be drawn."""
    path = ICON_DIR / f"{name}.svg"
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Imported here, not at the top: QtSvg is optional in some builds and icons are not
    # worth an import error at startup.
    from PyQt6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(source.replace("currentColor", colour).encode()))
    if not renderer.isValid():
        return None

    pixmap = QPixmap(QSize(size * SUPERSAMPLE, size * SUPERSAMPLE))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(SUPERSAMPLE)
    return pixmap


@lru_cache(maxsize=64)
def icon(name: str, resting: str = RESTING, selected: str = SELECTED, size: int = 18) -> QIcon:
    """The named icon, dim when unchecked and bright when checked."""
    result = QIcon()
    off = _pixmap(name, resting, size)
    on = _pixmap(name, selected, size)
    if off is None or on is None:
        return result
    result.addPixmap(off, QIcon.Mode.Normal, QIcon.State.Off)
    result.addPixmap(on, QIcon.Mode.Normal, QIcon.State.On)
    result.addPixmap(on, QIcon.Mode.Active, QIcon.State.Off)
    return result
