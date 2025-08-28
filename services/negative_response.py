# UDSIM/services/negative_response.py
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame

def send_negative_response(service_id, error_code):
    """Send a UDS negative response with proper PCI"""
    # PCI byte (0x03 = length 3 bytes following) + Negative Response (0x7F) + Service ID + Error Code
    send_can_frame(ARB_ID_RESPONSE, [0x03, 0x7F, service_id, error_code])
    print(f"[RESPONSE] Negative response for service 0x{service_id:02X}: Error 0x{error_code:02X}")
