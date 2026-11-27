"""A length-prefixed frame: one length byte, then that many payload bytes.

decode_frame parses untrusted input, so it has a Hypothesis test with @example seeds.
"""


class FrameError(ValueError):
    """The bytes are not one well-formed frame."""

    def __init__(self, declared: int | None, actual: int) -> None:
        super().__init__(f"bad frame: length byte {declared}, {actual} payload bytes")


def encode_frame(payload: bytes) -> bytes:
    """Prefix payload with its length. A payload over 255 bytes raises ValueError."""
    return bytes([len(payload)]) + payload


def decode_frame(data: bytes) -> bytes:
    if not data:
        raise FrameError(None, 0)
    length, payload = data[0], data[1:]
    if len(payload) != length:
        raise FrameError(length, len(payload))
    return payload
