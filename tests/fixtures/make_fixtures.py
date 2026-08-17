"""Regenerate the test images. Run this only when the fixture set needs to change.

The images are committed so tests do not depend on a particular Pillow version producing
the same bytes. This script exists so anyone can see exactly how they were made.

    python tests/fixtures/make_fixtures.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
SEED = 20260813


def textured(height, width, channels=None):
    """Smooth gradient plus noise: compresses like a photo rather than like a test pattern."""
    rng = np.random.default_rng(SEED)
    gradient = np.add.outer(np.linspace(0, 200, height), np.linspace(0, 55, width))
    noise = rng.normal(0, 12, size=(height, width))
    plane = np.clip(gradient + noise, 0, 255).astype(np.uint8)
    if channels is None:
        return plane
    return np.stack([np.roll(plane, shift * 7, axis=1) for shift in range(channels)], axis=-1)


def main():
    Image.fromarray(textured(64, 64), "L").save(HERE / "grey_64.png", optimize=True)
    Image.fromarray(textured(64, 64, 3), "RGB").save(HERE / "rgb_64.png", optimize=True)
    Image.fromarray(textured(32, 32, 4), "RGBA").save(HERE / "rgba_32.png", optimize=True)
    Image.fromarray(textured(512, 512), "L").save(HERE / "grey_512.png", optimize=True)

    for quality in (50, 75, 95):
        Image.fromarray(textured(512, 512), "L").save(
            HERE / f"grey_512_q{quality}.jpg", quality=quality, optimize=False
        )
    Image.fromarray(textured(64, 64, 3), "RGB").save(
        HERE / "rgb_64_q75.jpg", quality=75, optimize=False
    )
    Image.fromarray(textured(64, 64), "L").save(
        HERE / "grey_64_progressive.jpg", quality=75, progressive=True
    )

    # Not a carrier, used to check that detection refuses what it should.
    (HERE / "not_an_image.bin").write_bytes(b"BM" + bytes(64))

    total = sum(f.stat().st_size for f in HERE.iterdir() if f.is_file())
    print(f"{len(list(HERE.iterdir())) - 1} fixtures, {total / 1024:.0f} KiB total")


if __name__ == "__main__":
    main()
