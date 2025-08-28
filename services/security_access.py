# UDSIM/services/security_access.py
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response
import state
import time
import random

def handle_security_access(subfunction, data=None):
    """Handle UDS Security Access service with seed/key mechanism"""
    print(f"[DEBUG] Security Access subfunction: 0x{subfunction:02X}, Current session: 0x{state.current_session:02X}")

    # Check session permissions - Security Access typically not allowed in default session
    if state.current_session != 0x01:
        print("[WARNING] Security Access not allowed in default session")
        send_negative_response(0x27, 0x7F)  # Service not supported in current session
        return

    if subfunction == 0x01:  # requestSeed
        seed_value = random.randint(0, 0xFFFFFFFF)
        state.last_seed = seed_value

        seed_bytes = [(seed_value >> 24) & 0xFF,
                      (seed_value >> 16) & 0xFF,
                      (seed_value >> 8) & 0xFF,
                      seed_value & 0xFF]

        response_data = [0x06, 0x67, subfunction] + seed_bytes
        time.sleep(0.5)
        send_can_frame(ARB_ID_RESPONSE, response_data)
        print(f"[RESPONSE] Sent seed: 0x{seed_value:08X}")

    elif subfunction == 0x02:  # sendKey
        if state.last_seed == 0:
            send_negative_response(0x27, 0x24)  # Request sequence error
            return

        if not data or len(data) < 4:
            print(f"[WARNING] Key data missing or too short: {data}")
            send_negative_response(0x27, 0x13)  # Incorrect message length or format
            return

        key_value = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
        expected_key = (state.last_seed + 1) & 0xFFFFFFFF  # Simple algorithm: seed + 1

        print(f"[DEBUG] Received key: 0x{key_value:08X}, Expected: 0x{expected_key:08X}")

        if key_value == expected_key:
            state.security_level = 0x01  # Set security level to unlocked
            time.sleep(0.5)
            send_can_frame(ARB_ID_RESPONSE, [0x02, 0x67, subfunction])
            print(f"[RESPONSE] Security access granted")
        else:
            send_negative_response(0x27, 0x35)  # Invalid key
            print(f"[RESPONSE] Invalid key")

    else:
        print(f"[WARNING] Unsupported security subfunction: 0x{subfunction:02X}")
        send_negative_response(0x27, 0x12)  # Subfunction not supported
