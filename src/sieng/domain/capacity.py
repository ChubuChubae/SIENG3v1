"""Converting between payload rate and bits, and telling callers the real ceiling.

bpnzAC is bits per non-zero AC coefficient. It is what the steganography literature
reports, so numbers produced here stay comparable with published results.
"""

from sieng.common.errors import CapacityError

# Header cost, from FORMAT_SPEC.md 3. Every embed pays this before any payload.
HEADER_BITS = 96

# STC needs room to route around expensive positions. Pushing the relative payload
# past this makes distortion climb sharply and the coding loss stops being worth it,
# so we refuse rather than produce a stego file that is easy to detect.
MAX_RELATIVE_PAYLOAD = 0.5


def bits_from_bpnzac(rate: float, nnz_ac: int) -> int:
    """How many bits a rate buys, e.g. 0.1 bpnzAC over 26000 coefficients is 2600 bits."""
    if rate <= 0:
        raise ValueError(f"Payload rate must be positive, got {rate}")
    return int(rate * nnz_ac)


def bpnzac_from_bits(bits: int, nnz_ac: int) -> float:
    """The rate a given number of bits works out to. Report this, never the requested rate."""
    if nnz_ac <= 0:
        raise ValueError(f"Carrier has {nnz_ac} non-zero AC coefficients, nothing to embed in")
    return bits / nnz_ac


def max_payload_bits(n_changeable: int, *, header_bits: int = HEADER_BITS) -> int:
    """The hard ceiling for payload bits, after the header and the STC safety margin."""
    usable = int(n_changeable * MAX_RELATIVE_PAYLOAD) - header_bits
    return max(usable, 0)


def check_capacity(payload_bits: int, n_changeable: int, *, header_bits: int = HEADER_BITS) -> int:
    """Fail closed before any work starts, with the real ceiling attached to the error.

    Called before the cost model runs, because computing a J-UNIWARD cost map on a
    large image takes seconds and there is no point paying that to fail afterwards.
    """
    ceiling = max_payload_bits(n_changeable, header_bits=header_bits)
    if payload_bits > ceiling:
        raise CapacityError(
            requested_bits=payload_bits,
            max_bits=ceiling,
            max_bpnzac=bpnzac_from_bits(ceiling, n_changeable) if n_changeable else 0.0,
        )
    return ceiling
