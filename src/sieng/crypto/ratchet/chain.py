"""The symmetric ratchet: one set of keys per message, and no way back.

A chain key produces two things and then destroys itself:

    MK[n]   = HKDF-Expand(CK[n], MESSAGE_KEY)     the keys this message uses
    CK[n+1] = HKDF-Expand(CK[n], RATCHET_STEP)    the chain key the next one starts from

Only the labels separate them, which is why labels.py is written the way it is.

Then `CK[n]` is discarded, and that single act is the whole of forward secrecy. HKDF cannot
be run backwards, so once `CK[n]` is gone the keys for message n cannot be reconstructed
from anything that remains, not by the sender, not by the receiver, and not by someone who
seizes the machine tomorrow. Old stego files stay unreadable.

Each message key expands once more into four values at fixed offsets:

    K_aead   (32)   encrypts the payload
    nonce    (12)   for AES-256-GCM-SIV
    K_hdr    (32)   reserved, unused in v1
    seed_sel (32)   the secret order the coefficients are visited in

That last one is what makes this steganography rather than encryption with extra steps.
Because it comes from MK[n], every image has a different selection channel, so what an
examiner learns from one image tells them nothing about the next.

Zeroizing in Python is best effort and this file says so rather than pretending otherwise:
`bytes` is immutable and the interpreter may have copied it. What can be done is done, and
the real protection is that the value is short-lived.

This layer runs under mypy --strict, so annotations are complete (PROJECT_CONTEXT.md 2.2.1).
"""

from dataclasses import dataclass
from typing import Final

from sieng.common.errors import CryptoError, RatchetLimitError, ReplayError
from sieng.crypto.kdf import hkdf, labels

KEY_BYTES: Final = 32
NONCE_BYTES: Final = 12
SESSION_ID_BYTES: Final = 4

# The four subkeys, laid out end to end in one expansion (FORMAT_SPEC.md 2.3).
AEAD_SLICE: Final = slice(0, 32)
NONCE_SLICE: Final = slice(32, 44)
HEADER_SLICE: Final = slice(44, 76)
SELECTION_SLICE: Final = slice(76, 108)
MESSAGE_KEYS_BYTES: Final = 108

# The header carries the counter in 24 bits, so the chain cannot outlive that.
MAX_COUNTER: Final = (1 << 24) - 1


@dataclass(frozen=True)
class MessageKeys:
    """Everything one message needs. Derived together so they cannot get out of step."""

    aead: bytes
    nonce: bytes
    header: bytes
    selection: bytes
    counter: int

    @classmethod
    def from_message_key(cls, message_key: bytes, session_id: bytes, counter: int) -> "MessageKeys":
        """Split one 108 byte expansion into the four values it carries."""
        info = hkdf.counter_info(labels.MESSAGE_KEYS, session_id, counter)
        okm = hkdf.expand(message_key, info, MESSAGE_KEYS_BYTES)
        return cls(
            aead=okm[AEAD_SLICE],
            nonce=okm[NONCE_SLICE],
            header=okm[HEADER_SLICE],
            selection=okm[SELECTION_SLICE],
            counter=counter,
        )


def derive_message_key(chain_key: bytes) -> bytes:
    """MK[n] from CK[n]."""
    return hkdf.expand_key(chain_key, labels.MESSAGE_KEY)


def advance(chain_key: bytes) -> bytes:
    """CK[n+1] from CK[n]. One way, which is what forward secrecy rests on."""
    return hkdf.expand_key(chain_key, labels.RATCHET_STEP)


def root_chain_key(shared_secret: bytes) -> bytes:
    """CK[0] from ss."""
    return hkdf.expand_key(shared_secret, labels.CHAIN_INIT)


def header_session_key(shared_secret: bytes) -> bytes:
    """K_hdr_session from ss.

    Session level rather than per message, and that is not an oversight. The counter lives
    inside the header, so the key that unwraps the header cannot itself depend on the
    counter (FORMAT_SPEC.md 3.3).
    """
    return hkdf.expand_key(shared_secret, labels.HEADER_KEY)


def check_session_id(session_id: bytes) -> None:
    if len(session_id) != SESSION_ID_BYTES:
        raise CryptoError(f"Session id must be {SESSION_ID_BYTES} bytes, got {len(session_id)}")


def check_counter(counter: int) -> None:
    if not 0 <= counter <= MAX_COUNTER:
        raise CryptoError(f"Counter {counter} is outside the 24 bits the header holds")


class SendChain:
    """The sender's side. Hands out one set of keys per message and never repeats one.

    There is no way to ask for a counter that has already been used, because there is no
    argument to ask with. The only operation is "next", which is the point.
    """

    def __init__(self, shared_secret: bytes, session_id: bytes, counter: int = 0) -> None:
        check_session_id(session_id)
        check_counter(counter)
        self.session_id = session_id
        self.counter = counter
        self._chain_key = root_chain_key(shared_secret)

    def next_message_keys(self) -> MessageKeys:
        """Derive this message's keys and step the chain forward.

        The order inside this method matters. The next chain key is computed before the
        current one is dropped, and the current one is dropped before returning, so there
        is no path out of here that leaves CK[n] alive.
        """
        if self.counter > MAX_COUNTER:
            raise RatchetLimitError(
                f"This session has sent {MAX_COUNTER + 1} messages, which is every counter "
                f"the 24 bit header field holds. Start a new session."
            )
        message_key = derive_message_key(self._chain_key)
        self._chain_key = advance(self._chain_key)

        keys = MessageKeys.from_message_key(message_key, self.session_id, self.counter)
        self.counter += 1
        return keys

    def chain_key(self) -> bytes:
        """The current chain key, for the state file. Nothing else may call this."""
        return self._chain_key

    @classmethod
    def resume(cls, session_id: bytes, chain_key: bytes, counter: int) -> "SendChain":
        """Rebuild a chain from stored state, mid-session.

        The constructor derives CK[0] from the shared secret, which is the wrong key for
        a session already in progress. This takes the stored chain key as it is. Restoring
        happens through here rather than by reaching into the object, so a change to the
        internals cannot silently produce a chain that looks fine and derives wrong keys.
        """
        check_session_id(session_id)
        check_counter(counter)
        if len(chain_key) != KEY_BYTES:
            raise CryptoError(f"Chain key must be {KEY_BYTES} bytes, got {len(chain_key)}")
        chain = cls.__new__(cls)
        chain.session_id = session_id
        chain.counter = counter
        chain._chain_key = chain_key
        return chain


class RecvChain:
    """The receiver's side. Ratchets forward to reach a counter, and remembers the gaps.

    Messages arrive late, out of order, or not at all, so the receiver has to be able to
    reach counter 7 having only ever seen counter 3. Getting there means stepping the
    chain forward four times, and the keys for 4, 5 and 6 have to be kept in case those
    messages turn up afterwards.

    Two limits, and both of them are load bearing:

        max_skip     how far ahead a single message may drag the chain. Without it, a
                     forged counter of 2^24 - 1 makes the receiver run sixteen million
                     HKDF steps, which is a denial of service that costs the attacker one
                     packet.
        consumed     which counters have already been used. Without it, an attacker can
                     replay a message they captured and the receiver accepts it again.
    """

    def __init__(
        self,
        shared_secret: bytes,
        session_id: bytes,
        max_skip: int = 1000,
        counter: int = 0,
        max_pool: int | None = None,
    ) -> None:
        check_session_id(session_id)
        check_counter(counter)
        if max_skip < 1:
            raise CryptoError(f"max_skip must be at least 1, got {max_skip}")
        self.session_id = session_id
        self.counter = counter
        self.max_skip = max_skip
        # max_skip bounds one message, this bounds the whole session. Without it a stream
        # of messages each a little ahead of the last grows the pool without limit, and
        # every entry is 32 bytes of key material sitting in memory and in the state file.
        self.max_pool = max_skip if max_pool is None else max_pool
        self._chain_key = root_chain_key(shared_secret)
        self._skipped: dict[int, bytes] = {}
        self._consumed: set[int] = set()

    def keys_for(self, counter: int) -> MessageKeys:
        """The keys for one counter, ratcheting forward or looking in the skipped pool.

        Raises RatchetLimitError if the counter is too far ahead, and ReplayError if it
        has already been used. Both are distinct from DecryptError on purpose: they are
        facts about our own state, not about whether the ciphertext was valid, and the
        caller has not attempted a decryption yet.
        """
        check_counter(counter)
        if counter in self._consumed:
            raise ReplayError(f"Counter {counter} was already used in this session")

        if counter < self.counter:
            return self._from_skipped(counter)

        ahead = counter - self.counter
        if ahead >= self.max_skip:
            raise RatchetLimitError(
                f"Counter {counter} is {ahead} ahead of {self.counter}, past the "
                f"max_ratchet_skip of {self.max_skip}. Refusing rather than deriving "
                f"that many keys, which is what makes a forged counter a cheap attack."
            )
        self._ratchet_to(counter)
        return self._take(counter, derive_message_key(self._chain_key))

    def mark_consumed(self, counter: int) -> None:
        """Record that this counter is spent, so a replay of it is refused.

        Called only after the payload has actually decrypted. Marking earlier would let
        anyone burn a counter by sending garbage.
        """
        self._consumed.add(counter)
        self._skipped.pop(counter, None)

    def skipped_count(self) -> int:
        """How many messages are still outstanding, for the state file and for reporting."""
        return len(self._skipped)

    def snapshot(self) -> tuple[bytes, int, dict[int, bytes], set[int]]:
        """Everything the state file needs to rebuild this chain later."""
        return self._chain_key, self.counter, dict(self._skipped), set(self._consumed)

    @classmethod
    def resume(
        cls,
        session_id: bytes,
        chain_key: bytes,
        counter: int,
        skipped: dict[int, bytes],
        consumed: set[int],
        max_skip: int = 1000,
        max_pool: int | None = None,
    ) -> "RecvChain":
        """Rebuild a chain from stored state, mid-session. See SendChain.resume."""
        check_session_id(session_id)
        check_counter(counter)
        if len(chain_key) != KEY_BYTES:
            raise CryptoError(f"Chain key must be {KEY_BYTES} bytes, got {len(chain_key)}")
        chain = cls.__new__(cls)
        chain.session_id = session_id
        chain.counter = counter
        chain.max_skip = max_skip
        chain.max_pool = max_skip if max_pool is None else max_pool
        chain._chain_key = chain_key
        chain._skipped = dict(skipped)
        chain._consumed = set(consumed)
        return chain

    def _ratchet_to(self, counter: int) -> None:
        """Step forward to `counter`, keeping the message key of everything passed over."""
        while self.counter < counter:
            self._skipped[self.counter] = derive_message_key(self._chain_key)
            self._chain_key = advance(self._chain_key)
            self.counter += 1
            self._evict_oldest()

    def _evict_oldest(self) -> None:
        """Drop the oldest outstanding key when the pool is full.

        Oldest first, because a message that has not arrived by now is the least likely to
        still be coming. Dropping it means that message can never be read, which is a real
        loss, but an unbounded pool is a memory exhaustion attack that costs the attacker
        nothing.
        """
        while len(self._skipped) > self.max_pool:
            del self._skipped[min(self._skipped)]

    def _from_skipped(self, counter: int) -> MessageKeys:
        message_key = self._skipped.get(counter)
        if message_key is None:
            # Behind the chain and not in the pool: either already consumed, or dropped
            # when the pool filled. Either way the keys are gone and cannot be rebuilt.
            raise ReplayError(
                f"No keys remain for counter {counter}. It was either already used or it "
                f"fell out of the skipped pool."
            )
        return MessageKeys.from_message_key(message_key, self.session_id, counter)

    def _take(self, counter: int, message_key: bytes) -> MessageKeys:
        """Use the current chain key for this counter, then step past it."""
        self._chain_key = advance(self._chain_key)
        self.counter = counter + 1
        return MessageKeys.from_message_key(message_key, self.session_id, counter)
