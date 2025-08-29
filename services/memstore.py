# UDSIM/services/memstore.py
import random
from typing import Dict, List, Tuple

from constants import VIN
from services.secrets_data import S3CR3T1_HEX, S3CR3T2_HEX, FLAG023_HEX

# Address -> Data byte
MEM: Dict[int, int] = {}
_INITED = False

# Where we ended up placing each blob (for debugging)
PLACED: Dict[str, Tuple[int, int]] = {}  # name -> (start, length)

def _hex_to_bytes(s: str) -> bytes:
    s = " ".join(s.split())  # normalize whitespace
    if not s:
        return b""
    return bytes.fromhex(s)

def _vin_padded() -> bytes:
    if len(VIN) != 17:
        raise ValueError(f"VIN must be 17 chars, got {len(VIN)}")
    return b"\x00"*64 + VIN.encode("ascii") + b"\x00"*64

def _build_blobs() -> List[Tuple[str, bytes]]:
    blobs = [
        ("VIN_PADDED", _vin_padded()),
        ("s3cr3t1", _hex_to_bytes(S3CR3T1_HEX)),
        ("s3cr3t2", _hex_to_bytes(S3CR3T2_HEX)),
        ("flag023", _hex_to_bytes(FLAG023_HEX)),
    ]
    # sanity checks
    for name, blob in blobs:
        if not blob:
            raise ValueError(f"Blob {name} is empty. Did you paste the hex?")
    return blobs

def _fill_random_64k(rng: random.Random) -> None:
    MEM.clear()
    for addr in range(0x10000):
        MEM[addr] = rng.randrange(0, 256)

def _place_non_overlapping(blobs: List[Tuple[str, bytes]], rng: random.Random) -> None:
    """Place each blob contiguously somewhere in 0x0000..0xFFFF with no overlap."""
    occupied = bytearray(0x10000)  # 0 = free, 1 = used
    PLACED.clear()

    def fits(at: int, length: int) -> bool:
        if at + length > 0x10000:   # do not wrap; choose another slot
            return False
        return all(occupied[at+i] == 0 for i in range(length))

    def mark(at: int, length: int) -> None:
        for i in range(length):
            occupied[at+i] = 1

    # Place in random order so they land in random regions overall
    to_place = blobs[:]
    rng.shuffle(to_place)

    for name, blob in to_place:
        L = len(blob)
        # Try a randomized scan of possible starting positions
        candidates = list(range(0, 0x10000 - L))
        rng.shuffle(candidates)
        placed = False
        for at in candidates:
            if fits(at, L):
                # Write bytes and record
                for i, b in enumerate(blob):
                    MEM[at + i] = b
                mark(at, L)
                PLACED[name] = (at, L)
                print(f"[memstore] Placed {name} at 0x{at:04X}..0x{at+L-1:04X} (len={L})")
                placed = True
                break
        if not placed:
            raise RuntimeError(f"Could not place blob {name} (len={L}) without overlap")

def init_memory(seed: int | None = None) -> None:
    """Create 64 KiB random map, then randomly place VIN_PADDED + s3cr3t1 + s3cr3t2 + flag023."""
    global _INITED
    if _INITED:
        return
    rng = random.Random(seed)
    blobs = _build_blobs()
    _fill_random_64k(rng)
    _place_non_overlapping(blobs, rng)
    _INITED = True
    print(f"[memstore] Initialized 64 KiB (seed={seed}); placed: {', '.join(PLACED.keys())}")

def get_bytes(address: int, size: int) -> List[int]:
    """Return 'size' bytes starting at 'address' (wrap around 0xFFFF->0x0000)."""
    if not _INITED:
        init_memory()
    out = []
    a = address & 0xFFFF
    for i in range(size):
        out.append(MEM[(a + i) & 0xFFFF])
    return out
