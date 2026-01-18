from typing import List


class MessageBuffer:
    """Buffer that accumulates chunks of bytes and emits messages"""

    def __init__(self, eol: bytes) -> None:
        self.buf: bytearray = bytearray()
        self.eol: bytes = eol

    def append_chunk(self, chunk: bytes) -> List[bytes]:
        self.buf += chunk
        messages: List[bytes] = []
        while True:
            iX = self.buf.find(self.eol)
            if iX == -1:
                break
            messages.append(bytes(self.buf[: iX + len(self.eol)]))
            del self.buf[: iX + len(self.eol)]
        return messages
