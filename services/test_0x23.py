#!/usr/bin/env python3
# services/run_0x23_server.py
# Minimal ECU loop: accepts SF requests and answers 0x23.
# (Responses can be SF or MF; the handler handles that.)

import socket, struct, sys, pathlib
# allow running as a script
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from services.read_memory_by_address import handle_read_memory_by_address
from services.memstore import init_memory
import state

IFACE = "vcan0"
REQ_ID = 0x7E0   # tester -> ECU

def main():
    # init memory & “unlock” so 0x23 is allowed
    init_memory(seed=None)
    state.security_granted_level = 0x04

    # open raw CAN socket and filter to requests ID
    s = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    s.bind((IFACE,))
    can_filter = struct.pack("=II", REQ_ID, 0x7FF)
    s.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER, can_filter)

    print(f"[server] listening on {IFACE}, req-id=0x{REQ_ID:03X} (SF requests only)")

    while True:
        cf = s.recv(16)  # struct can_frame
        can_id, can_dlc, data = struct.unpack("=IB3x8s", cf)
        dlc = can_dlc & 0x0F
        payload = data[:dlc]
        if not payload:
            continue

        pci = payload[0]
        # Single Frame only: low nibble = payload length (0..7)
        if pci > 7:
            # ignore FF/CF/FC; keep it simple
            continue

        L = pci & 0x0F
        uds = payload[1:1+L]
        if not uds:
            continue

        sid = uds[0]
        if sid != 0x23:
            continue

        params = [b for b in uds[1:]]   # handler expects list[int]
        handle_read_memory_by_address(params)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[server] bye")
