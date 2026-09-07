"""The Read page. Deliberately the least informative screen in the program.

Every other page tries to tell the user what went wrong. This one must not. A message that
distinguishes "nothing hidden here" from "wrong session" from "the file was altered" turns
the window into a tool for testing whether a file is a stego file, and that is the exact
capability the whole project is built to deny.

So there is one failure message. It lists the possibilities, because that helps the person
who owns the file, and it refuses to say which one, because that is the only part an
examiner could use. `run_extract` already collapses the causes; this page must not undo
that by inspecting the exception it gets back, and nothing else on the page may report a
narrower reason either.

The one exception is a replayed counter, which is a fact about our own session that the
receiver already knows. Hiding it would leave a user unable to understand why a file they
read yesterday will not read today.
"""

from typing import Any

from sieng.common.errors import PipelineValidationError, ReplayError
from sieng.pipeline.context import Cancelled
from sieng.pipeline.engines.base import ExtractRequest
from sieng.pipeline.extract import run_extract
from sieng.ui.gui.components import recall
from sieng.ui.gui.components.session_bar import SessionSelection
from sieng.ui.gui.components.widgets import (
    Card,
    FileDropZone,
    SavePicker,
    label,
    link_button,
    primary_button,
    secondary_button,
    show_in_folder,
)
from sieng.ui.gui.pages.base_page import BasePage, password_field

IMAGE_FILTER = "Images (*.jpg *.jpeg *.jpe *.png);;All files (*)"

# One message, every reason. Changing this to say more is the change that breaks the
# property, so it lives here as a constant with its reason attached.
CANNOT_READ = (
    "Nothing could be recovered from this file. It may hold nothing, it may belong to a "
    "different session, the password may be wrong, or it may have been altered. "
    "SIENG3 cannot tell you which, on purpose."
)


class ExtractPage(BasePage):
    def __init__(self, container: Any, session: SessionSelection) -> None:
        super().__init__(
            container,
            "Read a File",
            "Take a hidden file back out of an image someone sent you.",
        )
        self.session = session

        files = Card("Files")
        self.stego = FileDropZone(
            "Drop the image you were sent here",
            IMAGE_FILTER,
            recall.recall_dir(recall.LAST_COVER_DIR),
            "JPEG or PNG",
            "photo",
        )
        self.output = SavePicker("Not chosen yet", "", recall.recall_dir(recall.LAST_OUTPUT_DIR))
        files.field("Image", self.stego)
        files.field("Save what comes out as", self.output)
        self.add(files)

        session_card = Card("Session")
        session_card.add(
            label(
                "Only the session this file was made for can read it. The session loaded "
                "at the top of the window is the one that will be tried.",
                "noticeLabel",
            )
        )
        self.password = password_field()
        self.password.returnPressed.connect(self._start)
        session_card.field("Session password", self.password)
        self.add(session_card)

        actions = Card()
        self.missing = label("", "missingLabel")
        actions.add(self.missing)
        self.run_button = primary_button("Read File", self._start)
        self.stop_button = secondary_button("Stop", self.cancel_job)
        self.stop_button.hide()
        actions.add_row(self.run_button, self.stop_button)
        self.reveal_button = link_button("Open the folder it was saved in", self._show_result)
        self.reveal_button.hide()
        actions.add(self.reveal_button)
        self.add(actions)
        self.finish()

        for source in (self.stego, self.output):
            source.chosen.connect(lambda _path: self._refresh())
        self.password.textChanged.connect(lambda _text: self._refresh())
        self.session.changed.connect(lambda _path: self._refresh())
        self._refresh()

    # ---- the state of the page ---------------------------------------------

    def _refresh(self) -> None:
        missing = self._what_is_missing()
        self.run_button.setEnabled(not missing)
        self.missing.setText(missing)
        self.missing.setVisible(bool(missing))

    def _what_is_missing(self) -> str:
        for value, message in (
            (self.stego.path, "Still needed: the image to read"),
            (self.session.path, "Still needed: a session, loaded at the top of the window"),
            (self.password.text(), "Still needed: the session password"),
            (self.output.path, "Still needed: where to save what comes out"),
        ):
            if not value:
                return message
        return ""

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

        request = ExtractRequest(
            stego=self.stego.path,
            state_path=self.session.path,
            password=self.password.text().encode(),
        )
        engine_id = self.container.engines.ids()[0]

        self.run_job(
            lambda context: run_extract(
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
        self.output.path.write_bytes(result.payload)
        recall.remember(recall.LAST_OUTPUT_DIR, self.output.path.parent)
        recall.remember(recall.LAST_COVER_DIR, self.stego.path.parent)
        self.reveal_button.show()
        self.say(f"{len(result.payload):,} bytes written to {self.output.path.name}", "good")

    def _failed(self, error: BaseException) -> None:
        """One message for anything about the file. Two exceptions, both about us."""
        self.password.clear()
        if isinstance(error, Cancelled):
            self.say("Stopped", "bad")
        elif isinstance(error, ReplayError):
            self.say(
                "This message has already been read once in this session. A message can "
                "only be read the first time it arrives.",
                "bad",
            )
        elif isinstance(error, PipelineValidationError):
            self.say(str(error), "bad")
        else:
            self.say(CANNOT_READ, "bad")
