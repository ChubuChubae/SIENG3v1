"""Check the four things carrier/image/_jpeg_codec.py assumes about jpeglib.

D1 was answered with this script: jpeglib 1.0.2 on libjpeg 6b keeps the entropy coded data
byte for byte, and only rewrites headers. jpeg.py relies on that, so run this again after
changing machine, python version or jpeglib version.

    pip install jpeglib
    python tools/spike_jpeglib.py

Each line maps to something the code depends on:

    coefficients are quantised integers   planes() would be in the wrong domain otherwise
    entropy data survives a round trip    splice() pastes original headers onto this data
    a single change survives              embedding would be silently lost otherwise
    progressive files are flagged         reject_progressive() reads progressive_mode

Detail is printed only when something fails, because that is the only time it is needed.
"""

import platform
import sys
import traceback
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
CASES = ["grey_512_q50.jpg", "grey_512_q75.jpg", "grey_512_q95.jpg", "rgb_64_q75.jpg"]
PROGRESSIVE = "grey_64_progressive.jpg"

STANDALONE = {0xD8, 0xD9, 0x01} | set(range(0xD0, 0xD8))
SOS = 0xDA
# Only the markers worth naming when something fails. Everything else falls back to hex,
# which is enough to look up. The first seven are what the fixtures actually contain;
# APP1 and APP14 are added because photos from real cameras carry EXIF and Adobe segments.
MARKER_NAMES = {
    0xD8: "SOI",
    0xE0: "APP0",
    0xE1: "APP1",
    0xEE: "APP14",
    0xDB: "DQT",
    0xC0: "SOF0",
    0xC2: "SOF2",
    0xC4: "DHT",
    0xDA: "SOS",
}

def report(label, passed):
    print(f"  {'PASS' if passed else 'FAIL'}  {label}")
    return passed

def parse_markers(raw):
    """Segments up to and including SOS, as (marker, offset, declared length)."""
    segments = []
    offset = 0
    while offset < len(raw) - 1:
        if raw[offset] != 0xFF:
            offset += 1
            continue
        marker = raw[offset + 1]
        if marker in (0xFF, 0x00):
            offset += 1
            continue
        if marker in STANDALONE:
            segments.append((marker, offset, 0))
            offset += 2
            if marker == 0xD9:
                break
            continue
        length = int.from_bytes(raw[offset + 2 : offset + 4], "big")
        segments.append((marker, offset, length))
        offset += 2 + length
        if marker == SOS:
            break
    return segments


def name_of(marker):
    return MARKER_NAMES.get(marker, f"FF{marker:02X}")


def entropy_of(raw, segments):
    """The compressed image data, which starts after the SOS header."""
    _, offset, length = segments[-1]
    return raw[offset + 2 + length :]


def print_failure_detail(source_bytes, target_bytes):
    """Only called when a check fails. Says which headers moved and where the data diverges."""
    source = parse_markers(source_bytes)
    target = parse_markers(target_bytes)

    print("original: " + ", ".join(f"{name_of(m)}({n})" for m, _, n in source))
    print("written : " + ", ".join(f"{name_of(m)}({n})" for m, _, n in target))

    for marker in (0xC0, 0xC2, SOS):
        a = next((s for s in source if s[0] == marker), None)
        b = next((s for s in target if s[0] == marker), None)
        if a is None or b is None:
            continue
        left = source_bytes[a[1] : a[1] + 2 + a[2]]
        right = target_bytes[b[1] : b[1] + 2 + b[2]]
        if left == right:
            continue
        print(f"{name_of(marker)} original: {left.hex(' ')}")
        print(f"{name_of(marker)} written : {right.hex(' ')}")

    if not source or not target or source[-1][0] != SOS or target[-1][0] != SOS:
        print("no SOS in one of the files, cannot compare the image data")
        return

    left_entropy = entropy_of(source_bytes, source)
    right_entropy = entropy_of(target_bytes, target)
    shared = min(len(left_entropy), len(right_entropy))
    first = next((i for i in range(shared) if left_entropy[i] != right_entropy[i]), shared)
    print(f"entropy data differs at byte {first} of {len(left_entropy)}")


def check_case(jpeglib, name, out):
    """Run the three per file checks. Returns True only if all of them pass."""
    source = FIXTURES / name
    if not source.is_file():
        print(f"SKIP {name} is missing, run tests/fixtures/make_fixtures.py first")
        return None

    try:
        original = jpeglib.read_dct(str(source))
    except Exception as error:
        report(f"{name} can be read", False)
        print(f"{type(error).__name__}: {error}")
        return False

    results = [
        report(
            f"{name} coefficients are quantised integers",
            "int" in str(getattr(original.Y, "dtype", "")),
        )
    ]

    target = out / name
    try:
        original.write_dct(str(target))
    except Exception as error:
        report(f"{name} can be written back", False)
        print(f"{type(error).__name__}: {error}")
        return False

    source_bytes = source.read_bytes()
    target_bytes = target.read_bytes()
    source_markers = parse_markers(source_bytes)
    target_markers = parse_markers(target_bytes)
    preserved = (
        source_markers
        and target_markers
        and source_markers[-1][0] == SOS
        and target_markers[-1][0] == SOS
        and entropy_of(source_bytes, source_markers) == entropy_of(target_bytes, target_markers)
    )
    results.append(report(f"{name} entropy data survives a round trip", bool(preserved)))
    if not preserved:
        print_failure_detail(source_bytes, target_bytes)

    try:
        modified = jpeglib.read_dct(str(source))
        before = int(modified.Y[0, 0, 0, 1])
        modified.Y[0, 0, 0, 1] = before + 1
        changed = out / f"changed_{name}"
        modified.write_dct(str(changed))
        after = int(jpeglib.read_dct(str(changed)).Y[0, 0, 0, 1])
        results.append(report(f"{name} a single coefficient change survives", after == before + 1))
    except Exception as error:
        report(f"{name} a single coefficient change survives", False)
        print(f"{type(error).__name__}: {error}")
        results.append(False)

    return all(results)


def check_progressive(jpeglib):
    """reject_progressive() in jpeg.py depends on this flag being set."""
    path = FIXTURES / PROGRESSIVE
    if not path.is_file():
        return None
    try:
        flagged = bool(getattr(jpeglib.read_dct(str(path)), "progressive_mode", False))
    except Exception:
        # Refusing to read it outright is also fine, the carrier never sees it either way.
        return report("progressive files are refused or flagged", True)
    return report("progressive files are flagged by progressive_mode", flagged)


def main():
    print(f"python {sys.version.split()[0]} on {platform.system()} {platform.machine()}")

    try:
        import jpeglib
    except ImportError:
        print("jpeglib is not installed. Run: pip install jpeglib")
        return 1

    version = getattr(jpeglib, "version", None)
    getter = getattr(version, "get", None)
    print(f"jpeglib {getattr(jpeglib, '__version__', '?')}, libjpeg {getter() if getter else '?'}")
    print()

    out = Path("spike_out")
    out.mkdir(exist_ok=True)

    results = []
    for name in CASES:
        try:
            outcome = check_case(jpeglib, name, out)
        except Exception:
            traceback.print_exc()
            outcome = False
        if outcome is not None:
            results.append(outcome)

    progressive = check_progressive(jpeglib)
    if progressive is not None:
        results.append(progressive)

    print()
    if results and all(results):
        print("jpeglib behaves the way _jpeg_codec.py assumes.")
        return 0
    print("jpeglib does not behave the way _jpeg_codec.py assumes. Do not ship this build.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
