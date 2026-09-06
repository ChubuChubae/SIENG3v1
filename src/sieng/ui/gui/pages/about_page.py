"""The About page: what is wired up, and what this build cannot do.

The limitations are read from `app.info`, which reads them from the modules that implement
them. A screen that described them in its own words would drift from the code, and the
drift is always in the direction of claiming more than is true.
"""

from typing import Any

from sieng.app.info import readiness, system_info
from sieng.ui.gui.components.widgets import Card, label
from sieng.ui.gui.pages.base_page import BasePage


class AboutPage(BasePage):
    def __init__(self, container: Any) -> None:
        super().__init__(container)
        info = system_info(container)

        build = Card("This build")
        for name, value in (
            ("Version", info["version"]),
            ("Crypto suite", info["crypto_suite"]),
            ("Engines", ", ".join(info["engines"]) or "none"),
            ("Cost models", ", ".join(info["cost_models"]) or "none"),
            ("File types", ", ".join(info["carriers"]) or "none"),
        ):
            build.add(label(f"{name}: {value}", "subLabel"))
        self.add(build)

        available, message = readiness(container)
        state = Card("Post-quantum status")
        state.add(label(message, "subLabel" if available else "statusLabel"))
        self.add(state)

        limits = Card("What this version does not do")
        for text in info["limitations"]:
            if text:
                limits.add(label(text, "hintLabel"))
        self.add(limits)
        self.finish()
