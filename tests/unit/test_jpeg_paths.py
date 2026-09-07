"""Paths libjpeg can open.

jpeglib hands the path to a C library as bytes in the system code page, so a folder named
in Thai, Japanese or anything else outside ASCII fails to open on Windows with a message
that reads like a corrupt file. These check the translation, and they check that it costs
nothing when the path was already fine.

No jpeglib needed: what is being tested is the path handling around it.
"""

from sieng.carrier.image._jpeg_codec import readable_path, writable_path

THAI_FOLDER = "รูปภาพ"


def test_an_ascii_path_is_handed_over_untouched(tmp_path):
    """The common case must not copy anything."""
    plain = tmp_path / "plain.jpg"
    plain.write_bytes(b"\xff\xd8not really a jpeg")

    with readable_path(plain) as usable:
        # Only meaningful if the checkout itself sits somewhere ASCII, which is the point.
        if str(plain).isascii():
            assert usable == plain


def test_a_non_ascii_path_becomes_one_libjpeg_can_open(tmp_path):
    folder = tmp_path / THAI_FOLDER
    folder.mkdir()
    original = folder / "ภาพ.jpg"
    original.write_bytes(b"\xff\xd8not really a jpeg")

    with readable_path(original) as usable:
        assert str(usable).isascii()
        assert usable.read_bytes() == original.read_bytes()


def test_no_copy_of_the_cover_outlives_the_read(tmp_path):
    """A copy of a cover left lying around is the thing this project exists to avoid.

    Which branch runs depends on the machine: Windows with 8.3 names gives a second name
    for the same file and copies nothing, everywhere else there is a copy. Both are fine;
    what must never happen is a second file still sitting there afterwards.
    """
    folder = tmp_path / THAI_FOLDER
    folder.mkdir()
    original = folder / "ภาพ.jpg"
    original.write_bytes(b"\xff\xd8not really a jpeg")

    with readable_path(original) as usable:
        was_a_copy = not usable.samefile(original)

    assert original.exists()
    if was_a_copy:
        assert not usable.exists()


def test_an_ascii_scratch_path_is_left_alone(tmp_path):
    scratch = tmp_path / "out.jpg.partial"

    with writable_path(scratch) as usable:
        assert usable == scratch


def test_a_non_ascii_scratch_path_is_replaced(tmp_path):
    folder = tmp_path / THAI_FOLDER
    folder.mkdir()

    with writable_path(folder / "ภาพ.jpg.partial") as usable:
        assert str(usable).isascii()
