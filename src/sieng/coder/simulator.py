"""What a perfect coder would achieve, so the real one can be measured against it.

An optimal embedder changes coefficient i with a probability that falls off exponentially
with its cost, tuned so the total entropy equals the payload. Nothing can do better at
that payload, which makes it the yardstick.

There are two yardsticks here and picking the wrong one makes a good coder look bad.

    binary    one bit per coefficient at most. Flipping the parity is one decision and
              the direction is whichever costs less. This is what stc.py does, so this
              is the bound to measure it against.
    ternary   log2(3) bits per coefficient, treating +1 and -1 as separate symbols.
              Only a double layered STC reaches for this. The gap between the two is
              the headroom a Phase 2 coder could still recover.

Nothing here writes a stego file. It only says what the cost would be.
"""

from collections.abc import Callable

import numpy as np

from sieng.domain.plane import Array

MAX_BITS_TERNARY = float(np.log2(3))
MAX_BITS_BINARY = 1.0

# Bisection range for lambda. Small lambda means costs barely matter and the payload is
# near maximum, large lambda means only the cheapest coefficients ever move.
LAMBDA_LOW = 1e-12
LAMBDA_HIGH = 1e12
BISECTION_STEPS = 200


def _plogp(p: Array) -> Array:
    """p * log2(p), taking 0 * log2(0) as 0 rather than nan."""
    safe = np.where(p > 0, p, 1.0)
    return np.where(p > 0, p * np.log2(safe), 0.0)


def _finite(cost: Array) -> Array:
    """Infinite costs contribute nothing, so replace them once instead of masking twice."""
    return np.where(np.isfinite(cost), np.nan_to_num(cost, posinf=0.0), 0.0)


def _bisect(
    payload_at: Callable[[float], float], target_bits: int, ceiling: float, what: str
) -> float:
    """Find the lambda whose payload matches. Payload falls as lambda grows."""
    if target_bits <= 0:
        return LAMBDA_HIGH
    if target_bits > ceiling:
        raise ValueError(
            f"No lambda carries {target_bits} bits with {what} embedding here. "
            f"These coefficients hold at most {ceiling:.0f} bits, the rest are wet."
        )
    low, high = LAMBDA_LOW, LAMBDA_HIGH
    for _ in range(BISECTION_STEPS):
        middle = (low + high) / 2
        if payload_at(middle) > target_bits:
            low = middle
        else:
            high = middle
    return (low + high) / 2


# ---- binary, the bound that matches stc.py ---------------------------------


def binary_probability(cost: Array, lam: float) -> Array:
    """How often each coefficient flips, at a given lambda."""
    with np.errstate(over="ignore"):
        flip = np.exp(-lam * np.asarray(cost, dtype=np.float64))
    return flip / (1.0 + flip)


def binary_payload(cost: Array, lam: float) -> float:
    """Bits an optimal binary coder carries at this lambda."""
    p = binary_probability(cost, lam)
    return float(-np.sum(_plogp(p) + _plogp(1.0 - p)))


def binary_lambda(cost: Array, target_bits: int) -> float:
    return _bisect(
        lambda lam: binary_payload(cost, lam),
        target_bits,
        binary_payload(cost, LAMBDA_LOW),
        "binary",
    )


def binary_bound(cost: Array, target_bits: int) -> float:
    """The lowest distortion any binary coder could pay at this payload."""
    p = binary_probability(cost, binary_lambda(cost, target_bits))
    return float(np.sum(p * _finite(cost)))


def coding_loss(actual_distortion: float, cost: Array, target_bits: int) -> float:
    """How much more stc.py paid than a perfect binary coder. 1.0 would be perfect.

    Report this next to P_E. A high loss means the trellis is the weak part, a low loss
    with poor detection results means the cost model is.
    """
    bound = binary_bound(cost, target_bits)
    return actual_distortion / bound if bound > 0 else 1.0


# ---- ternary, what a double layered coder could reach ----------------------


def ternary_probabilities(rho_p1: Array, rho_m1: Array, lam: float) -> tuple[Array, Array]:
    """How often each coefficient moves up and down, at a given lambda.

    Infinite costs fall out on their own: exp(-lambda * inf) is zero, so a forbidden
    direction is never chosen and a wet coefficient never moves at all.
    """
    with np.errstate(over="ignore"):
        up = np.exp(-lam * np.asarray(rho_p1, dtype=np.float64))
        down = np.exp(-lam * np.asarray(rho_m1, dtype=np.float64))
    total = 1.0 + up + down
    return up / total, down / total


def ternary_payload(rho_p1: Array, rho_m1: Array, lam: float) -> float:
    up, down = ternary_probabilities(rho_p1, rho_m1, lam)
    return float(-np.sum(_plogp(up) + _plogp(down) + _plogp(1.0 - up - down)))


def ternary_lambda(rho_p1: Array, rho_m1: Array, target_bits: int) -> float:
    return _bisect(
        lambda lam: ternary_payload(rho_p1, rho_m1, lam),
        target_bits,
        ternary_payload(rho_p1, rho_m1, LAMBDA_LOW),
        "ternary",
    )


def simulate_embedding(rho_p1: Array, rho_m1: Array, target_bits: int) -> tuple[Array, Array]:
    """Change probabilities an optimal ternary coder would use.

    Used by research to measure a cost model without running STC at all, which matters
    when a sweep covers thousands of images.
    """
    lam = ternary_lambda(rho_p1, rho_m1, target_bits)
    return ternary_probabilities(rho_p1, rho_m1, lam)


def ternary_bound(rho_p1: Array, rho_m1: Array, target_bits: int) -> float:
    """The lowest distortion any ternary coder could pay at this payload."""
    up, down = simulate_embedding(rho_p1, rho_m1, target_bits)
    return float(np.sum(up * _finite(rho_p1)) + np.sum(down * _finite(rho_m1)))
