# UDSIM/services/clear_dtc.py
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response
import state

def handle_clear_dtc(params: list[int]) -> None:
    """
    UDS 0x14 ClearDiagnosticInformation.
      - Request: SID(0x14) + groupOfDTC (3 bytes)
      - Positive response: 0x54 (no parameters)
    Policy:
      - Only allowed after 0x27 auth in session 0x03 (state.security_granted_level == 0x03)
      - If groupOfDTC == 0xFFFFFF (clear ALL): send 0x54, then send a second response (configurable)
      - Else (specific DTC / specific group): send only 0x54
    """
    # Gate: must be authenticated specifically in session 0x03
    if getattr(state, "security_granted_level", 0x00) < 0x03:
        send_negative_response(0x14, 0x33)  # SecurityAccessDenied
        return

    # Format check: exactly 3 param bytes
    if not params or len(params) != 3:
        send_negative_response(0x14, 0x13)  # IncorrectMessageLengthOrInvalidFormat
        return

    group = ((params[0] & 0xFF) << 16) | ((params[1] & 0xFF) << 8) | (params[2] & 0xFF)

    # Always send the positive response for valid format
    send_can_frame(ARB_ID_RESPONSE, [0x01, 0x54])
    print(f"[0x14] Clear DTCs request, group=0x{group:06X} -> sent 0x54")

    # If it's "clear ALL" (0xFFFFFF), also send the extra response (you define the bytes)
    if group == 0xFFFFFF:
        print(f"[0x14] Clear ALL DTCs -> sent 0x54")
