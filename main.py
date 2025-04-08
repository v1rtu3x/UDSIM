import subprocess
import can
import time
import random
import signal
import sys

# Configuration constants
VCAN_INTERFACE = "vcan0"
ARB_ID_REQUEST = 0x7E0  # Tester → ECU
ARB_ID_RESPONSE = 0x7E8  # ECU → Tester

# Global variables to track current session and security status
current_session = 0x01  # Default to standard session
security_level = 0x00   # Not authenticated by default
last_seed = 0           # Store the last generated seed

# 1. Setup function to initialize the vcan interface
def setup_vcan():
    """Setup the virtual CAN (vcan) interface"""
    try:
        # Load required kernel modules
        subprocess.run("modprobe can", shell=True, check=True)
        subprocess.run("modprobe vcan", shell=True, check=True)
        subprocess.run("modprobe can_raw", shell=True, check=True)
        
        # Check if vcan0 already exists to avoid errors
        result = subprocess.run(f"ip link show {VCAN_INTERFACE}", shell=True, capture_output=True)
        
        if result.returncode != 0:
            # Create vcan interface if it doesn't exist
            subprocess.run(f"ip link add dev {VCAN_INTERFACE} type vcan", shell=True, check=True)
        
        # Bring up the interface
        subprocess.run(f"ip link set {VCAN_INTERFACE} up", shell=True, check=True)
        print(f"[SETUP] {VCAN_INTERFACE} is now configured and ready")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Setup failed: {e}")
        return False

# 2a. Function to start cangen for background traffic
def start_cangen():
    """Start the cangen tool to generate random CAN traffic"""
    try:
        # Run cangen in background with 1000ms gap (-g 1)
        subprocess.Popen(f"cangen {VCAN_INTERFACE} -g 1 -v 0", shell=True, 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[INFO] Started cangen to generate background CAN traffic on {VCAN_INTERFACE}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to start cangen: {e}")
        return False

# 2b. Function to send frames on vcan0
def send_can_frame(arb_id, data):
    """Send a CAN frame with specified arbitration ID and data bytes"""
    try:
        # Format the data for cansend
        data_hex = ''.join([f'{x:02X}' for x in data])
        frame = f"{arb_id:03X}#{data_hex}"
        
        # Send using cansend
        subprocess.run(f"cansend {VCAN_INTERFACE} {frame}", shell=True, check=True)
        print(f"[SENT] {frame}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to send CAN frame: {e}")
        return False

# Function to handle Diagnostic Session Control (0x10)
def handle_session_control(session_type):
    """Handle UDS Diagnostic Session Control service and send appropriate response"""
    global current_session, security_level
    
    print(f"[INFO] Processing Session Control request: 0x{session_type:02X}")
    
    if session_type in [0x01, 0x02, 0x03, 0x04]:
        # Valid session types:
        # 0x01 - Default/Standard Session
        # 0x02 - Programming Session
        # 0x03 - Extended Diagnostic Session
        # 0x04 - Safety System Diagnostic Session
        
        # Update the current session
        current_session = session_type
        
        # P2_server and P2*_server timing parameters (in milliseconds)
        # You can adjust these values as needed
        p2_server = 50
        p2_star_server = 5000
        
        # Format: [length, positive response SID, session type, P2 high byte, P2 low byte, P2* high byte, P2* low byte]
        response_data = [0x06, 0x50, session_type, 
                        (p2_server >> 8) & 0xFF, p2_server & 0xFF,
                        (p2_star_server >> 8) & 0xFF, p2_star_server & 0xFF]
        
        # Send positive response
        send_can_frame(ARB_ID_RESPONSE, response_data)
        print(f"[RESPONSE] Changed to session type: 0x{session_type:02X}")
        
        # Reset security level when changing sessions (as per ISO 14229-1)
        if security_level != 0x00:
            security_level = 0x00
            print("[INFO] Security access reset due to session change")
    else:
        # Invalid session type
        print(f"[WARNING] Invalid session type: 0x{session_type:02X}")
        send_negative_response(0x10, 0x31)  # Request out of range

# Function to handle Security Access (0x27)
def handle_security_access(subfunction, data=None):
    """Handle UDS Security Access service with seed/key mechanism"""
    global security_level, last_seed, current_session
    
    print(f"[DEBUG] Security Access subfunction: 0x{subfunction:02X}, Current session: 0x{current_session:02X}")
    
    # Check session permissions - Security Access typically not allowed in default session
    if current_session != 0x01:
        print("[WARNING] Security Access not allowed in default session")
        send_negative_response(0x27, 0x7F)  # Service not supported in current session
        return
    
    # Check if this is a requestSeed (0x01) or sendKey (0x02)
    if subfunction == 0x01:  # requestSeed
        # Generate a random seed
        seed_value = random.randint(0, 0xFFFFFFFF)
        last_seed = seed_value
        
        # Format seed as 4 bytes
        seed_bytes = [(seed_value >> 24) & 0xFF, 
                      (seed_value >> 16) & 0xFF, 
                      (seed_value >> 8) & 0xFF, 
                      seed_value & 0xFF]
        
        # Response: [length, positive response SID, subfunction, seed bytes...]
        response_data = [0x06, 0x67, subfunction] + seed_bytes
        send_can_frame(ARB_ID_RESPONSE, response_data)
        print(f"[RESPONSE] Sent seed: 0x{seed_value:08X}")
    
    elif subfunction == 0x02:  # sendKey
        if last_seed == 0:
            # No seed was requested first
            send_negative_response(0x27, 0x24)  # Request sequence error
            return
        
        if not data or len(data) < 4:
            # Key data is too short
            print(f"[WARNING] Key data missing or too short: {data}")
            send_negative_response(0x27, 0x13)  # Incorrect message length or format
            return
        
        # Extract key value from data (4 bytes)
        key_value = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
        expected_key = (last_seed + 1) & 0xFFFFFFFF  # Simple algorithm: seed + 1
        
        print(f"[DEBUG] Received key: 0x{key_value:08X}, Expected: 0x{expected_key:08X}")
        
        if key_value == expected_key:
            # Key is correct
            security_level = 0x01  # Set security level to unlocked
            send_can_frame(ARB_ID_RESPONSE, [0x02, 0x67, subfunction])
            print(f"[RESPONSE] Security access granted")
        else:
            # Invalid key
            send_negative_response(0x27, 0x35)  # Invalid key
            print(f"[RESPONSE] Invalid key")
    
    else:
        # Unsupported subfunction
        print(f"[WARNING] Unsupported security subfunction: 0x{subfunction:02X}")
        send_negative_response(0x27, 0x12)  # Subfunction not supported

# Function to handle reset responses
def handle_reset_response(reset_type):
    """Handle UDS ECU Reset service and send appropriate response"""
    if reset_type == 0x01:  # Hard reset
        print("[INFO] Processing Hard Reset request")
        time.sleep(0.5)  # Simulate processing time
        
        # Send response with PCI byte (0x02 = length 2 bytes following)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x01])
    elif reset_type == 0x02:  # Key Off/On reset
        print("[INFO] Processing Key Off/On Reset request")
        time.sleep(0.5)  # Simulate processing time
        
        # Send response with PCI byte (0x02 = length 2 bytes following)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x02])
    elif reset_type == 0x03:  # Soft reset
        print("[INFO] Processing Soft Reset request")
        time.sleep(0.5)  # Simulate processing time
        
        # Send response with PCI byte (0x02 = length 2 bytes following)
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x51, 0x03])
    else:
        # Invalid reset type
        print(f"[WARNING] Invalid reset type: 0x{reset_type:02X}")
        send_negative_response(0x11, 0x31)  # Request out of range

# Function to handle Read Data By ID requests
def handle_read_data_id(data_id):
    """Handle UDS Read Data By ID service and send appropriate response"""
    print(f"[DEBUG] Processing data ID: 0x{data_id:04X}")
    
    if data_id == 0xF190:  # VIN (Vehicle Identification Number)
        print("[INFO] Processing VIN request")
        time.sleep(0.1)  # Small delay

        # Send multi-frame response for VIN
        # First frame: includes service response 0x62, data ID 0xF190, and first bytes of VIN
        send_can_frame(ARB_ID_RESPONSE, [0x10, 0x14, 0x62, 0xF1, 0x90, 0x55, 0x54, 0x43])
        time.sleep(0.125)  # Delay between frames
        
        # Consecutive frames with remaining VIN bytes
        send_can_frame(ARB_ID_RESPONSE, [0x21, 0x6E, 0x4D, 0x55, 0x53, 0x54, 0x57, 0x49])
        time.sleep(0.125)
        send_can_frame(ARB_ID_RESPONSE, [0x22,  0x4E, 0x48, 0x54, 0x42, 0x43, 0x54, 0x46])
    else: 
        # Invalid ID
        print(f"[WARNING] Invalid data ID: 0x{data_id:04X}")
        send_negative_response(0x22, 0x31)  # Request out of range

# Helper function to send negative responses
def send_negative_response(service_id, error_code):
    """Send a UDS negative response with proper PCI"""
    # PCI byte (0x03 = length 3 bytes following) + Negative Response (0x7F) + Service ID + Error Code
    send_can_frame(ARB_ID_RESPONSE, [0x03, 0x7F, service_id, error_code])
    print(f"[RESPONSE] Negative response for service 0x{service_id:02X}: Error 0x{error_code:02X}")

# Handler function to process incoming CAN frames
def handle_can_message(msg):
    """Process incoming CAN messages and handle UDS requests"""
    # Check if this is a request message (0x7E0)
    if msg.arbitration_id != ARB_ID_REQUEST:
        return
    
    # Convert CAN data to a list for easier handling  
    data = list(msg.data)
    
    if len(data) < 2:  # Need at least PCI byte and service ID
        print("[WARNING] Message too short, missing PCI or service ID")
        return
    
    # Extract PCI and calculate expected length
    pci = data[0]
    
    # For single frames, the high nibble should be 0 and low nibble is length
    if (pci & 0xF0) == 0x00:  # Single frame
        data_length = pci & 0x0F
        
        # Verify message length matches PCI
        if len(data) < data_length + 1:  # +1 for PCI byte itself
            print(f"[WARNING] Invalid message length. PCI indicates {data_length} bytes but got {len(data)-1}")
            return
        
        # Extract the service ID (second byte for UDS)
        service_id = data[1]
        
        print(f"[RECV] ID: 0x{msg.arbitration_id:X} PCI: 0x{pci:02X} Service: 0x{service_id:02X} Data: {[hex(b) for b in data]}")
        
        # Handle specific service IDs
        if service_id == 0x10:  # Diagnostic Session Control
            print("[DEBUG] Processing Diagnostic Session Control request")
            if data_length >= 2:  # Need service ID + session type
                session_type = data[2]
                handle_session_control(session_type)
            else:
                send_negative_response(service_id, 0x13)  # Incorrect message length
        elif service_id == 0x11:  # ECU Reset service
            if data_length >= 2:  # Need at least service ID + reset type
                reset_type = data[2]  # Reset type is the 3rd byte (after PCI and service ID)
                handle_reset_response(reset_type)
            else:
                # Not enough data for reset type
                send_negative_response(service_id, 0x13)  # Incorrect message length
        elif service_id == 0x22:  # Read Data By ID
            if data_length >= 3:  # Need service ID + 2 bytes for data ID
                data_id = (data[2] << 8) | data[3]  # Combine two bytes into a 16-bit value
                print(f"[INFO] Read Data ID request: 0x{data_id:04X}")
                handle_read_data_id(data_id)
            else:
                # Not enough data for data ID
                send_negative_response(service_id, 0x13)  # Incorrect message length
        elif service_id == 0x27:  # Security Access
            if data_length >= 2:  # Need service ID + subfunction
                subfunction = data[2]
                # Pass additional data if this is a sendKey request
                if (subfunction % 2) == 0 and data_length >= 6:  # Even subfunction with key data
                    handle_security_access(subfunction, data[3:7])  # Pass the 4-byte key
                else:
                    handle_security_access(subfunction)
            else:
                send_negative_response(service_id, 0x13)  # Incorrect message length
        else:
            # Unsupported service
            send_negative_response(service_id, 0x11)  # Service not supported
    else:
        print(f"[WARNING] Unsupported PCI format: 0x{pci:02X}")
        # Could handle multi-frame messages here if needed

# Signal handler for clean exit
def signal_handler(sig, frame):
    print("\n[INFO] Ctrl+C detected. Shutting down...")
    if 'bus' in globals():
        bus.shutdown()
    sys.exit(0)

# Main function
def main():
    global bus
    
    print("[INFO] Starting UDS ECU simulation with PCI")
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Setup vcan
    if not setup_vcan():
        print("[FATAL] Failed to setup vcan interface. Exiting.")
        return
    
    # Start background CAN traffic
    start_cangen()
    
    # Initialize CAN bus interface
    try:
        bus = can.interface.Bus(channel=VCAN_INTERFACE, bustype='socketcan')
        print(f"[INFO] Listening for UDS requests on {VCAN_INTERFACE}...")
        
        # Main loop - run indefinitely until Ctrl+C
        while True:
            msg = bus.recv(timeout=1.0)
            
            if msg is not None:
                handle_can_message(msg)
    
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")
    finally:
        if 'bus' in locals():
            bus.shutdown()
            print("[INFO] CAN bus shutdown completed")

if __name__ == "__main__":
    main()