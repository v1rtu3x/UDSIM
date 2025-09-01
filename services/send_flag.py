# UDSIM/services/send_flag.py
# Universal helper: call send_flag(FLAG) and it will send the bytes as
# UDS-style single frames on the ECU response ID.

from typing import Iterable, Union
from constants import ARB_ID_FLAG
from io_can import send_can_frame

# We'll tag each frame with a custom SID so it stands out in candump.
_SID_FLAG = 0x6F  # change if you prefer a different marker

def _to_bytes(flag: Union[str, bytes, bytearray, Iterable[int]]) -> bytes:
    """
    Normalize input to bytes.
    - str: space/comma/newline-separated hex tokens, e.g. "31 74 5F ..." or "0x31,0x74"
    - bytes/bytearray: used as-is
    - iterable[int]: values are masked to 0..255
    """
    if isinstance(flag, (bytes, bytearray)):
        return bytes(flag)

    if isinstance(flag, str):
        txt = flag.replace(",", " ")
        out = bytearray()
        for tok in txt.split():
            t = tok.strip().lower()
            if not t:
                continue
            if t.startswith("0x"):
                t = t[2:]
            out.append(int(t, 16) & 0xFF)
        return bytes(out)

    # Iterable of integers
    return bytes((int(b) & 0xFF) for b in flag)

def send_flag(flag: Union[str, bytes, bytearray, Iterable[int]]) -> int:
    """
    Send FLAG over CAN as one or more UDS single frames on ARB_ID_RESPONSE.

    Each frame: [ PCI=0x0N , SID(=_SID_FLAG) , up to 6 data bytes ]
      - N = 1 (SID) + len(chunk)  -> max chunk size is 6 bytes
      - No ISO-TP multi-frame; just convenient single-frame chunks.

    Returns: number of CAN frames sent.
    """
    data = _to_bytes(flag)

    # Empty payload? send just the SID marker so something is visible.
    if len(data) == 0:
        send_can_frame(ARB_ID_FLAG, [0x01, _SID_FLAG])
        return 1

    sent = 0
    max_chunk = 6
    for i in range(0, len(data), max_chunk):
        chunk = data[i:i + max_chunk]
        pci = (1 + len(chunk)) & 0x0F           # SID(1) + chunk_len
        frame = [pci, _SID_FLAG] + list(chunk)  # e.g., 0x0N, 0x6F, <data...>
        send_can_frame(ARB_ID_FLAG, frame)
        sent += 1
    return sent
