"""The small pieces every page is built from, named to match default.qss.

The theme selects on object names, so a widget that does not set the right one gets no
styling at all and looks broken. The names are set here once rather than remembered at
every call site.

Three pieces have real behaviour rather than just a name.

`FileDropZone` has two states. Empty it invites a drop; filled it shows what was chosen,
how big it is, and for an image its dimensions, with Change and Remove beside it. The
second state exists because "did I pick the right file" is a question the user should not
have to answer by clicking to find out.

`Disclosure` hides a section behind a triangle. It is what keeps session settings off the
first screen without removing them, which is the whole of "simple by default, technical
when needed".

`Segmented` is the preset row. It reports the value it moved to, and the page decides what
that value means; this file does not know what a payload rate is.
"""

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sieng.ui.gui.components.icons import icon

THUMBNAIL = QSize(56, 56)

# Formats QImageReader will be asked about. Anything else is described by size alone.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".jpe", ".png", ".bmp", ".gif", ".webp"}


# ---- text ------------------------------------------------------------------


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def _centred_line(text: str, name: str) -> QLabel:
    """One line of text that stays one line. Wrapping here is what overflowed the box."""
    line = QLabel(text)
    line.setObjectName(name)
    line.setWordWrap(False)
    line.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return line


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


# ---- buttons ---------------------------------------------------------------


def primary_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryActionBtn")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setMinimumHeight(46)
    if on_click:
        button.clicked.connect(on_click)
    return button


def secondary_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SecondaryBtn")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(on_click)
    return button


def small_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    """For actions attached to something else, like Change next to a chosen file."""
    button = QPushButton(text)
    button.setObjectName("SmallBtn")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(on_click)
    return button


def link_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    """A quiet button for an offer rather than an instruction."""
    button = QPushButton(text)
    button.setObjectName("LinkBtn")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if on_click:
        button.clicked.connect(on_click)
    return button


def show_in_folder(path: Path) -> None:
    """Open the folder a file landed in, using whatever the system uses for folders."""
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))


# ---- page furniture --------------------------------------------------------


class PageHeader(QWidget):
    """The title of a page and one line saying what it is for.

    There was a state chip here. It mixed three different things into one word — an
    instruction, a running state, and a page mode — and none of them read as any of the
    others. Progress and outcome live at the bottom of the page instead, next to the
    button that starts the work.
    """

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(3)
        column.addWidget(label(title, "pageTitle"))
        column.addWidget(label(subtitle, "pageSubtitle"))


class CapacityMeter(QFrame):
    """How full the cover would be, as a bar and as a sentence.

    A percentage is the honest summary of the choice being made. The bar turns amber past
    seventy percent and red past a hundred, and the sentence says why in words rather than
    leaving the colour to carry the meaning on its own: a nearly full cover is what a
    detector is best at seeing.
    """

    WARN_AT = 70

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("capacityMeter")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(7)

        self.headline = label("", "capacityHeadline")
        self.bar = QProgressBar()
        self.bar.setObjectName("capacityBar")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setRange(0, 100)
        self.note = label("", "capacityNote")
        column.addWidget(self.headline)
        column.addWidget(self.bar)
        column.addWidget(self.note)

    def show_unknown(self, message: str) -> None:
        """No number to give, so no bar to draw."""
        self.headline.setText(message)
        self.note.setText("")
        self.bar.setValue(0)
        self._tone("ok")

    def show_fill(self, needed: int, available: int) -> None:
        percent = 100 if available <= 0 else round(needed * 100 / available)
        self.headline.setText(
            f"{human_size(needed)} to hide · about {human_size(available)} available "
            f"at this rate · {percent}% full"
        )
        self.bar.setValue(min(percent, 100))
        if percent > 100:
            self.note.setText(
                "This will not fit. Use a larger image, or raise the rate and accept "
                "that a fuller image is easier to spot."
            )
            self._tone("over")
        elif percent >= self.WARN_AT:
            self.note.setText(
                "Filling most of an image is the pattern detection tools look for. "
                "A larger image at the same rate hides the same file more safely."
            )
            self._tone("warn")
        else:
            self.note.setText("There is room to spare, which is the safer place to be.")
            self._tone("ok")

    def show_capacity_only(self, available: int) -> None:
        self.headline.setText(f"About {human_size(available)} would fit at this rate")
        self.note.setText("Choose the file to hide to see how full that would leave it.")
        self.bar.setValue(0)
        self._tone("ok")

    def _tone(self, tone: str) -> None:
        for widget in (self, self.bar, self.headline, self.note):
            widget.setProperty("capacityState", tone)
            _restyle(widget)


class Card(QFrame):
    """A panel. A page is a short stack of these, not a long one."""

    def __init__(
        self,
        title: str = "",
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 20, 24, 22)
        self.body.setSpacing(12)
        if title:
            self.body.addWidget(label(title, "cardTitle"))
        if subtitle:
            self.body.addWidget(label(subtitle, "cardSubtitle"))

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def field(self, name: str, widget: QWidget, hint: str = "") -> QWidget:
        """A label, the thing it names, and an optional line under it explaining why."""
        self.body.addWidget(label(name, "formLabel"))
        self.body.addWidget(widget)
        if hint:
            self.body.addWidget(label(hint, "hintLabel"))
        return widget

    def add_row(self, *widgets: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        for widget in widgets:
            row.addWidget(widget)
        self.body.addLayout(row)
        return row


class Disclosure(QFrame):
    """A section folded away behind its own title. Closed unless told otherwise."""

    def __init__(self, title: str, open_at_start: bool = False) -> None:
        super().__init__()
        self.setObjectName("disclosure")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        self._title = title
        self._toggle = QPushButton()
        self._toggle.setObjectName("disclosureToggle")
        self._toggle.setCheckable(True)
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.toggled.connect(self._on_toggled)
        column.addWidget(self._toggle)

        self.body_widget = QFrame()
        self.body_widget.setObjectName("disclosureBody")
        self.body = QVBoxLayout(self.body_widget)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(10)
        column.addWidget(self.body_widget)

        self._toggle.setChecked(open_at_start)
        self._on_toggled(open_at_start)

    def _on_toggled(self, opened: bool) -> None:
        self._toggle.setText(f"{'▾' if opened else '▸'}  {self._title}")
        self.body_widget.setVisible(opened)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def field(self, name: str, widget: QWidget, hint: str = "") -> QWidget:
        self.body.addWidget(label(name, "formLabel"))
        self.body.addWidget(widget)
        if hint:
            self.body.addWidget(label(hint, "hintLabel"))
        return widget


class Segmented(QWidget):
    """A row of choices where exactly one is picked. Emits the key of the new one."""

    changed = pyqtSignal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._keys: list[str] = []
        for index, (key, text) in enumerate(options):
            button = QPushButton(text)
            button.setObjectName("segmentBtn")
            button.setCheckable(True)
            button.setMinimumHeight(38)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(button, index)
            self._keys.append(key)
            row.addWidget(button)
        self._group.idClicked.connect(lambda index: self.changed.emit(self._keys[index]))

    def select(self, key: str) -> None:
        """Set the choice without claiming the user made it: no signal is emitted."""
        if key in self._keys:
            button = self._group.button(self._keys.index(key))
            if button is not None:
                button.setChecked(True)

    def clear_selection(self) -> None:
        """Nothing chosen, which is how a custom value is shown."""
        self._group.setExclusive(False)
        for button in self._group.buttons():
            button.setChecked(False)
        self._group.setExclusive(True)


class DetailTable(QFrame):
    """Name and value rows for the technical details a page keeps folded away."""

    def __init__(self, rows: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailTable")
        column = QVBoxLayout(self)
        column.setContentsMargins(14, 12, 14, 12)
        column.setSpacing(6)
        for name, value in rows:
            row = QHBoxLayout()
            row.setSpacing(12)
            key = label(name, "detailKey")
            key.setFixedWidth(110)
            row.addWidget(key)
            row.addWidget(label(value, "detailValue"), stretch=1)
            column.addLayout(row)


# ---- files -----------------------------------------------------------------


class FileDropZone(QFrame):
    """Drop a file here or click to browse, then see what you chose."""

    chosen = pyqtSignal(object)

    def __init__(
        self,
        prompt: str = "Drop a file here",
        filters: str = "All files (*)",
        start_dir: str = "",
        hint: str = "",
        icon_name: str = "file-plus",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fileDropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # A minimum, never a fixed height. A fixed one is what made the prompt sit on top
        # of the icon and cut the hint in half when the text needed a second line.
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        self._filters = filters
        self._prompt = prompt
        self._hint = hint
        self._icon_name = icon_name
        self.start_dir = start_dir
        self.path: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(0)
        self._empty = self._build_empty()
        self._filled = self._build_filled()
        outer.addWidget(self._empty)
        outer.addWidget(self._filled)

        self.set_path(None)

    # ---- the two faces of the same box -------------------------------------

    def _build_empty(self) -> QWidget:
        holder = QWidget()
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(6)
        column.setAlignment(Qt.AlignmentFlag.AlignCenter)

        glyph = QLabel()
        glyph.setPixmap(icon(self._icon_name, size=24).pixmap(24, 24))
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setFixedHeight(26)
        column.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignCenter)

        for text, name in ((self._prompt, "dropPrompt"), ("or click to browse", "dropAction")):
            line = _centred_line(text, name)
            column.addWidget(line)
        self._hint_line = _centred_line(self._hint, "dropHint")
        self._hint_line.setVisible(bool(self._hint))
        column.addWidget(self._hint_line)
        return holder

    def _build_filled(self) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        self._thumb = QLabel()
        self._thumb.setFixedSize(THUMBNAIL)
        self._thumb.setObjectName("fileThumb")
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._thumb)

        names = QVBoxLayout()
        names.setSpacing(2)
        self._name = _centred_line("", "fileInfoName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._detail = _centred_line("", "fileInfoDetail")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        names.addWidget(self._name)
        names.addWidget(self._detail)
        row.addLayout(names, stretch=1)

        row.addWidget(small_button("Change", self._browse))
        row.addWidget(small_button("Remove", self.clear))
        return holder

    # ---- what the user does ------------------------------------------------

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self, "Choose a file", self.start_dir, self._filters
        )
        if chosen:
            self.set_path(Path(chosen))

    def mousePressEvent(self, event) -> None:
        """Clicking the empty box browses. Once a file is there, only the buttons act."""
        if self.path is None:
            self._browse()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._restyle(dragging=True)

    def dragLeaveEvent(self, event) -> None:
        self._restyle(dragging=False)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.set_path(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    # ---- state -------------------------------------------------------------

    def set_path(self, path: Path | None) -> None:
        self.path = path
        self._empty.setVisible(path is None)
        self._filled.setVisible(path is not None)
        if path is not None:
            self._name.setText(path.name)
            self._detail.setText(describe(path))
            self._thumb.setPixmap(_thumbnail(path, self._icon_name))
        self._restyle(dragging=False)
        self.chosen.emit(path)

    def clear(self) -> None:
        self.set_path(None)

    def _restyle(self, dragging: bool) -> None:
        self.setProperty("hasFile", "true" if self.path is not None else "false")
        self.setProperty("isDragging", "true" if dragging else "false")
        self.setCursor(
            Qt.CursorShape.ArrowCursor if self.path else Qt.CursorShape.PointingHandCursor
        )
        _restyle(self)


class SavePicker(QFrame):
    """Where the output goes: the path, and a button to change it."""

    chosen = pyqtSignal(object)

    def __init__(
        self,
        prompt: str = "Not chosen yet",
        filters: str = "All files (*)",
        start_dir: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("savePicker")
        self._filters = filters
        self._prompt = prompt
        self.start_dir = start_dir
        self.suggested = ""
        self.path: Path | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 12, 10)
        row.setSpacing(10)
        self._label = label(prompt, "savePickerPath")
        row.addWidget(self._label, stretch=1)
        row.addWidget(small_button("Browse", self._browse))

    def _browse(self) -> None:
        """Opens where the last one was saved, with a name already filled in if we have one."""
        start = str(Path(self.start_dir) / self.suggested) if self.start_dir else self.suggested
        chosen, _ = QFileDialog.getSaveFileName(self, "Save as", start, self._filters)
        if chosen:
            self.set_path(Path(chosen))

    def suggest(self, name: str) -> None:
        """A default filename to offer. Never overrides a path the user already picked."""
        self.suggested = name

    def set_path(self, path: Path | None) -> None:
        self.path = path
        self._label.setText(str(path) if path else self._prompt)
        self.setProperty("hasPath", "true" if path else "false")
        _restyle(self)
        self.chosen.emit(path)


# ---- helpers ---------------------------------------------------------------


def describe(path: Path) -> str:
    """What a person would want to know about a file they just picked."""
    try:
        size = human_size(path.stat().st_size)
    except OSError:
        return "This file cannot be read"
    kind = path.suffix.upper().lstrip(".") or "File"
    if path.suffix.lower() in IMAGE_SUFFIXES:
        reader = QImageReader(str(path))
        dimensions = reader.size()
        if dimensions.isValid():
            # A plain x, not the multiplication sign: ruff flags that one as ambiguous.
            return f"{kind} · {dimensions.width()} x {dimensions.height()} · {size}"
    return f"{kind} · {size}"


def human_size(size: float) -> str:
    """Size in the unit a person would use, without a dependency to do it."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def _thumbnail(path: Path, fallback_icon: str) -> QPixmap:
    """A small picture of an image file, or its icon if it is not one."""
    if path.suffix.lower() in IMAGE_SUFFIXES:
        reader = QImageReader(str(path))
        reader.setScaledSize(_fitted(reader.size()))
        image = reader.read()
        if not image.isNull():
            return QPixmap.fromImage(image)
    return icon(fallback_icon, size=24).pixmap(24, 24)


def _fitted(size: QSize) -> QSize:
    """Scale to fill the thumbnail box without distorting the picture."""
    if not size.isValid() or size.width() == 0 or size.height() == 0:
        return THUMBNAIL
    scale = max(THUMBNAIL.width() / size.width(), THUMBNAIL.height() / size.height())
    return QSize(max(int(size.width() * scale), 1), max(int(size.height() * scale), 1))


def _restyle(widget: QWidget) -> None:
    """Qt does not re-evaluate a stylesheet when a property changes, so ask it to."""
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
