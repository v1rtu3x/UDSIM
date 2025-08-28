# UDSIM/io_can.py
import subprocess
from constants import VCAN_INTERFACE

def setup_vcan():
    """Setup the virtual CAN (vcan) interface"""
    try:
        subprocess.run("modprobe can", shell=True, check=True)
        subprocess.run("modprobe vcan", shell=True, check=True)
        subprocess.run("modprobe can_raw", shell=True, check=True)

        result = subprocess.run(f"ip link show {VCAN_INTERFACE}", shell=True, capture_output=True)
        if result.returncode != 0:
            subprocess.run(f"ip link add dev {VCAN_INTERFACE} type vcan", shell=True, check=True)

        subprocess.run(f"ip link set {VCAN_INTERFACE} up", shell=True, check=True)
        print(f"[SETUP] {VCAN_INTERFACE} is now configured and ready")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Setup failed: {e}")
        return False

def start_cangen():
    """Start the cangen tool to generate random CAN traffic"""
    try:
        subprocess.Popen(
            f"cangen {VCAN_INTERFACE} -g 1 -v 0",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"[INFO] Started cangen to generate background CAN traffic on {VCAN_INTERFACE}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to start cangen: {e}")
        return False

def send_can_frame(arb_id, data):
    """Send a CAN frame with specified arbitration ID and data bytes"""
    try:
        data_hex = ''.join([f'{x:02X}' for x in data])
        frame = f"{arb_id:03X}#{data_hex}"
        subprocess.run(f"cansend {VCAN_INTERFACE} {frame}", shell=True, check=True)
        print(f"[SENT] {frame}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to send CAN frame: {e}")
        return False
