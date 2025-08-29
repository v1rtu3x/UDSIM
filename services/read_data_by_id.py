# UDSIM/services/read_data_by_id.py
import time
from constants import ARB_ID_RESPONSE, VIN
from io_can import send_can_frame
from services.negative_response import send_negative_response
import state

def handle_read_data_id(data_id):
    print(f"[DEBUG] Processing data ID: 0x{data_id:04X}")

    if state.security_granted_level < 0x02:
        print("[WARN] Hard Reset denied in session 0x01: security level not sufficient")
        send_negative_response(0x22, 0x33)  # SecurityAccessDenied
        return

    elif data_id == 0xF190:  # VIN
        if len(VIN) != 17:
            print("[ERROR] VIN must be 17 ASCII chars")
            send_negative_response(0x22, 0x31); return

        payload = [0x62, 0xF1, 0x90] + list(VIN.encode("ascii"))  # total = 3 + 17 = 20 bytes
        # First Frame (FF): 0x10, total-length (0x14), then 6 bytes
        send_can_frame(ARB_ID_RESPONSE, [0x10, 0x14] + payload[:6])
        time.sleep(0.1)
        # Consecutive Frames
        send_can_frame(ARB_ID_RESPONSE, [0x21] + payload[6:13])
        time.sleep(0.1)
        send_can_frame(ARB_ID_RESPONSE, [0x22] + payload[13:20])

    else:
        print(f"[WARNING] Invalid data ID: 0x{data_id:04X}")
        send_negative_response(0x22, 0x31)
