# UDSIM — Lightweight UDS ECU Simulator (Python)

> A tiny ECU simulator that speaks **UDS over classic CAN** on a Linux **vcan** interface. Handy for testing diagnostic clients without real hardware.

## Table of contents

* [Overview](#overview)
* [Features](#features)
* [Requirements](#requirements)
* [Quick start](#quick-start)
* [Configure the CAN/ISO‑TP stack](#configure-the-caniso‑tp-stack)
* [Run the simulator](#run-the-simulator)
* [Talk to it (examples)](#talk-to-it-examples)
* [Repository layout](#repository-layout)
* [Configuration](#configuration)
* [Service architecture](#service-architecture)
* [Add a new UDS service](#add-a-new-uds-service)

---

## Overview

UDSIM emulates a single ECU that answers **UDS (ISO 14229)** requests transported over **ISO‑TP (ISO 15765‑2)** on a SocketCAN interface. It’s intentionally minimal and easy to extend: each UDS Service is implemented as a small handler you can drop into `services/` and wire up in the dispatcher.

**CTF‑style simulation:** besides being a practical ECU simulator, UDSIM can be used as a **challenge box** for trainings/CTFs. The goal is typically to discover interactions (sessions, NRCs, security access) and extract a *flag* (e.g., via a DID or routine) by chaining standard UDS flows.

Typical uses:

* Develop and test UDS clients without access to a vehicle/ECU
* Reproduce edge cases and negative responses
* Practice diagnostics on a virtual CAN bus (`vcan0`)
* Run **CTF‑style labs** on UDS without real hardware

## Features

* Pure Python; uses Linux **SocketCAN**
* Runs on a **virtual CAN** device (no hardware required)
* Pluggable **service handlers** (implement only what you need)
* Simple in‑memory **ECU state** for simulating DIDs, routines, etc.
* CTF‑friendly design: puzzle‑like flows (sessions, security, routines) to retrieve a **flag**

> Scope: classic CAN only (not CAN‑FD). One ECU instance per process.

## Requirements

* Linux with **SocketCAN** and the **vcan** module
* Python 3.8+ (3.10+ recommended)
* Optional but recommended:

  * **can‑isotp** kernel module (ISO‑TP sockets) if your client speaks UDS over ISO‑TP
  * `can-utils` package for quick testing (`candump`, `cansend`, `isotpsend`, `isotprecv`)

## Quick start

```bash
# 1) Clone
git clone https://github.com/v1rtu3x/UDSIM.git
cd UDSIM

# 2) (Optional) Create a venv
python3 -m venv .venv && source .venv/bin/activate

# 3) Install runtime deps
[ -f requirements.txt ] && pip install -r requirements.txt || pip install python-can

# 4) Bring up a virtual CAN bus
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0

# 5) Run the simulator
python main.py
```

You should see log lines indicating the simulator is listening on `vcan0` and waiting for UDS requests.

## Talk to it with **can-utils**

The easiest way to interact is with the Linux **can-utils** toolkit.

**Listen/receive (ISO‑TP):**

```bash
isotprecv -s 0x7E8 -d 0x7E0 vcan0
```

**Send requests (ISO‑TP, preferred):**

```bash
# TesterPresent (0x3E 00) → positive response 0x7E 00
isotpsend -s 0x7E0 -d 0x7E8 vcan0 3E 00

# DefaultSession (0x10 01) → positive response 0x50 01
isotpsend -s 0x7E0 -d 0x7E8 vcan0 10 01

# ReadDataByIdentifier (0x22) DID 0xF190 (VIN)
isotpsend -s 0x7E0 -d 0x7E8 vcan0 22 F1 90
```

**Send requests with raw CAN frames `cansend`
For short UDS requests (≤ 7 data bytes), you can craft **ISO‑TP Single Frames** and send them directly with `cansend`. The first byte is `0x0L`, where `L` is payload length. Pad to 8 bytes.

```bash
# TesterPresent (2‑byte payload: 3E 00)
# 0x02 = ISO‑TP SF length (2). REQ ID default is 0x7E0.
cansend vcan0 7E0#023E000000000000

# DiagnosticSessionControl Default (10 01)
cansend vcan0 7E0#0210010000000000

# ReadDataByIdentifier F190 (VIN) – 3‑byte payload
cansend vcan0 7E0#0322F19000000000
```

You can **receive** the ECU’s replies either with `candump vcan0` (raw frames) or keep `isotprecv` running to see reassembled ISO‑TP payloads.

> For messages longer than 7 bytes (multi‑frame), prefer `isotpsend` so you don’t have to hand‑craft FF/CF frames.

**Peek raw CAN frames:**

```bash
candump vcan0
```

> Adjust IDs if you changed them in `constants.py` (default REQ 0x7E0, RES 0x7E8).

## Configure the CAN/ISO‑TP stack

Most UDS clients use **ISO‑TP** over CAN. On Linux you can enable an ISO‑TP socket with the kernel module (usually built‑in on 5.10+). To test from the shell, install `can-utils` and use `isotpsend`/`isotprecv`.

If your client uses raw CAN frames instead, you can still observe traffic with `candump`.

## Run the simulator

```bash
# Default run (uses settings from constants.py)
python main.py

# Example: override via environment variables (if supported)
# CAN_IFACE=vcan0 TX_ID=0x7E8 RX_ID=0x7E0 python main.py
```

> If command‑line flags are added later, document them here.

## CTF flavor & gameplay

If you’re using UDSIM for a **CTF/learning challenge**, here’s a suggested storyline:

* Start in **DefaultSession** and try common services; observe **NRCs** to infer prerequisites.
* Switch sessions (e.g., **Extended**), keep **TesterPresent** alive, and enumerate DIDs.
* Defeat a simple **SecurityAccess** (seed/key) to unlock a protected DID/routine.
* Extract a **flag** (e.g., from a hidden DID or routine result).

> Design note: keep everything *nondestructive* and reproducible; the ECU state resets on restart.

## Repository layout

```
UDSIM/
├─ main.py          # entrypoint / event loop
├─ io_can.py        # SocketCAN / ISO‑TP I/O abstraction
├─ dispatcher.py    # maps Service ID → handler in services/
├─ state.py         # ECU state: session, security level, DIDs, etc.
├─ constants.py     # CAN IDs, timeouts, default values
└─ services/        # individual UDS service handlers
   ├─ __init__.py
   ├─ <service_name>.py
   └─ ...
```

```
UDSIM/
├─ main.py          # entrypoint / event loop
├─ io_can.py        # SocketCAN / ISO‑TP I/O abstraction
├─ dispatcher.py    # maps Service ID → handler in services/
├─ state.py         # ECU state: session, security level, DIDs, etc.
├─ constants.py     # CAN IDs, timeouts, default values
└─ services/        # individual UDS service handlers
   ├─ __init__.py
   ├─ <service_name>.py
   └─ ...
```

## Configuration

Edit **`constants.py`** to match your client:

* `CAN_IFACE` — e.g., `"vcan0"`
* `REQ_ID`    — tester→ECU CAN ID (commonly `0x7E0`)
* `RES_ID`    — ECU→tester CAN ID (commonly `0x7E8`)
* Timing: `P2`, `P2_STAR`, etc.
* Defaults for DIDs, routines, VIN string, seeds/keys (if used)

## Services implemented

> **Heads‑up:** the exact set depends on what’s wired in `dispatcher.py`. To print the live list of SIDs, run:
>
> ```bash
> python - <<'PY'
> from dispatcher import SERVICE_TABLE
> print('Implemented SIDs:', ', '.join(hex(sid) for sid in sorted(SERVICE_TABLE)))
> PY
> ```

Commonly included (and recommended for CTFs):

* `0x3E` **TesterPresent**
* `0x10` **DiagnosticSessionControl**
* `0x11` **ECUReset**
* `0x22` **ReadDataByIdentifier** (e.g., VIN `0xF190`, SW version)
* `0x27` **SecurityAccess** (simple seed/key)
* `0x31` **RoutineControl** (flag retrieval routine)

If your local tree differs, update this list to match the `SERVICE_TABLE` output.

## Service architecture

Each UDS Service lives in `services/` as a small function or class that:

1. Parses the request payload
2. Validates session/security pre‑conditions
3. Updates `state` as needed
4. Returns a **positive** (`SID + 0x40`) or **negative** (`0x7F`) response payload

`dispatcher.py` exposes a **service table** that maps the first byte (SID) to the handler. Common services you might implement first:

* `0x3E` TesterPresent
* `0x10` DiagnosticSessionControl
* `0x22` ReadDataByIdentifier (e.g., DID `0xF190` for VIN)
* `0x11` ECUReset
* `0x27` SecurityAccess (stubbed or simple seed/key)
* `0x31` RoutineControl (for demo routines)

`state.py` holds the current session, security level, and any emulated signals/DIDs.

## Add a new UDS service

1. Create `services/my_service.py`:

   ```python
   # services/my_service.py
   from state import ECUState
   from constants import NRC, POS_RESP_OFFSET

   SID = 0x99  # example

   def handle(req: bytes, st: "ECUState") -> bytes:
       # Validate length, session, security, etc.
       if len(req) < 2:
           return bytes([0x7F, SID, NRC.IncorrectMessageLengthOrInvalidFormat])

       # Do the thing…
       subfn = req[1]
       # Update st as needed

       # Return positive response
       return bytes([SID + POS_RESP_OFFSET, subfn])
   ```
2. Register it in `dispatcher.py`:

   ```python
   from services import my_service
   SERVICE_TABLE[my_service.SID] = my_service.handle
   ```
3. Add tests/examples under `examples/` (optional).
