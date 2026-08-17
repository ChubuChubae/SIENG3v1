"""PNG chunk handling, written out by hand rather than through an image library.

An image library gives pixels back but rebuilds the file when it saves, so ancillary
chunks, their order and the exact compression settings all change. That difference is
visible to anyone comparing against an original, which is precisely what we must avoid.
Working at the chunk level means everything we did not touch survives untouched.
"""

import struct
import zlib
from typing import NamedTuple

SIGNATURE = b"\x89PNG\r\n\x1a\n"
IHDR = b"IHDR"
IDAT = b"IDAT"
IEND = b"IEND"

LENGTH_FIELD = 4
TYPE_FIELD = 4
CRC_FIELD = 4


class Chunk(NamedTuple):
    """One PNG chunk. The CRC is recomputed on write, never carried over."""

    type: bytes
    data: bytes

    def pack(self) -> bytes:
        body = self.type + self.data
        return struct.pack(">I", len(self.data)) + body + struct.pack(">I", zlib.crc32(body))


class Header(NamedTuple):
    """What IHDR says about the image."""

    width: int
    height: int
    bit_depth: int
    colour_type: int
    compression: int
    filter_method: int
    interlace: int


def parse_chunks(raw: bytes) -> list[Chunk]:
    """Split a PNG into chunks, checking every CRC on the way.

    A bad CRC means the file is damaged or has been tampered with. Continuing would
    mean embedding into something already broken, so this refuses instead.
    """
    if not raw.startswith(SIGNATURE):
        raise ValueError("Not a PNG: the 8 byte signature is missing")

    chunks: list[Chunk] = []
    offset = len(SIGNATURE)

    while offset + LENGTH_FIELD + TYPE_FIELD <= len(raw):
        (length,) = struct.unpack(">I", raw[offset : offset + LENGTH_FIELD])
        start = offset + LENGTH_FIELD
        end = start + TYPE_FIELD + length
        if end + CRC_FIELD > len(raw):
            raise ValueError(f"PNG chunk at offset {offset} runs past the end of the file")

        body = raw[start:end]
        (stored_crc,) = struct.unpack(">I", raw[end : end + CRC_FIELD])
        if zlib.crc32(body) != stored_crc:
            name = body[:TYPE_FIELD].decode("ascii", "replace")
            raise ValueError(
                f"CRC mismatch in chunk '{name}' at offset {offset}. "
                f"The file is corrupt or has been altered."
            )

        chunks.append(Chunk(body[:TYPE_FIELD], body[TYPE_FIELD:]))
        offset = end + CRC_FIELD

        if chunks[-1].type == IEND:
            break

    if not chunks or chunks[0].type != IHDR:
        raise ValueError("Not a valid PNG: IHDR must be the first chunk")
    if chunks[-1].type != IEND:
        raise ValueError("Not a valid PNG: IEND is missing")

    return chunks


def build_png(chunks: list[Chunk]) -> bytes:
    """Reassemble a PNG from chunks, recomputing every CRC."""
    return SIGNATURE + b"".join(chunk.pack() for chunk in chunks)


def parse_header(chunks: list[Chunk]) -> Header:
    """Read IHDR."""
    return Header(*struct.unpack(">IIBBBBB", chunks[0].data))


def trailing_bytes(raw: bytes) -> bytes:
    """Anything after IEND.

    A PNG ends at IEND. Bytes after it are an overlay: data appended by someone else,
    which the analyzer reports and which we carry across unchanged rather than silently
    dropping, because dropping it would alter evidence.
    """
    end = raw.rfind(IEND)
    if end == -1:
        return b""
    return raw[end + len(IEND) + CRC_FIELD :]


def join_idat(chunks: list[Chunk]) -> bytes:
    """Concatenate every IDAT. PNG allows the pixel stream to be split across many."""
    return b"".join(chunk.data for chunk in chunks if chunk.type == IDAT)
