# UDSIM/dispatcher.py
from constants import ARB_ID_REQUEST
from services.session_control import handle_session_control
from services.ecu_reset import handle_reset_response
from services.read_data_by_id import handle_read_data_id
from services.security_access import handle_security_access
from services.negative_response import send_negative_response
from services.read_memory_by_address import handle_read_memory_by_address

def handle_can_message(msg):
    """Process incoming CAN messages and handle UDS requests"""
    # Enforce tester -> ECU arbitration ID (0x7E0)
    if msg.arbitration_id != ARB_ID_REQUEST:
        # print(f"[IGNORE] Unexpected CAN ID 0x{msg.arbitration_id:X}; "
              # f"expecting tester→ECU ID 0x{ARB_ID_REQUEST:X}")
        return 0

    data = list(msg.data)
    if len(data) < 2:
        print("[WARNING] Message too short, missing PCI or service ID")
        return

    pci = data[0]

    if (pci & 0xF0) == 0x00:  # Single frame
        data_length = pci & 0x0F

        if len(data) < data_length + 1:
            # print(f"[WARNING] Invalid message length. PCI indicates {data_length} bytes but got {len(data)-1}")
            return

        service_id = data[1]
        print(f"[RECV] ID: 0x{msg.arbitration_id:X} PCI: 0x{pci:02X} Service: 0x{service_id:02X} Data: {[hex(b) for b in data]}")

        if service_id == 0x10:  # Diagnostic Session Control
            print("[DEBUG] Processing Diagnostic Session Control request")
            if data_length >= 2:
                handle_session_control(data[2])
            else:
                send_negative_response(service_id, 0x13)

        elif service_id == 0x11:  # ECU Reset
            if data_length >= 2:
                handle_reset_response(data[2])
            else:
                send_negative_response(service_id, 0x13)

        elif service_id == 0x22:  # Read Data By ID
            if data_length >= 3:
                data_id = (data[2] << 8) | data[3]
                print(f"[INFO] Read Data ID request: 0x{data_id:04X}")
                handle_read_data_id(data_id)
            else:
                send_negative_response(service_id, 0x13)

        elif service_id == 0x27:  # Security Access
            if data_length >= 2:
                subfunction = data[2]
                if (subfunction % 2) == 0:
                    # sendKey: forward exactly the remaining bytes after [SID, subfn]
                    payload_len = max(0, data_length - 2)
                    key_bytes = data[3:3 + payload_len]
                    handle_security_access(subfunction, key_bytes)
                else:
                    # requestSeed: no payload
                    handle_security_access(subfunction)
            else:
                send_negative_response(service_id, 0x13)

        elif service_id == 0x23:  # ReadMemoryByAddress
            if data_length >= 2:
                params = data[2: 1 + data_length]  # bytes after SID
                handle_read_memory_by_address(params)
            else:
                send_negative_response(service_id, 0x13)

        else:
            send_negative_response(service_id, 0x11)
    else:
        print(f"[WARNING] Unsupported PCI format: 0x{pci:02X}")
        # Multi-frame requests could be implemented here if needed