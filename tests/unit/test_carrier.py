"""carrier: the registry, detection by content, and the PNG round trip."""

from pathlib import Path

import numpy as np
import pytest

from sieng.carrier.base import Carrier
from sieng.carrier.detect import open_carrier, read_head, sniff
from sieng.carrier.image.png import CHANNELS, PngCarrier, paeth, refilter, unfilter
from sieng.carrier.registry import CarrierRegistry
from sieng.common.errors import CorruptCarrierError, UnsupportedCarrierError
from sieng.common.types import SPATIAL_DOMAIN

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PNG_FILES = ["grey_64.png", "rgb_64.png", "rgba_32.png", "grey_512.png"]


@pytest.fixture
def registry():
    reg = CarrierRegistry()
    reg.register(PngCarrier)
    return reg


# ---- registry --------------------------------------------------------------


def test_registry_rejects_duplicate_suffix(registry):
    """Two carriers for one suffix would make the choice arbitrary."""

    class OtherPng(Carrier):
        suffixes = (".png",)
        magic = (b"\x89PNG",)
        domain = SPATIAL_DOMAIN
        lossless_roundtrip = True
        security_tier = "strong"

        def load(self): ...
        def planes(self): ...
        def apply(self, planes): ...
        def save(self, destination): ...
        def fingerprint(self): ...
        def capacity_base(self): ...

    with pytest.raises(ValueError, match="already registered"):
        registry.register(OtherPng)


def test_registering_the_same_carrier_twice_is_harmless(registry):
    registry.register(PngCarrier)

    assert registry.all() == [PngCarrier]


def test_for_domain_is_what_the_ui_reads(registry):
    assert registry.for_domain(SPATIAL_DOMAIN) == [PngCarrier]
    assert registry.for_domain("dct") == []


def test_suffixes_are_sorted(registry):
    assert registry.suffixes() == [".png"]


# ---- detection -------------------------------------------------------------


def test_finds_png_by_content(registry):
    assert sniff(FIXTURES / "grey_64.png", registry) is PngCarrier


def test_extension_lying_uses_content(tmp_path, registry):
    """A file named .png that is really a JPEG must not be treated as a PNG."""
    liar = tmp_path / "lying.png"
    liar.write_bytes((FIXTURES / "grey_512_q75.jpg").read_bytes())

    with pytest.raises(UnsupportedCarrierError):
        sniff(liar, registry)


@pytest.mark.parametrize(
    ("name", "expected"),
    [("grey_512_q75.jpg", "Phase 1 supports"), ("not_an_image.bin", "BMP arrives in Phase 2")],
)
def test_unsupported_carrier_is_refused(name, expected, registry):
    """The message names the format and says when it arrives, not just "unsupported"."""
    with pytest.raises(UnsupportedCarrierError, match=expected):
        sniff(FIXTURES / name, registry)


def test_missing_file_is_refused(tmp_path, registry):
    with pytest.raises(UnsupportedCarrierError, match="Not a file"):
        sniff(tmp_path / "absent.png", registry)


def test_read_head_stops_at_the_requested_size():
    assert len(read_head(FIXTURES / "grey_512.png", 16)) == 16


def test_open_carrier_loads_it(registry):
    carrier = open_carrier(FIXTURES / "grey_64.png", registry)

    assert carrier.loaded
    assert carrier.capacity_base() > 0


# ---- PNG filters -----------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "above", "upper_left", "expected"),
    [
        (0, 0, 0, 0),
        (10, 20, 30, 10),  # estimate 0 is nearest to left
        (10, 20, 10, 20),  # estimate 20 is exactly above
        (200, 100, 150, 150),  # estimate 150 is exactly upper left
        (5, 5, 5, 5),
    ],
)
def test_paeth_picks_the_nearest_neighbour(left, above, upper_left, expected):
    """Worked through by hand from the PNG spec, since a wrong predictor decodes silently."""
    assert paeth(left, above, upper_left) == expected


@pytest.mark.parametrize("filter_type", [0, 1, 2, 3, 4])
def test_every_filter_type_survives_a_round_trip(filter_type):
    """All five filters must undo exactly, or a saved file decodes to different pixels."""
    rng = np.random.default_rng(3)
    pixels = rng.integers(0, 256, size=(8, 12), dtype=np.uint8)
    filters = np.full(8, filter_type, dtype=np.uint8)

    encoded = refilter(pixels, filters, bpp=3)
    decoded, seen = unfilter(encoded, height=8, stride=12, bpp=3)

    assert np.array_equal(decoded, pixels)
    assert np.array_equal(seen, filters)


def test_unknown_filter_type_is_refused():
    with pytest.raises(CorruptCarrierError, match="Unknown PNG filter"):
        unfilter(bytes([9]) + bytes(4), height=1, stride=4, bpp=1)


def test_truncated_pixel_stream_is_refused():
    with pytest.raises(CorruptCarrierError, match="pixel stream"):
        unfilter(bytes(3), height=4, stride=8, bpp=1)


# ---- PNG carrier -----------------------------------------------------------


@pytest.mark.parametrize("name", PNG_FILES)
def test_png_roundtrip_is_byte_exact(name, tmp_path):
    """Load then save without touching anything must give the original file back."""
    source = FIXTURES / name
    carrier = PngCarrier(source)
    carrier.load()

    destination = tmp_path / name
    carrier.save(destination)

    assert destination.read_bytes() == source.read_bytes()


@pytest.mark.parametrize("name", PNG_FILES)
def test_pixels_match_an_independent_decoder(name):
    """Our own unfilter must agree with Pillow, or we are reading the wrong numbers."""
    pillow = pytest.importorskip("PIL.Image")
    carrier = PngCarrier(FIXTURES / name)
    carrier.load()

    reference = np.array(pillow.open(FIXTURES / name))
    assert np.array_equal(carrier.pixels.reshape(reference.shape), reference)


@pytest.mark.parametrize("name", PNG_FILES)
def test_modified_pixels_survive_a_save_and_reload(name, tmp_path):
    carrier = PngCarrier(FIXTURES / name)
    carrier.load()
    plane = carrier.planes()[0]
    plane.values[0, 0] ^= 1
    plane.values[-1, -1] ^= 1
    carrier.apply([plane])

    destination = tmp_path / name
    carrier.save(destination)
    reloaded = PngCarrier(destination)
    reloaded.load()

    assert np.array_equal(reloaded.pixels, carrier.pixels)


def test_crc_stays_valid_after_a_change(tmp_path):
    """parse_chunks checks every CRC, so a rebuild with a bad one fails to load."""
    carrier = PngCarrier(FIXTURES / "grey_64.png")
    carrier.load()
    plane = carrier.planes()[0]
    plane.values[2, 2] ^= 1
    carrier.apply([plane])

    destination = tmp_path / "changed.png"
    carrier.save(destination)

    PngCarrier(destination).load()


def test_every_sample_is_changeable():
    """Spatial carriers have no wet elements."""
    carrier = PngCarrier(FIXTURES / "grey_64.png")
    carrier.load()

    assert carrier.planes()[0].changeable.all()


def test_capacity_base_counts_every_sample():
    carrier = PngCarrier(FIXTURES / "rgb_64.png")
    carrier.load()

    assert carrier.capacity_base() == 64 * 64 * CHANNELS[2]


def test_fingerprint_ignores_pixel_values(tmp_path):
    """The receiver recomputes this from the stego file, so embedding must not change it."""
    carrier = PngCarrier(FIXTURES / "grey_64.png")
    carrier.load()
    before = carrier.fingerprint()

    plane = carrier.planes()[0]
    plane.values[5, 5] ^= 1
    carrier.apply([plane])

    assert carrier.fingerprint() == before


def test_fingerprint_differs_between_images():
    grey = PngCarrier(FIXTURES / "grey_64.png")
    grey.load()
    rgb = PngCarrier(FIXTURES / "rgb_64.png")
    rgb.load()

    assert grey.fingerprint() != rgb.fingerprint()


def test_methods_refuse_to_run_before_load():
    carrier = PngCarrier(FIXTURES / "grey_64.png")

    with pytest.raises(RuntimeError, match="has not loaded"):
        carrier.planes()


def test_a_corrupt_png_is_refused(tmp_path):
    broken = bytearray((FIXTURES / "grey_64.png").read_bytes())
    broken[30] ^= 0xFF
    target = tmp_path / "broken.png"
    target.write_bytes(bytes(broken))

    with pytest.raises(CorruptCarrierError, match="CRC mismatch"):
        PngCarrier(target).load()
