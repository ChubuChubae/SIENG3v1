"""The small pieces every page is built from, named to match default.qss.

The theme is 1,083 lines that were written before this code and expect particular object
names: `#card`, `#sectionLabel`, `#PrimaryActionBtn`, `#fileDropZone` and so on. A widget
that does not set the right name gets no styling at all and looks broken, so the names are
set here once rather than remembered at every call site.

`FileDropZone` is the only piece with real behaviour. It accepts a drag or a click, and it
flips two Qt properties the stylesheet selects on, `hasFile` and `isDragging`. Qt does not
restyle on a property change by itself, hence the unpolish/polish dance in `_restyle`.
"""

from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def label(text: str, name: str = "") -> QLabel:
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def primary_button(text: str, on_click: Callable[[], None] | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryActionBtn")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
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


class Card(QFrame):
    """A titled panel. Most of a page is a stack of these."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)
        if title:
            self.body.addWidget(label(title, "cardTitle"))

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_row(self, *widgets: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in widgets:
            row.addWidget(widget)
        self.body.addLayout(row)
        return row


class FileDropZone(QFrame):
    """Drop a file here, or click to browse. Emits the path it ended up with."""

    chosen = pyqtSignal(object)

    def __init__(
        self,
        prompt: str = "Drop a file here, or click to choose",
        filters: str = "All files (*)",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("fileDropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(96)

        self._filters = filters
        self._prompt = prompt
        self.path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name = label(prompt, "fileInfoName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail = label("", "fileInfoDetail")
        self._detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._name)
        layout.addWidget(self._detail)

        self._restyle(has_file=False, dragging=False)

    # ---- what the user does ------------------------------------------------

    def mousePressEvent(self, event) -> None:
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose a file", "", self._filters)
        if chosen:
            self.set_path(Path(chosen))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._restyle(has_file=self.path is not None, dragging=True)

    def dragLeaveEvent(self, event) -> None:
        self._restyle(has_file=self.path is not None, dragging=False)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.set_path(Path(urls[0].toLocalFile()))
            event.acceptProposedAction()

    # ---- state -------------------------------------------------------------

    def set_path(self, path: Path | None) -> None:
        self.path = path
        if path is None:
            self._name.setText(self._prompt)
            self._detail.setText("")
        else:
            self._name.setText(path.name)
            self._detail.setText(_describe(path))
        self._restyle(has_file=path is not None, dragging=False)
        self.chosen.emit(path)

    def clear(self) -> None:
        self.set_path(None)

    def _restyle(self, has_file: bool, dragging: bool) -> None:
        """Qt does not re-evaluate a stylesheet when a property changes, so ask it to."""
        self.setProperty("hasFile", "true" if has_file else "false")
        self.setProperty("isDragging", "true" if dragging else "false")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)


class SavePicker(QFrame):
    """Where the output goes. A button and the path it produced, nothing more."""

    chosen = pyqtSignal(object)

    def __init__(
        self,
        prompt: str = "Choose where to save",
        filters: str = "All files (*)",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._filters = filters
        self.path: Path | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = label(prompt, "hintLabel")
        layout.addWidget(self._label, stretch=1)
        layout.addWidget(secondary_button("Browse", self._browse))

    def _browse(self) -> None:
        chosen, _ = QFileDialog.getSaveFileName(self, "Save as", "", self._filters)
        if chosen:
            self.set_path(Path(chosen))

    def set_path(self, path: Path | None) -> None:
        self.path = path
        self._label.setText(str(path) if path else "Choose where to save")
        self.chosen.emit(path)


def _describe(path: Path) -> str:
    """Size in the unit a human would use, without a dependency to do it."""
    try:
        size = path.stat().st_size
    except OSError:
        return "unreadable"
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
