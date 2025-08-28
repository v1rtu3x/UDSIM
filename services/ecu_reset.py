# UDSIM/services/ecu_reset.py
import time
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response

def handle_reset_response(reset_type):
    """Handle UDS ECU Reset service and send appropriate response"""
    if reset_type == 0x01:  # Hard reset
        print("[INFO] Processing Hard Reset request")
        time.sleep(0.5)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x01])

    elif reset_type == 0x02:  # Key Off/On reset
        print("[INFO] Processing Key Off/On Reset request")
        time.sleep(0.5)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x02])

    elif reset_type == 0x03:  # Soft reset
        print("[INFO] Processing Soft Reset request")
        time.sleep(0.5)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x03])

    else:
        print(f"[WARNING] Invalid reset type: 0x{reset_type:02X}")
        send_negative_response(0x11, 0x31)  # Request out of range
