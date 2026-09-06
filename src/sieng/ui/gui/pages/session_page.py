"""The Sessions page: start a session, or join one somebody else started.

This screen is where the program is most obviously unfinished, and it says so rather than
hiding it. Creating a session produces a 32 byte secret that both sides need, and this
version has no way to deliver it: the full handshake exists in `crypto/kem` and
`crypto/auth`, but nothing has a screen yet. So the secret is shown, with a plain statement
that the user has to carry it themselves and that doing so badly undoes the rest.

Showing a secret on screen is a real weakness and it is presented as one. The alternative
considered was hiding it behind a "copy" button, which would have made it feel safer
without being safer.
"""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit

from sieng.common.errors import CryptoError
from sieng.pipeline.session import create_session, join_session
from sieng.ui.gui.components.widgets import (
    Card,
    SavePicker,
    label,
    primary_button,
    secondary_button,
)
from sieng.ui.gui.pages.base_page import BasePage, password_field

STATE_FILTER = "Session state (*.state);;All files (*)"


class SessionPage(BasePage):
    def __init__(self, container: Any) -> None:
        super().__init__(container)

        start = Card("Start a new session")
        self.new_path = SavePicker("Choose where to keep the session state", STATE_FILTER)
        self.new_password = password_field("Choose a password for this session")
        self.new_confirm = password_field("Type it again")
        start.add(self.new_path)
        start.add(label("Password", "formLabel"))
        start.add(self.new_password)
        start.add(self.new_confirm)
        start.add(
            label(
                "The password protects the session file on this machine. It is not the "
                "secret the other side needs.",
                "hintLabel",
            )
        )
        start.add(primary_button("Create session", self._create))
        self.secret_box = QPlainTextEdit()
        self.secret_box.setObjectName("payloadTextArea")
        self.secret_box.setReadOnly(True)
        self.secret_box.setFixedHeight(96)
        self.secret_box.hide()
        start.add(self.secret_box)
        self.add(start)

        join = Card("Join a session someone sent you")
        self.join_path = SavePicker("Choose where to keep the session state", STATE_FILTER)
        self.join_id = _field("Session id, 8 hex characters")
        self.join_secret = _field("Shared secret, 64 hex characters")
        self.join_password = password_field("Choose a password for this machine")
        join.add(self.join_path)
        join.add(label("Session id", "formLabel"))
        join.add(self.join_id)
        join.add(label("Shared secret", "formLabel"))
        join.add(self.join_secret)
        join.add(label("Password", "formLabel"))
        join.add(self.join_password)
        join.add(secondary_button("Join session", self._join))
        self.add(join)

        warning = Card("What this screen cannot do yet")
        warning.add(
            label(
                "The secret below has to reach the other side over a channel you trust, "
                "and this program does not provide one. Sending it through the same place "
                "you will send the images undoes everything the encryption is for. "
                "Compare it in person, or over a call where you recognise the voice.",
                "hintLabel",
            )
        )
        self.add(warning)
        self.finish()

    # ---- creating ----------------------------------------------------------

    def _create(self) -> None:
        if not self.new_path.path:
            self.say("Choose where to keep the session state")
            return
        if self.new_password.text() != self.new_confirm.text():
            self.say("The two passwords do not match")
            return
        if not self.new_password.text():
            self.say("An empty password protects nothing")
            return

        try:
            session_id, secret = create_session(
                self.new_path.path, self.new_password.text().encode()
            )
        except (CryptoError, OSError) as error:
            self.say(str(error))
            return

        self.new_password.clear()
        self.new_confirm.clear()
        self.secret_box.setPlainText(
            f"session id     {session_id.hex()}\nshared secret  {secret.hex()}"
        )
        self.secret_box.show()
        self.say("Session created. Carry the two values below to the other side yourself.")

    # ---- joining -----------------------------------------------------------

    def _join(self) -> None:
        if not self.join_path.path:
            self.say("Choose where to keep the session state")
            return
        try:
            session_id = bytes.fromhex(self.join_id.text().strip())
            secret = bytes.fromhex(self.join_secret.text().strip())
        except ValueError:
            self.say("The session id and secret must be hex, exactly as they were shown")
            return
        if len(session_id) != 4 or len(secret) != 32:
            self.say("A session id is 8 hex characters and a secret is 64")
            return
        if not self.join_password.text():
            self.say("An empty password protects nothing")
            return

        try:
            join_session(
                self.join_path.path, session_id, secret, self.join_password.text().encode()
            )
        except (CryptoError, OSError) as error:
            self.say(str(error))
            return

        self.join_password.clear()
        self.join_secret.clear()
        self.say("Joined. This machine can now read messages sent in that session.")


def _field(placeholder: str) -> QLineEdit:
    box = QLineEdit()
    box.setObjectName("formInput")
    box.setPlaceholderText(placeholder)
    box.setAlignment(Qt.AlignmentFlag.AlignLeft)
    return box
