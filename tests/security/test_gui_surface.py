"""What the window is allowed to say and to keep.

These read the source rather than importing it. The gui modules need PyQt6, which is not
installed everywhere the test suite runs, and the properties being checked here are
properties of the code as written: a page cannot leak a distinction it never mentions.
"""

from pathlib import Path

GUI = Path(__file__).resolve().parents[2] / "src" / "sieng" / "ui" / "gui"

EXTRACT_PAGE = (GUI / "pages" / "extract_page.py").read_text(encoding="utf-8")
EMBED_PAGE = (GUI / "pages" / "embed_page.py").read_text(encoding="utf-8")
RECALL = (GUI / "components" / "recall.py").read_text(encoding="utf-8")
PAGES = [path.read_text(encoding="utf-8") for path in (GUI / "pages").glob("*.py")]


# ---- the read page must not name the reason it failed ----------------------


def test_the_read_page_has_one_failure_message():
    """Any second wording is a second thing an examiner can tell apart."""
    assert EXTRACT_PAGE.count("CANNOT_READ = (") == 1
    assert EXTRACT_PAGE.count("self.say(CANNOT_READ") == 1


def test_the_read_page_does_not_name_a_cause():
    """Words that would say which of the four possibilities happened."""
    for word in ("DecryptError", "wrong password", "not a stego", "no header", "tampered"):
        assert word not in EXTRACT_PAGE


def test_only_three_named_causes_get_their_own_wording():
    """Stopped, already read, and a field the user left empty. A fourth branch is a leak."""
    assert EXTRACT_PAGE.count("isinstance(error,") == 3


# ---- passwords stay in the field they were typed into ----------------------


def test_pages_clear_the_password_after_every_run():
    """Both outcomes, on every page that asks for one."""
    for source in PAGES:
        if "password_field()" in source:
            assert source.count("self.password.clear()") >= 2


def test_nothing_remembered_is_a_secret():
    """recall stores paths. A password reaching it would be written to disk in the clear."""
    for source in PAGES:
        for line in source.splitlines():
            if "recall.remember" in line:
                assert ".text()" not in line
                assert "password" not in line.lower()


def test_recall_holds_no_secret_of_its_own():
    for word in ("password", "secret", "key", "payload"):
        assert f'"{word}' not in RECALL


def test_the_password_field_never_reveals():
    base = (GUI / "pages" / "base_page.py").read_text(encoding="utf-8")
    assert "EchoMode.Password" in base
    assert "setClearButtonEnabled" not in base
    assert "PasswordEchoOnEdit" not in base


# ---- protection is not something the window can switch off -----------------


def test_the_hide_page_offers_no_way_to_embed_without_a_session():
    """Folding the session controls away must not become a toggle that skips them."""
    assert "state_path=self.session.path" in EMBED_PAGE
    assert "Still needed: a session" in EMBED_PAGE
    for word in ("setCheckable", "no_session", "skip_session", "plaintext"):
        assert word not in EMBED_PAGE
