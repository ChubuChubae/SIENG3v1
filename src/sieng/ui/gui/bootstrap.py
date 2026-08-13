"""Starts the GUI: build the QApplication, apply the theme, open the main window.

No business logic here. The ui always goes through pipeline or analyzer
(PROJECT_CONTEXT.md 2.1).
"""

from pathlib import Path

STYLE_DIR = Path(__file__).parent / "styles"
DEFAULT_STYLE = "default.qss"
DEFAULT_FONT = ("Segoe UI", 10)


class GuiUnavailableError(RuntimeError):
    """PyQt6 is missing. The message must say how to fix it, not just that it broke."""


def load_stylesheet(name: str = DEFAULT_STYLE):
    """Return the theme, or an empty string. A missing theme should not block startup."""
    path = STYLE_DIR / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def run(container):
    """Open the GUI and return an exit code.

    PyQt6 is imported here so this module still imports without the [gui] extra,
    which keeps non-GUI tests from failing on a missing dependency.
    """
    try:
        from PyQt6.QtGui import QFont
        from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError as error:
        raise GuiUnavailableError(
            'PyQt6 is not installed. Run: pip install -e ".[gui]" '
            "(or use the CLI instead: sieng --status)"
        ) from error

    app = QApplication([])
    app.setFont(QFont(*DEFAULT_FONT))

    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Phase 9.1 replaces this with sieng.ui.gui.main_window.MainWindow
    window = QMainWindow()
    window.setWindowTitle("SIENG3")
    window.resize(900, 600)
    window.setCentralWidget(
        QLabel(
            "SIENG3 - structure is in place, no screens yet\n\n"
            f"{container.summary()}\n\n"
            "The real window arrives in Phase 9.1 (docs/PROJECT_CONTEXT.md)"
        )
    )
    window.show()

    return app.exec()
