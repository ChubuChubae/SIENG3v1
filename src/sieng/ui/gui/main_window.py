"""The window: a frameless shell with its own title bar, a sidebar, and a page stack.

Frameless because default.qss was written for one. It styles `#titleBarContainer`,
`#windowControlBtn` and `#windowCloseBtn`, which only exist if the window draws its own
chrome. Taking the system frame instead would leave a third of the theme unused and the
window looking half finished.

The cost of drawing your own title bar is that dragging and the window buttons become this
file's job. That is the whole of `_TitleBar`, and it is the only place in the ui that deals
with the window rather than with the program.

Pages are created once and kept in a QStackedWidget. They hold state a user is part way
through entering, and rebuilding a page on every visit would throw that away.

The session bar sits between the title bar and the pages because a session is the state the
whole window is working in, not a setting belonging to one screen. One selection object is
made here and handed to every page that needs it.
"""

from PyQt6.QtCore import QPoint, QSize, Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sieng import __version__
from sieng.ui.gui.components.icons import icon
from sieng.ui.gui.components.session_bar import SessionBar, SessionSelection
from sieng.ui.gui.components.widgets import label

WINDOW_SIZE = (1180, 800)
SIDEBAR_WIDTH = 216


class MainWindow(QWidget):
    """The whole application window. One instance, created by bootstrap.run."""

    def __init__(self, container: object) -> None:
        super().__init__()
        self.container = container
        self.setObjectName("rootWidget")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("SIENG3")
        self.resize(*WINDOW_SIZE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(_TitleBar(self))

        # One session for the whole window. Pages read it; the Sessions page writes it.
        self.session = SessionSelection()
        outer.addWidget(SessionBar(self.session))

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        outer.addLayout(body, stretch=1)

        self.pages = QStackedWidget()
        self._sidebar_buttons = QButtonGroup(self)
        self._sidebar_buttons.setExclusive(True)

        body.addWidget(self._build_sidebar(), stretch=0)
        body.addWidget(self.pages, stretch=1)

        self._add_pages()

    # ---- structure ---------------------------------------------------------

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebarContainer")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self._sidebar_layout = QVBoxLayout(sidebar)
        self._sidebar_layout.setContentsMargins(12, 16, 12, 16)
        self._sidebar_layout.setSpacing(6)
        return sidebar

    def _add_pages(self) -> None:
        """Build every page once. Imported here so a broken page cannot stop the window
        from opening with a message the user can read."""
        from sieng.ui.gui.pages.about_page import AboutPage
        from sieng.ui.gui.pages.embed_page import EmbedPage
        from sieng.ui.gui.pages.extract_page import ExtractPage
        from sieng.ui.gui.pages.session_page import SessionPage

        # Grouped, because "hide a file" and "manage a session" are different kinds of
        # task and a flat list of four makes them look interchangeable.
        self._add_section("FILES")
        self._add_page("Hide File", "lock-plus", EmbedPage(self.container, self.session))
        self._add_page("Read File", "lock-open", ExtractPage(self.container, self.session))
        self._add_section("SETUP")
        self._add_page("Sessions", "key", SessionPage(self.container, self.session))
        self._add_page("About", "help", AboutPage(self.container))

        first = self._sidebar_buttons.button(0)
        if first is not None:
            first.setChecked(True)
        self._sidebar_layout.addStretch(1)
        self._add_footer()

    def _add_footer(self) -> None:
        """The one place the version is visible without opening a page."""
        for text, name in (
            ("SIENG3", "sidebarFooterName"),
            ("Local steganography", "sidebarFooterLine"),
            (f"v{__version__}", "sidebarFooterLine"),
        ):
            self._sidebar_layout.addWidget(label(text, name))

    def _add_section(self, title: str) -> None:
        heading = QLabel(title)
        heading.setObjectName("sidebarSectionLabel")
        self._sidebar_layout.addWidget(heading)

    def _add_page(self, title: str, icon_name: str, page: QWidget) -> None:
        index = self.pages.count()
        self.pages.addWidget(page)

        button = QPushButton(f"  {title}")
        button.setObjectName("sidebarButton")
        button.setIcon(icon(icon_name))
        button.setIconSize(QSize(17, 17))
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _checked, i=index: self.pages.setCurrentIndex(i))
        self._sidebar_buttons.addButton(button, index)
        self._sidebar_layout.addWidget(button)


class _TitleBar(QFrame):
    """The window's own chrome: logo, title, and the three buttons on the right."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.setObjectName("titleBarContainer")
        self.setFixedHeight(52)
        self._window = window
        self._drag_from: QPoint | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(10)

        mark = QLabel("S")
        mark.setObjectName("logoMark")
        mark.setFixedSize(28, 28)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark)

        names = QVBoxLayout()
        names.setSpacing(0)
        title = QLabel("SIENG3")
        title.setObjectName("appTitle")
        subtitle = QLabel(f"adaptive steganography  v{__version__}")
        subtitle.setObjectName("appSubtitle")
        names.addWidget(title)
        names.addWidget(subtitle)
        layout.addLayout(names)
        layout.addStretch(1)

        for text, slot, name in (
            ("—", window.showMinimized, "windowControlBtn"),
            ("□", self._toggle_maximised, "windowControlBtn"),
            ("✕", window.close, "windowCloseBtn"),
        ):
            button = QPushButton(text)
            button.setObjectName(name)
            button.setFixedSize(32, 28)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(slot)
            layout.addWidget(button)

    def _toggle_maximised(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    # ---- dragging, which a system title bar would have done for us ---------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_from = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_from is not None and not self._window.isMaximized():
            self._window.move(event.globalPosition().toPoint() - self._drag_from)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_from = None

    def mouseDoubleClickEvent(self, event) -> None:
        self._toggle_maximised()
