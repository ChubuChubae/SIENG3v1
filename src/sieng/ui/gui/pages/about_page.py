"""The About page: what is wired up, and what this build cannot do.

The limitations are read from `app.info`, which reads them from the modules that implement
them. A screen that described them in its own words would drift from the code, and the
drift is always in the direction of claiming more than is true.

This is also where the technical detail that was taken off the other screens ends up. It
is here in full, because a user who wants to know what the program is doing should be able
to find out without reading the source, and moving it here is not the same as removing it.
"""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox

from sieng.app.info import readiness, system_info
from sieng.ui.gui.components import recall
from sieng.ui.gui.components.widgets import Card, DetailTable, label, secondary_button
from sieng.ui.gui.naming import engine_name
from sieng.ui.gui.pages.base_page import BasePage


class AboutPage(BasePage):
    def __init__(self, container: Any) -> None:
        subtitle = "What this build contains, and what it cannot do yet."
        super().__init__(container, "About SIENG3", subtitle)
        info = system_info(container)

        privacy = Card("Where your files go")
        privacy.add(
            label(
                "Nowhere. Every image, file and key stays on this machine. SIENG3 has no "
                "server, makes no network connection, sends no telemetry, and has no "
                "auto-update. Nothing here phones home because there is no home to phone.",
                "noticeLabel",
            )
        )
        self.add(privacy)
        self.add(self._traces_card())

        engines = ", ".join(engine_name(name) for name in info["engines"]) or "none"
        build = Card("This build")
        build.add(
            DetailTable(
                [
                    ("Version", info["version"]),
                    ("Crypto suite", info["crypto_suite"]),
                    ("Methods", engines),
                    ("Cost models", ", ".join(info["cost_models"]) or "none"),
                    ("File types", ", ".join(info["carriers"]) or "none"),
                ]
            )
        )
        self.add(build)

        available, message = readiness(container)
        state = Card("Post-quantum status")
        state.add(label(message, "subLabel" if available else "noticeLabel"))
        self.add(state)

        limits = Card("What this version does not do")
        for text in info["limitations"]:
            if text:
                limits.add(label(f"·  {text}", "hintLabel"))
        self.add(limits)
        self.finish()

    def _traces_card(self) -> Card:
        """What the program leaves behind, and the switch that decides whether it does.

        A list of the last folders someone used is a list an examiner would want, so it is
        off unless asked for, and what it costs is written next to the switch rather than
        left for the user to reason out.
        """
        card = Card(
            "What is written to this machine",
            "Beside the files you choose yourself, SIENG3 writes the session file you "
            "create, and nothing else. There is no log and no cache of your images.",
        )
        self.remember = QCheckBox("Remember the last folders I used")
        self.remember.setObjectName("formCheck")
        self.remember.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remember.setChecked(recall.is_on())
        self.remember.toggled.connect(self._set_remember)
        card.add(self.remember)
        card.add(
            label(
                "Off by default. When on, the last session, image and output folders are "
                "kept in the system settings store, where anything running as you can "
                "read them.",
                "hintLabel",
            )
        )
        card.add(secondary_button("Forget remembered folders", self._forget))
        return card

    def _set_remember(self, on: bool) -> None:
        recall.set_on(on)
        self.say("Folders will be remembered" if on else "Folders will not be remembered", "good")

    def _forget(self) -> None:
        recall.forget_everything()
        self.say("Remembered folders cleared", "good")
