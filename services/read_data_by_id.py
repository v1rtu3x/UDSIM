# UDSIM/services/read_data_by_id.py
import time
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response

def handle_read_data_id(data_id):
    """Handle UDS Read Data By ID service and send appropriate response"""
    print(f"[DEBUG] Processing data ID: 0x{data_id:04X}")

    if data_id == 0xF190:  # VIN (Vehicle Identification Number)
        print("[INFO] Processing VIN request")
        time.sleep(0.1)

        send_can_frame(ARB_ID_RESPONSE, [0x10, 0x14, 0x62, 0xF1, 0x90, 0x55, 0x54, 0x43])
        time.sleep(0.125)
        send_can_frame(ARB_ID_RESPONSE, [0x21, 0x6E, 0x4D, 0x55, 0x53, 0x54, 0x57, 0x49])
        time.sleep(0.125)
        send_can_frame(ARB_ID_RESPONSE, [0x22,  0x4E, 0x48, 0x54, 0x42, 0x43, 0x54, 0x46])

    else:
        print(f"[WARNING] Invalid data ID: 0x{data_id:04X}")
        send_negative_response(0x22, 0x31)  # Request out of range
