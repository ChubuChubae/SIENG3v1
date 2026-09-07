"""The Sessions page: start a session, or join one somebody else started.

A session is the thing both sides share, and every hidden file depends on one, so this
page is where a first-time user has to start. It says that at the top rather than leaving
them to work it out from the other screens.

This is also where the program is most obviously unfinished, and it says so rather than
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
from sieng.ui.gui.components.session_bar import SessionSelection
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
    def __init__(self, container: Any, session: SessionSelection) -> None:
        super().__init__(
            container,
            "Sessions",
            "A session is what the two sides share. Everything else depends on having one.",
        )
        self.session = session

        start = Card(
            "Start a session",
            "Do this once. Every file you hide afterwards uses the session file it creates.",
        )
        self.new_path = SavePicker("Not chosen yet", STATE_FILTER)
        self.new_path.suggest("sieng.state")
        self.new_password = password_field("A password for this session")
        self.new_confirm = password_field("Type it again")
        self.new_confirm.returnPressed.connect(self._create)
        start.field("Where to keep the session file", self.new_path)
        start.field(
            "Password",
            self.new_password,
            "This protects the session file on this machine. It is not the secret the "
            "other side needs.",
        )
        start.add(self.new_confirm)
        start.add(primary_button("Create session", self._create))

        self.secret_box = QPlainTextEdit()
        self.secret_box.setObjectName("payloadTextArea")
        self.secret_box.setReadOnly(True)
        self.secret_box.setFixedHeight(80)
        self.secret_box.hide()
        self.secret_note = label(
            "Read these two values to the other side over a channel you trust: in person, "
            "or a call where you recognise the voice. Sending them the same way you send "
            "the images undoes everything the encryption is for.",
            "noticeLabel",
        )
        self.secret_note.hide()
        start.add(self.secret_box)
        start.add(self.secret_note)
        self.add(start)

        join = Card(
            "Or join one someone sent you",
            "Use the two values the other side read out to you, not ones that arrived "
            "alongside the images.",
        )
        self.join_path = SavePicker("Not chosen yet", STATE_FILTER)
        self.join_path.suggest("sieng.state")
        self.join_id = _field("8 hex characters")
        self.join_secret = _field("64 hex characters")
        self.join_password = password_field("A password for this machine")
        self.join_password.returnPressed.connect(self._join)
        join.field("Where to keep the session file", self.join_path)
        join.field("Session id", self.join_id)
        join.field("Shared secret", self.join_secret)
        join.field("Password", self.join_password)
        join.add(secondary_button("Join session", self._join))
        self.add(join)
        self.finish()

    # ---- creating ----------------------------------------------------------

    def _create(self) -> None:
        if not self.new_path.path:
            self.say("Choose where to keep the session file", "bad")
            return
        if not self.new_password.text():
            self.say("An empty password protects nothing", "bad")
            return
        if self.new_password.text() != self.new_confirm.text():
            self.say("The two passwords do not match", "bad")
            return

        try:
            session_id, secret = create_session(
                self.new_path.path, self.new_password.text().encode()
            )
        except (CryptoError, OSError) as error:
            self.say(str(error), "bad")
            return

        self.session.set_path(self.new_path.path)
        self.new_password.clear()
        self.new_confirm.clear()
        self.secret_box.setPlainText(
            f"session id     {session_id.hex()}\nshared secret  {secret.hex()}"
        )
        self.secret_box.show()
        self.secret_note.show()
        self.say(
            "Session created and loaded. Carry the two values below to the other side "
            "yourself, and never send the session file the same way as the images.",
            "good",
        )

    # ---- joining -----------------------------------------------------------

    def _join(self) -> None:
        if not self.join_path.path:
            self.say("Choose where to keep the session file", "bad")
            return
        try:
            session_id = bytes.fromhex(self.join_id.text().strip())
            secret = bytes.fromhex(self.join_secret.text().strip())
        except ValueError:
            self.say("The session id and secret must be hex, exactly as they were read out", "bad")
            return
        if len(session_id) != 4 or len(secret) != 32:
            self.say("A session id is 8 hex characters and a secret is 64", "bad")
            return
        if not self.join_password.text():
            self.say("An empty password protects nothing", "bad")
            return

        try:
            join_session(
                self.join_path.path, session_id, secret, self.join_password.text().encode()
            )
        except (CryptoError, OSError) as error:
            self.say(str(error), "bad")
            return

        self.session.set_path(self.join_path.path)
        self.join_password.clear()
        self.join_secret.clear()
        self.say("Joined and loaded. This machine can now read files sent in that session.", "good")


def _field(placeholder: str) -> QLineEdit:
    box = QLineEdit()
    box.setObjectName("formInput")
    box.setPlaceholderText(placeholder)
    box.setAlignment(Qt.AlignmentFlag.AlignLeft)
    return box
