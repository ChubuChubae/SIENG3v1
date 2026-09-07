"""The Hide page: pick a cover, pick something to hide, and put one inside the other.

Five decisions here are about honesty rather than layout.

**The method list is filtered by what the cover actually is.** The registry knows which
domain each engine works in and `sniff` knows what the file really is, by its bytes and
never by its name. A PNG offered a JPEG-domain method is a promise the program cannot keep,
and letting the user find that out after they have typed a password is the worst possible
moment to tell them.

**The capacity meter is a percentage, not a byte count.** Bytes are the number the program
knows; how full the image ends up is the number that decides whether anyone can tell. Past
seventy percent it says so in words, because a user who does not see the cost will raise
the rate until the file fits, and rate is the single thing detectors measure best.

**The rate presets are honest about what they cost.** "High" is offered because a user who
needs the space will find it anyway, and offering it with the consequence written next to
it is better than making them discover the number by fighting the meter.

**The session is not on this page.** It is one bar at the top of the window, because a
session is what the program is working in rather than a setting belonging to this
operation. What stays here is the password, which is typed for one run and cleared after.

**The suggested output name is the cover's own name, in a different folder.** A name like
"photo-hidden.jpg" is a confession, and two near-identical images side by side in one
folder are evidence on their own even if neither can be shown to hold anything.
"""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QLocale
from PyQt6.QtWidgets import QComboBox, QDoubleSpinBox

from sieng.common.errors import CapacityError, PipelineValidationError
from sieng.pipeline.context import Cancelled
from sieng.pipeline.embed import run_embed
from sieng.pipeline.engines.base import EmbedRequest
from sieng.ui.gui.components import recall
from sieng.ui.gui.components.session_bar import SessionSelection
from sieng.ui.gui.components.widgets import (
    CapacityMeter,
    Card,
    DetailTable,
    Disclosure,
    FileDropZone,
    SavePicker,
    Segmented,
    label,
    link_button,
    primary_button,
    secondary_button,
    show_in_folder,
)
from sieng.ui.gui.naming import ENGINE_DETAILS, ENGINE_NOTES, engine_name
from sieng.ui.gui.pages.base_page import BasePage, password_field

IMAGE_FILTER = "Images (*.jpg *.jpeg *.jpe *.png);;All files (*)"

# The three presets and the rate each one means, in bpnzAC. Shown with their numbers, so
# a preset is a shortcut to a value rather than a name for something hidden.
PRESETS = {"low": 0.05, "balanced": 0.10, "high": 0.40}

PRESET_NOTES = {
    "low": "Least to notice, least room. Good for short files.",
    "balanced": "Recommended for most files.",
    "high": "More room, and the easiest of the three for a detector to spot.",
}


class EmbedPage(BasePage):
    def __init__(self, container: Any, session: SessionSelection) -> None:
        super().__init__(
            container,
            "Hide a File",
            "Put a file inside an image, so that only the other side can take it out.",
        )
        self.session = session

        files = Card("Files")
        self.cover = FileDropZone(
            "Drop the cover image here",
            IMAGE_FILTER,
            recall.recall_dir(recall.LAST_COVER_DIR),
            "JPEG or PNG",
            "photo",
        )
        self.payload = FileDropZone(
            "Drop the file you want to hide here",
            hint="Any file, encrypted before it goes in",
            icon_name="file-plus",
        )
        files.field("Cover image", self.cover, "Your image is not changed. A copy is written.")
        files.field("File to hide", self.payload)
        self.add(files)

        self.add(self._protection_card())
        self.add(self._output_card())
        self.finish()

        for source in (self.cover, self.payload, self.output):
            source.chosen.connect(lambda _path: self._refresh())
        self.cover.chosen.connect(self._cover_chosen)
        self.rate.valueChanged.connect(self._rate_typed)
        self.password.textChanged.connect(lambda _text: self._refresh())
        self.session.changed.connect(lambda _path: self._refresh())
        self._refresh()

    # ---- the cards ---------------------------------------------------------

    def _protection_card(self) -> Card:
        card = Card("Protection")

        self.engine = QComboBox()
        self.engine.setObjectName("formInput")
        self.engine_note = label("", "hintLabel")
        card.field("Method", self.engine)
        card.add(self.engine_note)
        self.engine.currentIndexChanged.connect(lambda _index: self._engine_changed())

        options = [(key, f"{key.capitalize()}  ·  {rate:.2f}") for key, rate in PRESETS.items()]
        self.preset = Segmented(options)
        self.preset.changed.connect(self._preset_picked)
        card.field("How much to hide", self.preset)
        self.preset_note = label("", "hintLabel")
        card.add(self.preset_note)

        self.meter = CapacityMeter()
        card.add(self.meter)

        self.password = password_field()
        self.password.returnPressed.connect(self._start)
        card.field(
            "Session password",
            self.password,
            "The password for the session file loaded at the top of the window.",
        )

        # The exact number, for anyone who wants it. The presets write into this field, so
        # there is one value and not two that can disagree.
        self.rate = QDoubleSpinBox()
        self.rate.setObjectName("formInput")
        # English locale on purpose. Under a Thai or other non-Latin system locale Qt draws
        # the number in that locale's own digits, which is where "0.ð..." came from.
        self.rate.setLocale(QLocale("en_US"))
        self.rate.setRange(0.01, 0.5)
        self.rate.setSingleStep(0.01)
        self.rate.setDecimals(2)
        self.rate.setSuffix(" bpnzAC")
        self.rate.setMinimumWidth(170)
        self.rate.setValue(PRESETS["balanced"])

        self.advanced = Disclosure("Advanced")
        self.advanced.field(
            "Payload rate",
            self.rate,
            "Bits per non-zero AC coefficient. The presets above are three points on this.",
        )
        self.detail_table = DetailTable([])
        self.advanced.add(self.detail_table)
        card.add(self.advanced)

        self._fill_methods(None)
        self.preset.select("balanced")
        self._describe_preset("balanced")
        return card

    def _output_card(self) -> Card:
        card = Card("Output")
        self.output = SavePicker(
            "Not chosen yet", IMAGE_FILTER, recall.recall_dir(recall.LAST_OUTPUT_DIR)
        )
        card.field(
            "Save the result as",
            self.output,
            "Somewhere other than the cover's own folder: two near-identical images in one "
            "place is a pattern on its own.",
        )

        self.missing = label("", "missingLabel")
        card.add(self.missing)

        self.run_button = primary_button("Hide File", self._start)
        self.stop_button = secondary_button("Stop", self.cancel_job)
        self.stop_button.hide()
        card.add_row(self.run_button, self.stop_button)

        self.reveal_button = link_button("Open the folder it was saved in", self._show_result)
        self.reveal_button.hide()
        card.add(self.reveal_button)
        return card

    # ---- what the cover changes --------------------------------------------

    def _cover_chosen(self, cover: Path | None) -> None:
        self._fill_methods(cover)
        self._suggest_output_name(cover)

    def _fill_methods(self, cover: Path | None) -> None:
        """Only methods that can work on this file, and a reason when none can.

        The domain comes from the carrier that claims the file's actual bytes, so renaming
        a PNG to .jpg does not put a JPEG method back on the list.
        """
        self.engine.clear()
        usable = self._usable_engines(cover)
        for engine in usable:
            self.engine.addItem(engine_name(engine.engine_id), engine.engine_id)
        self.engine.setEnabled(bool(usable))
        if usable:
            self._engine_changed()
        elif cover is None:
            self.engine_note.setText("Choose a cover image and the methods for it appear here.")
        else:
            self.engine_note.setText(
                f"No method in this build works on a {cover.suffix.upper().lstrip('.')} "
                "file. The methods here embed in JPEG coefficients; the spatial-domain "
                "ones are not finished yet."
            )

    def _usable_engines(self, cover: Path | None) -> list[Any]:
        if cover is None:
            return list(self.container.engines.all())
        try:
            from sieng.carrier.detect import sniff

            domain = sniff(cover, self.container.carriers).domain
        except Exception:
            # Broad on purpose: an unreadable or unknown file is a state to show, not an
            # error to raise, and the capacity line says the same thing a moment later.
            return []
        return list(self.container.engines.for_domain(domain))

    def _engine_changed(self) -> None:
        engine_id = self.engine.currentData()
        self.engine_note.setText(ENGINE_NOTES.get(engine_id, ""))
        rows = ENGINE_DETAILS.get(engine_id, [("Engine id", str(engine_id))])
        self.detail_table.setParent(None)
        self.detail_table = DetailTable(rows)
        self.advanced.add(self.detail_table)

    def _suggest_output_name(self, cover: Path | None) -> None:
        """The cover's own name. A "-hidden" suffix would say out loud what this is."""
        if cover is not None and self.output.path is None:
            self.output.suggest(cover.name)

    # ---- the rate ----------------------------------------------------------

    def _preset_picked(self, key: str) -> None:
        self.rate.setValue(PRESETS[key])
        self._describe_preset(key)

    def _rate_typed(self, value: float) -> None:
        """A rate typed by hand deselects the presets rather than pretending to be one."""
        match = [key for key, rate in PRESETS.items() if abs(rate - value) < 1e-9]
        if match:
            self.preset.select(match[0])
            self._describe_preset(match[0])
        else:
            self.preset.clear_selection()
            self.preset_note.setText(f"Custom · {value:.2f} bpnzAC")
        self._refresh()

    def _describe_preset(self, key: str) -> None:
        self.preset_note.setText(f"{PRESETS[key]:.2f} bpnzAC · {PRESET_NOTES[key]}")

    # ---- keeping the page honest about itself ------------------------------

    def _refresh(self) -> None:
        """The meter and the button, together: both answer 'can I press this yet'."""
        self._update_capacity()
        missing = self._what_is_missing()
        self.run_button.setEnabled(not missing)
        self.missing.setText(missing)
        self.missing.setVisible(bool(missing))

    def _what_is_missing(self) -> str:
        for value, message in (
            (self.cover.path, "Still needed: a cover image"),
            (self.engine.currentData(), "Still needed: a method that works on this image"),
            (self.payload.path, "Still needed: the file to hide"),
            (self.session.path, "Still needed: a session, loaded at the top of the window"),
            (self.password.text(), "Still needed: the session password"),
            (self.output.path, "Still needed: where to save the result"),
        ):
            if not value:
                return message
        if self.output.path == self.cover.path:
            return "The result cannot overwrite the cover image"
        return ""

    def _update_capacity(self) -> None:
        """Say how full the cover would be, live.

        Deliberately opens the cover to ask it, rather than estimating from the file size:
        the number that matters is the non-zero AC count, and nothing else predicts it.
        """
        cover, payload = self.cover.path, self.payload.path
        if cover is None:
            self.meter.show_unknown("Choose a cover image to see how much it holds")
            return
        try:
            available = self._available_bytes(cover)
        except Exception:
            # Broad on purpose. This runs on every keystroke against a file the user is
            # still choosing, so anything unreadable is a state to display rather than an
            # error to raise. The real attempt reports properly.
            self.meter.show_unknown("This file cannot be used as a cover")
            return

        if payload is None:
            self.meter.show_capacity_only(available)
        else:
            self.meter.show_fill(payload.stat().st_size, available)

    def _available_bytes(self, cover: Path) -> int:
        from sieng.carrier.detect import open_carrier
        from sieng.domain.capacity import max_payload_bits

        carrier = open_carrier(cover, self.container.carriers)
        at_rate = int(carrier.capacity_base() * self.rate.value())
        ceiling = max_payload_bits(carrier.capacity_base())
        return max(min(at_rate, ceiling) // 8 - 16, 0)

    def job_state_changed(self, running: bool) -> None:
        self.stop_button.setVisible(running)
        if running:
            self.reveal_button.hide()

    def _show_result(self) -> None:
        if self.output.path is not None:
            show_in_folder(self.output.path)

    # ---- doing it ----------------------------------------------------------

    def _start(self) -> None:
        missing = self._what_is_missing()
        if missing:
            self.say(missing, "bad")
            return
        self.reveal_button.hide()

        request = EmbedRequest(
            cover=self.cover.path,
            destination=self.output.path,
            payload=self.payload.path.read_bytes(),
            state_path=self.session.path,
            password=self.password.text().encode(),
            payload_rate=self.rate.value(),
        )
        engine_id = self.engine.currentData()

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

    def _succeeded(self, result: Any) -> None:
        self.password.clear()
        self._remember()
        self.reveal_button.show()
        self.say(
            f"Saved as {self.output.path.name}. Send this image only; the session file and "
            f"its password must never travel the same way. {result.summary()}",
            "good",
        )

    def _remember(self) -> None:
        """Only after a run that worked, only paths, and only if the user asked for it."""
        if self.output.path is not None:
            recall.remember(recall.LAST_OUTPUT_DIR, self.output.path.parent)
        if self.cover.path is not None:
            recall.remember(recall.LAST_COVER_DIR, self.cover.path.parent)

    def _failed(self, error: BaseException) -> None:
        self.password.clear()
        if isinstance(error, Cancelled):
            self.say("Stopped. Nothing was written, but a message counter was used.", "bad")
        elif isinstance(error, CapacityError):
            self.say(f"{error} Lower the rate, or choose a larger image.", "bad")
        elif isinstance(error, PipelineValidationError):
            self.say(str(error), "bad")
        else:
            self.say(f"Could not hide the file: {error}", "bad")
