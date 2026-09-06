"""The Hide page: pick a cover, pick something to hide, and put one inside the other.

Two decisions here are about honesty rather than layout.

**The engine list comes from the registry, not from a list typed into this file.** An
engine that is registered appears; one that is not does not. A hardcoded list drifts, and
the way it drifts is by offering something that no longer works.

**The capacity line updates as the user types.** Finding out that a payload does not fit
after waiting through a cost map is a bad experience, but the real reason is different: a
user who does not see the number will reach for a higher rate until it fits, and rate is
the single thing detectors measure best. Showing the cost of the choice while it is being
made is the only point at which it can be influenced.
"""

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox

from sieng.common.errors import CapacityError, PipelineValidationError
from sieng.pipeline.context import Cancelled
from sieng.pipeline.embed import run_embed
from sieng.pipeline.engines.base import EmbedRequest
from sieng.ui.gui.components.widgets import (
    Card,
    FileDropZone,
    SavePicker,
    label,
    primary_button,
    secondary_button,
)
from sieng.ui.gui.pages.base_page import BasePage, password_field

IMAGE_FILTER = "Images (*.jpg *.jpeg *.jpe *.png);;All files (*)"
STATE_FILTER = "Session state (*.state);;All files (*)"


class EmbedPage(BasePage):
    def __init__(self, container: Any) -> None:
        super().__init__(container)

        files = Card("What to hide, and where")
        self.cover = FileDropZone("Drop the cover image here", IMAGE_FILTER)
        self.payload = FileDropZone("Drop the file to hide here")
        self.output = SavePicker("Choose where to save the result", IMAGE_FILTER)
        files.add(label("Cover image", "formLabel"))
        files.add(self.cover)
        files.add(label("File to hide", "formLabel"))
        files.add(self.payload)
        files.add(label("Save the result as", "formLabel"))
        files.add(self.output)
        self.add(files)

        settings = Card("Settings")
        self.engine = QComboBox()
        self.engine.setObjectName("formInput")
        for engine in container.engines.all():
            self.engine.addItem(engine.engine_id)

        self.rate = QDoubleSpinBox()
        self.rate.setObjectName("formInput")
        self.rate.setRange(0.01, 0.5)
        self.rate.setSingleStep(0.05)
        self.rate.setDecimals(2)
        self.rate.setValue(0.10)

        settings.add(label("Engine", "formLabel"))
        settings.add(self.engine)
        settings.add(label("Payload rate (bpnzAC)", "formLabel"))
        settings.add(self.rate)
        self.capacity = label("", "capacityLabel")
        settings.add(self.capacity)
        settings.add(
            label(
                "A higher rate fits more, and is easier for a detector to notice. "
                "Published work reports 0.05 to 0.4.",
                "hintLabel",
            )
        )
        self.add(settings)

        session = Card("Session")
        self.state = FileDropZone("Drop the session state file here", STATE_FILTER)
        self.password = password_field()
        session.add(self.state)
        session.add(label("Session password", "formLabel"))
        session.add(self.password)
        self.add(session)

        self.run_button = primary_button("Hide it", self._start)
        self.stop_button = secondary_button("Stop", self.cancel_job)
        actions = Card()
        actions.add_row(self.run_button, self.stop_button)
        self.add(actions)
        self.finish()

        for source in (self.cover, self.payload):
            source.chosen.connect(lambda _path: self._update_capacity())
        self.rate.valueChanged.connect(lambda _value: self._update_capacity())
        self._update_capacity()

    # ---- the live capacity line -------------------------------------------

    def _update_capacity(self) -> None:
        """Say how much would fit, and colour it when the answer is no.

        Deliberately opens the cover to ask it, rather than estimating from the file size:
        the number that matters is the non-zero AC count, and nothing else predicts it.
        """
        cover, payload = self.cover.path, self.payload.path
        if cover is None:
            self._set_capacity("", "ok")
            return
        try:
            available = self._available_bytes(cover)
        except Exception:
            # Broad on purpose. This runs on every keystroke against a file the user is
            # still choosing, so anything unreadable is a state to display rather than an
            # error to raise. The real attempt reports properly.
            self._set_capacity("This file cannot be read as a cover", "danger")
            return

        if payload is None:
            self._set_capacity(f"About {available:,} bytes would fit at this rate", "ok")
            return

        needed = payload.stat().st_size
        if needed > available:
            self._set_capacity(
                f"{needed:,} bytes will not fit: about {available:,} available at this rate",
                "danger",
            )
        elif needed > available * 0.9:
            self._set_capacity(f"{needed:,} of about {available:,} bytes", "warning")
        else:
            self._set_capacity(f"{needed:,} of about {available:,} bytes", "ok")

    def _available_bytes(self, cover: Path) -> int:
        from sieng.carrier.detect import open_carrier
        from sieng.domain.capacity import max_payload_bits

        carrier = open_carrier(cover, self.container.carriers)
        at_rate = int(carrier.capacity_base() * self.rate.value())
        ceiling = max_payload_bits(carrier.capacity_base())
        return max(min(at_rate, ceiling) // 8 - 16, 0)

    def _set_capacity(self, text: str, state: str) -> None:
        self.capacity.setText(text)
        self.capacity.setProperty("capacityState", state)
        style = self.capacity.style()
        if style is not None:
            style.unpolish(self.capacity)
            style.polish(self.capacity)

    # ---- doing it ----------------------------------------------------------

    def _start(self) -> None:
        missing = self._what_is_missing()
        if missing:
            self.say(missing)
            return

        request = EmbedRequest(
            cover=self.cover.path,
            destination=self.output.path,
            payload=self.payload.path.read_bytes(),
            state_path=self.state.path,
            password=self.password.text().encode(),
            payload_rate=self.rate.value(),
        )
        engine_id = self.engine.currentText()

        self.run_job(
            lambda context: run_embed(
                request,
                engine_id,
                self.container.carriers,
                self.container.engines,
                context,
            ),
            self._succeeded,
            self._failed,
            busy_widgets=[self.run_button],
        )

    def _what_is_missing(self) -> str:
        for value, message in (
            (self.cover.path, "Choose a cover image"),
            (self.payload.path, "Choose a file to hide"),
            (self.output.path, "Choose where to save the result"),
            (self.state.path, "Choose the session state file"),
            (self.password.text(), "Enter the session password"),
        ):
            if not value:
                return message
        if self.output.path == self.cover.path:
            return "The result cannot overwrite the cover"
        return ""

    def _succeeded(self, result: Any) -> None:
        self.password.clear()
        self.say(result.summary())

    def _failed(self, error: BaseException) -> None:
        self.password.clear()
        if isinstance(error, Cancelled):
            self.say("Stopped. Nothing was written, but a message counter was used.")
        elif isinstance(error, CapacityError):
            self.say(f"{error} Lower the rate, or choose a larger cover.")
        elif isinstance(error, PipelineValidationError):
            self.say(str(error))
        else:
            self.say(f"Could not hide the file: {error}")
