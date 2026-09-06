"""The Recover page. Deliberately the least informative screen in the program.

Every other page tries to tell the user what went wrong. This one must not. A message that
distinguishes "nothing hidden here" from "wrong session" from "the file was altered" turns
the window into a tool for testing whether a file is a stego file, and that is the exact
capability the whole project is built to deny.

So there is one failure message. It lists the possibilities, because that helps the person
who owns the file, and it refuses to say which one, because that is the only part an
examiner could use. `run_extract` already collapses the causes; this page must not undo
that by inspecting the exception it gets back.

The one exception is a replayed counter, which is a fact about our own session that the
receiver already knows. Hiding it would leave a user unable to understand why a file they
read yesterday will not read today.
"""

from typing import Any

from sieng.common.errors import PipelineValidationError, ReplayError
from sieng.pipeline.context import Cancelled
from sieng.pipeline.engines.base import ExtractRequest
from sieng.pipeline.extract import run_extract
from sieng.ui.gui.components.widgets import (
    Card,
    FileDropZone,
    SavePicker,
    label,
    primary_button,
)
from sieng.ui.gui.pages.base_page import BasePage, password_field

IMAGE_FILTER = "Images (*.jpg *.jpeg *.jpe *.png);;All files (*)"
STATE_FILTER = "Session state (*.state);;All files (*)"

# One message, every reason. Changing this to say more is the change that breaks the
# property, so it lives here as a constant with its reason attached.
CANNOT_READ = (
    "Nothing could be recovered from this file. It may hold nothing, it may belong to a "
    "different session, the password may be wrong, or it may have been altered. "
    "SIENG3 cannot tell you which, on purpose."
)


class ExtractPage(BasePage):
    def __init__(self, container: Any) -> None:
        super().__init__(container)

        files = Card("What to read")
        self.stego = FileDropZone("Drop the image here", IMAGE_FILTER)
        self.output = SavePicker("Choose where to save what comes out")
        files.add(self.stego)
        files.add(label("Save the recovered file as", "formLabel"))
        files.add(self.output)
        self.add(files)

        session = Card("Session")
        self.state = FileDropZone("Drop the session state file here", STATE_FILTER)
        self.password = password_field()
        session.add(self.state)
        session.add(label("Session password", "formLabel"))
        session.add(self.password)
        session.add(
            label(
                "Only the session this file was made for can read it. Without the state "
                "file and its password there is nothing to try.",
                "hintLabel",
            )
        )
        self.add(session)

        self.run_button = primary_button("Read it", self._start)
        actions = Card()
        actions.add_row(self.run_button)
        self.add(actions)
        self.finish()

    def _start(self) -> None:
        for value, message in (
            (self.stego.path, "Choose the image to read"),
            (self.output.path, "Choose where to save what comes out"),
            (self.state.path, "Choose the session state file"),
            (self.password.text(), "Enter the session password"),
        ):
            if not value:
                self.say(message)
                return

        request = ExtractRequest(
            stego=self.stego.path,
            state_path=self.state.path,
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
        self.say(f"{len(result.payload):,} bytes written to {self.output.path.name}")

    def _failed(self, error: BaseException) -> None:
        """One message for anything about the file. Two exceptions, both about us."""
        self.password.clear()
        if isinstance(error, Cancelled):
            self.say("Stopped")
        elif isinstance(error, ReplayError):
            self.say(
                "This message has already been read once in this session. A message can "
                "only be read the first time it arrives."
            )
        elif isinstance(error, PipelineValidationError):
            self.say(str(error))
        else:
            self.say(CANNOT_READ)
