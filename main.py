# UDSIM/main.py
import sys
import can
from io_can import setup_vcan, start_cangen
from constants import VCAN_INTERFACE
from dispatcher import handle_can_message
from services.memstore import init_memory
from services.test_0x23 import Test


def main():
    print("[INFO] Starting UDS ECU simulation with PCI")

    if not setup_vcan():
        print("[FATAL] Failed to setup vcan interface. Exiting.")
        return

    # Launch traffic generator (if your helper starts a subprocess/thread, consider adding a matching stop later)
    init_memory(seed=None)
    start_cangen()
    
    bus = None
    try:
        bus = can.interface.Bus(channel=VCAN_INTERFACE, bustype='socketcan')
        Test()
        print(f"[INFO] Listening for UDS requests on {VCAN_INTERFACE}... Press Ctrl+C to exit.")
        while True:
            msg = bus.recv(timeout=1.0)  # 1s timeout lets Ctrl+C be handled promptly
            if msg is not None:
                handle_can_message(msg)

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received. Shutting down cleanly...")

    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")

    finally:
        if bus is not None:
            try:
                bus.shutdown()
                print("[INFO] CAN bus shutdown completed")
            except Exception as e:
                print(f"[WARN] Error during CAN bus shutdown: {e}")
        # If start_cangen() creates a background process/thread, stop it here
        # e.g., stop_cangen()  # implement if needed

if __name__ == "__main__":
    main()
