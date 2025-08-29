# UDSIM/services/read_memory_by_address.py
from __future__ import annotations

import time
from typing import List

from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response
from services.memstore import init_memory, get_bytes
import state

# NRC constants
NRC_INCORRECT_MESSAGE_LENGTH = 0x13
NRC_RESPONSE_TOO_LONG        = 0x14
NRC_REQUEST_OUT_OF_RANGE     = 0x31
NRC_SECURITY_ACCESS_DENIED   = 0x33

SERVICE_ID   = 0x23
POS_RESP_SID = 0x63

# Classic ISO-TP (8-byte CAN) length limit is 4095 bytes of UDS payload per message.
# Our positive response payload is [0x63] + data ⇒ data ≤ 4094 bytes.
MAX_DATA_PER_MSG = 4094

# Optional tiny inter-frame gap for CFs if you want to be gentle on tools (seconds)
CF_GAP = 0.0  # set to e.g. 0.001 for 1 ms between CFs

def _fmt_hex(v: int, nbytes: int) -> str:
    return f"0x{v:0{nbytes*2}X}"

def _send_isotp_positiveResponse(data: List[int]) -> None:
    """
    Send a UDS positive response (0x63 + data) via ISO-TP.
    - Single Frame if len(payload) <= 7
    - Otherwise First Frame + Consecutive Frames (streams CFs; does not wait for FC)
    """
    # Build UDS payload first
    uds = [POS_RESP_SID] + data
    total = len(uds)

    if total <= 7:
        # SF: [len][UDS...]
        frame = [total] + uds
        send_can_frame(ARB_ID_RESPONSE, frame)
        return

    # --- Multi-frame transmit path (classic CAN, 8-byte frames) ---
    # First Frame: PCI = 0x10 | (length high nibble), then length low byte,
    # followed by first 6 bytes of UDS payload.
    if total > 0xFFF:  # ISO-TP classic max length (12-bit)
        # (should not happen if caller enforces MAX_DATA_PER_MSG)
        raise ValueError("UDS payload too large for ISO-TP classic")

    ff_pci0 = 0x10 | ((total >> 8) & 0x0F)
    ff_pci1 = total & 0xFF
    first_data = uds[:6]
    send_can_frame(ARB_ID_RESPONSE, [ff_pci0, ff_pci1] + first_data)

    # Remaining bytes go in CF frames, 7 bytes per CF
    remaining = uds[6:]
    sn = 1  # sequence number 1..15 wraps
    while remaining:
        chunk = remaining[:7]
        remaining = remaining[7:]
        pci = 0x20 | (sn & 0x0F)  # CF with sequence number
        send_can_frame(ARB_ID_RESPONSE, [pci] + chunk)
        sn = 1 if sn == 15 else sn + 1
        if CF_GAP > 0:
            time.sleep(CF_GAP)

def handle_read_memory_by_address(params: list[int]) -> None:
    """
    params: UDS payload bytes AFTER the service id (i.e., starts with ALFID).
            Example: for request "23 13 00 F0 00 04", params == [0x13, 0x00, 0xF0, 0x00, 0x04].
    Replies with single-frame or multi-frame ISO-TP positive response.
    """
    # Security gate (match your sim’s policy)
    if getattr(state, "security_granted_level", 0) != 0x04:
        send_negative_response(SERVICE_ID, NRC_SECURITY_ACCESS_DENIED)
        return

    # Need ALFID at least
    if not params:
        send_negative_response(SERVICE_ID, NRC_INCORRECT_MESSAGE_LENGTH)
        return

    alfid = params[0] & 0xFF
    size_len = (alfid >> 4) & 0x0F   # HIGH nibble = memorySize length in BYTES
    addr_len = alfid & 0x0F          # LOW  nibble = memoryAddress length in BYTES

    if size_len == 0 or addr_len == 0:
        send_negative_response(SERVICE_ID, NRC_INCORRECT_MESSAGE_LENGTH)
        return

    expected_len = 1 + addr_len + size_len
    if len(params) != expected_len:
        send_negative_response(SERVICE_ID, NRC_INCORRECT_MESSAGE_LENGTH)
        return

    # Decode address (big-endian)
    p = 1
    address = 0
    for _ in range(addr_len):
        address = (address << 8) | (params[p] & 0xFF)
        p += 1

    # Decode size (big-endian)
    size = 0
    for _ in range(size_len):
        size = (size << 8) | (params[p] & 0xFF)
        p += 1

    # Semantic checks
    if size == 0:
        send_negative_response(SERVICE_ID, NRC_REQUEST_OUT_OF_RANGE)
        return
    if size > MAX_DATA_PER_MSG:
        # Would exceed classic ISO-TP message length
        send_negative_response(SERVICE_ID, NRC_RESPONSE_TOO_LONG)
        return

    # Prepare data
    init_memory()
    try:
        data = get_bytes(address, size)  # list[int] or bytes-like
        if isinstance(data, (bytes, bytearray)):
            data = list(data)
        if not isinstance(data, list) or len(data) != size:
            send_negative_response(SERVICE_ID, NRC_REQUEST_OUT_OF_RANGE)
            return
        for b in data:
            if not (0 <= int(b) <= 0xFF):
                send_negative_response(SERVICE_ID, NRC_REQUEST_OUT_OF_RANGE)
                return
    except Exception:
        send_negative_response(SERVICE_ID, NRC_REQUEST_OUT_OF_RANGE)
        return

    # Send SF or MF as needed
    _send_isotp_positiveResponse(data)

    # Debug log
    print(
        f"[0x23] addr={_fmt_hex(address, addr_len)} size={size} "
        f"-> sent {'MF' if (1 + len(data)) > 7 else 'SF'} response"
    )
