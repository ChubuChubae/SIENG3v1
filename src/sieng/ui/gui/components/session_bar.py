"""One session, chosen once, shown everywhere.

The session was a block on the Hide page and the same block again on the Read page. That
is wrong about what a session is: it is not a setting belonging to an operation, it is the
state the whole program is currently working in, and having two copies of the control
invites the user to point them at two different files without noticing.

So the selection lives here, once, under the title bar. Both pages read it, the Sessions
page writes to it when a session is created or joined, and every page hears about a change
through one signal.

The password is deliberately **not** here. A session file on the bar is a fact about what
this window is pointed at; the password is a secret typed for one operation and cleared
straight afterwards, and a window-wide password box would exist to be left filled in.
"""

from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from sieng.ui.gui.components import recall
from sieng.ui.gui.components.icons import icon
from sieng.ui.gui.components.widgets import label, small_button

STATE_FILTER = "Session state (*.state);;All files (*)"


class SessionSelection(QObject):
    """Which session file the window is working with. One instance, held by the window."""

    changed = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        # Offered from the last run only if the user asked to be remembered. recall
        # returns None when the file has moved, so a stale path never appears here.
        self.path: Path | None = recall.recall(recall.LAST_SESSION)

    def set_path(self, path: Path | None) -> None:
        self.path = path
        recall.remember(recall.LAST_SESSION, path)
        self.changed.emit(path)


class SessionBar(QFrame):
    """The strip that says which session is loaded, with the buttons to change it."""

    def __init__(self, selection: SessionSelection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sessionBar")
        self.selection = selection

        row = QHBoxLayout(self)
        row.setContentsMargins(30, 10, 30, 10)
        row.setSpacing(12)

        glyph = label("", "sessionGlyph")
        glyph.setPixmap(icon("key", size=16).pixmap(16, 16))
        glyph.setFixedWidth(18)
        row.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignVCenter)

        names = QVBoxLayout()
        names.setSpacing(1)
        self._name = label("", "sessionName")
        self._where = label("", "sessionWhere")
        names.addWidget(self._name)
        names.addWidget(self._where)
        row.addLayout(names, stretch=1)

        row.addWidget(small_button("Choose", self._browse))
        self._clear_button = small_button("Clear", self._clear)
        row.addWidget(self._clear_button)

        selection.changed.connect(self._show)
        self._show(selection.path)

    def _browse(self) -> None:
        start = str(self.selection.path.parent) if self.selection.path else ""
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose a session", start, STATE_FILTER)
        if chosen:
            self.selection.set_path(Path(chosen))

    def _clear(self) -> None:
        """Unload the session. The file is not touched; the window stops pointing at it."""
        self.selection.set_path(None)

    def _show(self, path: Path | None) -> None:
        if path is None:
            self._name.setText("No session loaded")
            self._where.setText("Create or join one on the Sessions page")
        else:
            self._name.setText(path.name)
            self._where.setText(str(path.parent))
        self._clear_button.setVisible(path is not None)
        self.setProperty("loaded", "true" if path else "false")
        style = self.style()
        if style is not None:
            style.unpolish(self)
            style.polish(self)
