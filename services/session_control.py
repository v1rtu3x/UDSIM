# UDSIM/services/session_control.py
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response
import state

def handle_session_control(session_type):
    """Handle UDS Diagnostic Session Control service and send appropriate response"""
    print(f"[INFO] Processing Session Control request: 0x{session_type:02X}")

    if session_type in [0x01, 0x02, 0x03, 0x04]:
        # Update the current session
        state.current_session = session_type

        # P2_server and P2*_server timing parameters (in milliseconds)
        p2_server = 50
        p2_star_server = 5000

        # [length, positive SID, session type, P2 hi, P2 lo, P2* hi, P2* lo]
        response_data = [0x06, 0x50, session_type,
                         (p2_server >> 8) & 0xFF, p2_server & 0xFF,
                         (p2_star_server >> 8) & 0xFF, p2_star_server & 0xFF]

        send_can_frame(ARB_ID_RESPONSE, response_data)
        print(f"[RESPONSE] Changed to session type: 0x{session_type:02X}")

        # Reset security level when changing sessions (as per ISO 14229-1)
        if state.security_level != 0x00:
            state.security_level = 0x00
            print("[INFO] Security access reset due to session change")
    else:
        print(f"[WARNING] Invalid session type: 0x{session_type:02X}")
        send_negative_response(0x10, 0x31)  # Request out of range
