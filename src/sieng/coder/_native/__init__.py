"""C kernel for the STC Viterbi search.

Why C: at h=10 that is 1024 states per bit, and a 512x512 image at 0.4 bpnzAC carries
tens of thousands of bits. A numpy loop takes minutes where C takes seconds.
"""

HAVE_NATIVE = False

try:  # pragma: no cover
    from sieng.coder._native._stc import viterbi  # type: ignore  # noqa: F401

    HAVE_NATIVE = True
except ImportError:  # pragma: no cover
    pass
