"""JPEG carrier. The byte exact round trip here gates everything JPEG in the project.

These are skipped when jpeglib is not installed, so the rest of the suite still runs on a
machine that has not set it up. A skip is not a pass: Phase 3.3 is only done when these
run for real.
"""

from itertools import pairwise
from pathlib import Path

import numpy as np
import pytest

from sieng.carrier.image._jpeg_codec import (
    DHT,
    DQT,
    blocks_to_grid,
    collect,
    find_sos,
    grid_to_blocks,
    parse_segments,
    splice,
    verify_tables_match,
)
from sieng.carrier.image.jpeg import JpegCarrier
from sieng.common.errors import CorruptCarrierError, UnsupportedCarrierError
from sieng.common.types import BLOCK_SIZE

jpeglib = pytest.importorskip("jpeglib", reason="JPEG support needs jpeglib")

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
BASELINE = ["grey_512_q50.jpg", "grey_512_q75.jpg", "grey_512_q95.jpg", "rgb_64_q75.jpg"]
PROGRESSIVE = "grey_64_progressive.jpg"


def loaded(name):
    carrier = JpegCarrier(FIXTURES / name)
    carrier.load()
    return carrier


# ---- block layout ----------------------------------------------------------


def test_blocks_and_grid_are_inverses():
    """domain finds the DC coefficient at [::8, ::8], which needs blocks laid out as tiles."""
    rng = np.random.default_rng(11)
    blocks = rng.integers(-50, 50, size=(3, 4, BLOCK_SIZE, BLOCK_SIZE), dtype=np.int16)

    assert np.array_equal(grid_to_blocks(blocks_to_grid(blocks)), blocks)


def test_dc_lands_where_the_domain_layer_looks_for_it():
    blocks = np.zeros((2, 2, BLOCK_SIZE, BLOCK_SIZE), dtype=np.int16)
    blocks[1, 0, 0, 0] = 42

    grid = blocks_to_grid(blocks)

    assert grid[BLOCK_SIZE, 0] == 42


# ---- marker parsing --------------------------------------------------------


def test_finds_the_start_of_scan():
    raw = (FIXTURES / "grey_512_q75.jpg").read_bytes()

    sos = find_sos(raw)

    assert sos.marker == 0xDA
    assert 0 < sos.end < len(raw)


def test_a_file_without_a_scan_is_refused():
    with pytest.raises(CorruptCarrierError, match="no start of scan"):
        find_sos(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes(6))


def test_collects_every_table_segment():
    raw = (FIXTURES / "rgb_64_q75.jpg").read_bytes()

    assert len(collect(raw, (DQT,))) == 2
    assert len(collect(raw, (DHT,))) == 4


def test_segments_are_contiguous():
    """A gap or an overlap means the parser lost track, which would corrupt a splice."""
    raw = (FIXTURES / "grey_512_q75.jpg").read_bytes()
    segments = parse_segments(raw)

    for earlier, later in pairwise(segments):
        assert earlier.end == later.offset


# ---- the splice ------------------------------------------------------------


def test_splice_refuses_when_the_tables_changed():
    """Entropy data encoded against other tables decodes to noise, so this must fail loudly."""
    raw = bytearray((FIXTURES / "grey_512_q75.jpg").read_bytes())
    quant = collect(bytes(raw), (DQT,))[0]
    start = bytes(raw).find(quant)
    raw[start + 5] ^= 0x01

    with pytest.raises(CorruptCarrierError, match="rewrote the quantisation tables"):
        verify_tables_match((FIXTURES / "grey_512_q75.jpg").read_bytes(), bytes(raw))


def test_splice_keeps_the_original_headers():
    original = (FIXTURES / "grey_512_q75.jpg").read_bytes()

    result = splice(original, original)

    assert result == original


# ---- the blocking test -----------------------------------------------------


@pytest.mark.parametrize("name", BASELINE)
def test_jpeg_roundtrip_is_byte_exact(name, tmp_path):
    """Load then save without touching a coefficient must return the original file.

    If this fails, nothing else in the project matters: the recompression traces are
    already there before anything has been embedded.
    """
    source = FIXTURES / name
    carrier = JpegCarrier(source)
    carrier.load()

    destination = tmp_path / name
    carrier.save(destination)

    assert destination.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("name", BASELINE)
def test_a_changed_coefficient_survives_a_save_and_reload(name, tmp_path):
    carrier = loaded(name)
    planes = carrier.planes()
    target = np.flatnonzero(planes[0].changeable)[0]
    before = int(planes[0].values.reshape(-1)[target])
    planes[0].values.reshape(-1)[target] = before + 1
    carrier.apply(planes)

    destination = tmp_path / name
    carrier.save(destination)
    reloaded = JpegCarrier(destination)
    reloaded.load()

    assert int(reloaded.planes()[0].values.reshape(-1)[target]) == before + 1


@pytest.mark.parametrize("name", BASELINE)
def test_only_the_scan_data_changes(name, tmp_path):
    """Everything before the start of scan must come out identical, byte for byte."""
    source = FIXTURES / name
    carrier = loaded(name)
    planes = carrier.planes()
    index = np.flatnonzero(planes[0].changeable)[0]
    planes[0].values.reshape(-1)[index] += 1
    carrier.apply(planes)

    destination = tmp_path / name
    carrier.save(destination)

    original = source.read_bytes()
    result = destination.read_bytes()
    assert result[: find_sos(original).end] == original[: find_sos(original).end]


# ---- coefficients ----------------------------------------------------------


@pytest.mark.parametrize("name", BASELINE)
def test_coefficients_are_quantised_integers(name):
    """Floats would mean the library dequantised them, which is the wrong domain entirely."""
    plane = loaded(name).planes()[0]

    assert np.issubdtype(plane.values.dtype, np.integer)


@pytest.mark.parametrize("name", BASELINE)
def test_dc_is_never_changeable(name):
    plane = loaded(name).planes()[0]

    assert not plane.changeable[::BLOCK_SIZE, ::BLOCK_SIZE].any()


@pytest.mark.parametrize("name", BASELINE)
def test_nnz_ac_matches_the_mask(name):
    carrier = loaded(name)

    assert carrier.nnz_ac() == int(carrier.planes()[0].changeable.sum())
    assert carrier.capacity_base() == carrier.nnz_ac()


def test_a_colour_jpeg_offers_three_planes():
    assert len(loaded("rgb_64_q75.jpg").planes()) == 3


def test_lower_quality_leaves_fewer_coefficients():
    """More aggressive quantisation zeroes more AC coefficients, so capacity drops."""
    assert loaded("grey_512_q50.jpg").nnz_ac() < loaded("grey_512_q95.jpg").nnz_ac()


# ---- refusals --------------------------------------------------------------


def test_progressive_jpeg_handled_or_refused():
    """jpeglib reads a progressive file without complaint, so the carrier must catch it."""
    with pytest.raises(UnsupportedCarrierError, match="progressive"):
        loaded(PROGRESSIVE)


def test_a_truncated_jpeg_is_refused(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes((FIXTURES / "grey_512_q75.jpg").read_bytes()[:200])

    with pytest.raises((CorruptCarrierError, UnsupportedCarrierError)):
        JpegCarrier(broken).load()


def test_methods_refuse_to_run_before_load():
    with pytest.raises(RuntimeError, match="has not loaded"):
        JpegCarrier(FIXTURES / "grey_512_q75.jpg").planes()


# ---- fingerprint -----------------------------------------------------------


@pytest.mark.parametrize("name", BASELINE)
def test_fingerprint_ignores_coefficients(name):
    """The receiver recomputes this from the stego file, so embedding must not change it."""
    carrier = loaded(name)
    before = carrier.fingerprint()

    planes = carrier.planes()
    index = np.flatnonzero(planes[0].changeable)[0]
    planes[0].values.reshape(-1)[index] += 1
    carrier.apply(planes)

    assert carrier.fingerprint() == before


def test_fingerprint_separates_quality_settings():
    """Different quant tables must give different fingerprints, or aad binding is weak."""
    prints = {loaded(name).fingerprint() for name in BASELINE}

    assert len(prints) == len(BASELINE)
