"""The main engine: JPEG, J-UNIWARD, STC, and the crypto stack in front of it.

There is no arithmetic in this file. Every line is a call into a layer that has its own
tests, and what this module contributes is the order. That order is given in
PROJECT_STRUCTURE.md 2.3 and 2.4 and it is a security property, so a rearrangement that
still passes the tests is still wrong.

Embedding, in the order it happens:

    identify the file by its bytes, never its name
    read the plane, and find out how much of it can actually move
    check capacity before doing any expensive work
    take the next message keys, which commits the ratchet state to disk
    seal the payload, with the header and the carrier's fingerprint as associated data
    whiten the header with the session key
    lay the bits out in the secret order, then run the trellis
    write the file

Three things here are decisions rather than transcription, and each is stated where it is
made as well as here.

**Capacity is checked before the cost map is built.** A J-UNIWARD cost map on a large
image takes seconds, and paying that only to discover the payload does not fit is waste.
`gcm_siv.sealed_length` gives the final size before anything is encrypted.

**The coefficients are split into two regions, both secret.** The header carries the
counter, and the counter is what produces `seed_sel`, so the payload's secret order cannot
be known until the header has been read. The header therefore uses an order derived from
the session level header key, which the receiver holds from the start. Laying the header
in plain scan order instead would put every header this program has ever written into the
same coefficients: nothing readable, but a fixed place to look.

**The split is a fixed fraction of the plane, not proportional to the payload.** It has to
be, because the receiver must locate the header before it knows the payload length, and a
size that depends on the payload would leave it guessing. One eighth for a fixed 96 bits
means the header region runs at a very low rate, which is the cheap end of the trade and
the right way round: the header is the part an examiner would most like to find.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from sieng.carrier.detect import open_carrier
from sieng.carrier.registry import CarrierRegistry
from sieng.coder import stc
from sieng.coder.base import DEFAULT_HEIGHT, bits_to_bytes, bytes_to_bits, flip_costs
from sieng.coder.simulator import coding_loss
from sieng.common.errors import CapacityError, DecryptError
from sieng.common.types import DCT_DOMAIN
from sieng.cost.juniward import JUniwardCost
from sieng.crypto import header as header_module
from sieng.crypto.aead import gcm_siv
from sieng.crypto.kdf import hkdf, labels
from sieng.crypto.ratchet import session
from sieng.domain.capacity import bpnzac_from_bits, check_capacity
from sieng.domain.plane import Array
from sieng.domain.selection import permute
from sieng.pipeline.context import RunContext
from sieng.pipeline.engines.base import (
    EmbedRequest,
    EmbedResult,
    Engine,
    ExtractRequest,
    ExtractResult,
)

HEADER_BITS = header_module.HEADER_BITS

# The header gets one coefficient in this many. Fixed so both sides compute the same split
# from the plane size alone, with no dependence on anything inside the header.
HEADER_SHARE = 8

# How far the receiver will search for the counter. Bounded, or a file with nothing hidden
# in it costs sixteen million derivations to reject (FORMAT_SPEC.md 3.3).
DEFAULT_MAX_SKIP = 1000


@dataclass(frozen=True)
class Layout:
    """Which coefficients carry the header and which carry the payload.

    Two slices of one secret order rather than two orders over the same coefficients,
    because they must not overlap: a coefficient carrying a header bit cannot also carry
    a payload bit.
    """

    header_index: Array
    payload_index: Array

    @classmethod
    def build(cls, n_changeable: int, header_key: bytes) -> "Layout":
        """The split. Depends only on the plane size and the session key, never on the
        payload, so the receiver can compute it before reading anything."""
        order = permute(n_changeable, hkdf.expand_key(header_key, labels.HEADER_STREAM))
        split = header_span(n_changeable)
        return cls(order[:split], order[split:])


def header_span(n_changeable: int) -> int:
    """How many coefficients the header region holds."""
    return max(HEADER_BITS, n_changeable // HEADER_SHARE)


def payload_capacity(n_changeable: int) -> int:
    """How many coefficients are left for the payload once the header has its share."""
    return n_changeable - header_span(n_changeable)


class JUniwardStcEngine(Engine):
    """J-UNIWARD costs, syndrome trellis coding, on quantised JPEG coefficients."""

    engine_id = "juniward_stc"
    description = "J-UNIWARD cost model with syndrome trellis coding, for baseline JPEG"
    supported_domains = (DCT_DOMAIN,)

    def __init__(
        self,
        carriers: CarrierRegistry | None = None,
        cost_model: JUniwardCost | None = None,
        max_skip: int = DEFAULT_MAX_SKIP,
    ) -> None:
        self.carriers = carriers if carriers is not None else default_registry()
        self.cost_model = cost_model if cost_model is not None else JUniwardCost()
        self.max_skip = max_skip

    # ---- embed -------------------------------------------------------------

    def embed(self, request: EmbedRequest, context: RunContext) -> EmbedResult:
        context.step(0, "Reading the cover")
        carrier = open_carrier(request.cover, self.carriers)
        planes = carrier.planes()
        plane = planes[request.component]
        values, index = plane.flatten()
        height = request.constraint_height or DEFAULT_HEIGHT

        ciphertext_bytes = gcm_siv.sealed_length(len(request.payload))
        payload_bits = ciphertext_bytes * 8
        context.step(5, "Checking capacity")
        check_capacity(payload_bits, payload_capacity(values.size), header_bits=0)

        context.step(10, "Taking the next message keys")
        session_id, header_key = session.header_material(request.state_path, request.password)
        keys = session.send(request.state_path, request.password)

        context.step(20, "Sealing the payload")
        header = header_module.Header(
            session_id=session_id,
            counter=keys.counter,
            length=ciphertext_bytes,
            flags=header_module.build_flags(has_precover=request.precover is not None),
        )
        # The fingerprint covers everything embedding does not change, so a ciphertext cut
        # out of this file and pasted into another will not open (THREAT_MODEL.md S10).
        aad = header.pack() + carrier.fingerprint()
        ciphertext = gcm_siv.seal(keys.aead, keys.nonce, request.payload, aad)
        masked = header_module.whiten(header.pack(), header_key, keys.counter)

        context.step(30, "Scoring the cover")
        rho_p1, rho_m1 = self.cost_model.costs(plane)
        up, down = rho_p1.reshape(-1)[index], rho_m1.reshape(-1)[index]

        context.step(60, "Embedding")
        layout = Layout.build(values.size, header_key)
        stego = values.copy()
        write_region(stego, up, down, layout.header_index, bytes_to_bits(masked), height)
        write_region(stego, up, down, layout.payload_index, bytes_to_bits(ciphertext), height)

        context.step(90, "Writing the stego file")
        plane.unflatten(stego, index)
        carrier.apply(planes)
        carrier.save(request.destination)

        base = carrier.capacity_base()
        total_bits = HEADER_BITS + payload_bits
        cost, _ = flip_costs(values, up, down)
        distortion = stc.distortion(values, stego, up, down)
        context.step(100, "Done")

        return EmbedResult(
            destination=Path(request.destination),
            payload_bytes=len(request.payload),
            counter=keys.counter,
            changes=int(np.count_nonzero(stego != values)),
            capacity_base=base,
            effective_rate=bpnzac_from_bits(total_bits, base),
            engine_id=self.engine_id,
            distortion=distortion,
            coding_loss=coding_loss(distortion, cost, total_bits),
        )

    # ---- extract -----------------------------------------------------------

    def extract(self, request: ExtractRequest, context: RunContext) -> ExtractResult:
        context.step(0, "Reading the file")
        carrier = open_carrier(request.stego, self.carriers)
        plane = carrier.planes()[request.component]
        values, _ = plane.flatten()
        height = request.constraint_height or DEFAULT_HEIGHT

        context.step(20, "Looking for a header")
        session_id, header_key = session.header_material(request.state_path, request.password)
        layout = Layout.build(values.size, header_key)
        header = self.read_header(values, layout, header_key, height)

        # A file from another session. Reported as the same failure as everything else:
        # saying "wrong session" would tell an examiner the file holds something at all.
        if header.session_id != session_id:
            raise DecryptError

        context.step(50, "Deriving the message keys")
        keys = session.receive(request.state_path, request.password, header.counter, self.max_skip)

        context.step(70, "Reading the payload")
        bits = stc.extract(values[layout.payload_index], header.length * 8, height)
        ciphertext = bits_to_bytes(bits)

        context.step(90, "Opening the payload")
        aad = header.pack() + carrier.fingerprint()
        payload = gcm_siv.open_(keys.aead, keys.nonce, ciphertext, aad)

        # Only now, once the payload has actually opened. Marking earlier would let anyone
        # burn a counter by sending noise.
        session.mark_received(request.state_path, request.password, header.counter)
        context.step(100, "Done")
        return ExtractResult(payload=payload, counter=header.counter, engine_id=self.engine_id)

    def read_header(
        self, values: Array, layout: Layout, header_key: bytes, height: int
    ) -> header_module.Header:
        """Pull the header out of its region and find the counter it was whitened with.

        Everything needed to locate the region comes from the session key and the plane
        size, so there is nothing to guess. What is not known is the counter, and that is
        what `unwhiten_search` is for, bounded by max_skip.
        """
        bits = stc.extract(values[layout.header_index], HEADER_BITS, height)
        return header_module.unwhiten_search(
            bits_to_bytes(bits),
            header_key,
            last_counter=0,
            max_skip=self.max_skip,
            max_length=values.size // 8,
        )


def write_region(
    stego: Array, up: Array, down: Array, region: Array, bits: Array, height: int
) -> None:
    """Run the trellis over one region and write the result back into place.

    Raises CapacityError naming the region, because "the payload does not fit" and "the
    header does not fit" call for different answers from the caller.
    """
    try:
        stego[region] = stc.embed(stego[region], up[region], down[region], bits, height)
    except CapacityError as error:
        raise CapacityError(
            requested_bits=error.requested_bits,
            max_bits=error.max_bits,
            max_bpnzac=error.max_bpnzac,
        ) from error


def default_registry() -> CarrierRegistry:
    """A registry holding the carriers this engine can use.

    Built here rather than demanded from the caller, so an engine can be constructed in a
    test without assembling a container. The real one still comes from app.container.
    """
    from sieng.carrier.image.jpeg import JpegCarrier

    registry = CarrierRegistry()
    registry.register(JpegCarrier)
    return registry


__all__ = [
    "HEADER_SHARE",
    "JUniwardStcEngine",
    "Layout",
    "default_registry",
    "header_span",
    "payload_capacity",
]
