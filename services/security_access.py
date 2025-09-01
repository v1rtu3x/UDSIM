# UDSIM/services/security_access.py
from constants import ARB_ID_RESPONSE
from io_can import send_can_frame
from services.negative_response import send_negative_response
from services.secrets_data import FLAG027_1_HEX, FLAG027_2_HEX, FLAG027_3_HEX, FLAG027_4_HEX
from services.send_flag import send_flag
import state
import random

def _params_for_session(sess):
    """Return (mask, nbytes, level_id) based on *session* (not subfunction)."""
    if sess in (0x01, 0x02):   # 1-byte seed/key sessions
        return 0xFF, 1, 1
    if sess in (0x03, 0x04):   # 2-byte seed/key sessions
        return 0xFFFF, 2, 2
    return None, None, None

def _get_last_and_prev(level_id):
    return (state.last_seed_1, state.prev_seed_1) if level_id == 1 else (state.last_seed_2, state.prev_seed_2)

def _set_last_and_prev(level_id, last_val=None, prev_val=None):
    if level_id == 1:
        if last_val is not None: state.last_seed_1 = last_val
        if prev_val is not None: state.prev_seed_1 = prev_val
    else:
        if last_val is not None: state.last_seed_2 = last_val
        if prev_val is not None: state.prev_seed_2 = prev_val

def _pack_be(value, nbytes):
    return [value & 0xFF] if nbytes == 1 else [(value >> 8) & 0xFF, value & 0xFF]

def _fmt_hex(value, nbytes):  # pretty debug
    return f"0x{value:0{nbytes*2}X}"

def handle_security_access(subfunction, data=None):
    """SecurityAccess with session-driven seed/key sizes."""
    sess = state.current_session
    print(f"[DEBUG] Security Access subfunction: 0x{subfunction:02X}, Session: 0x{sess:02X}")

    mask, nbytes, level_id = _params_for_session(sess)
    if mask is None:
        send_negative_response(0x27, 0x7F)  # not supported in this session
        return

    # Only 0x01 (requestSeed) and 0x02 (sendKey) are supported
    if subfunction not in (0x01, 0x02):
        print(f"[WARNING] Unsupported subfunction for our model: 0x{subfunction:02X} (use 0x01/0x02)")
        send_negative_response(0x27, 0x12)
        return

    # ---------------- requestSeed (0x27 0x01) ----------------
    if subfunction == 0x01:
        last_seed, prev_seed = _get_last_and_prev(level_id)

        if sess == 0x01:
            seed = random.randint(0, mask) if last_seed == 0 else (last_seed + 0x02) & mask
            print(f"[SEC][S01] SEED = {_fmt_hex(seed, nbytes)}"
                  + ("" if last_seed == 0 else f"  (prev={_fmt_hex(last_seed, nbytes)} + 0x02)"))
            expected_key = (seed + 0x01) & mask

        elif sess == 0x02:
            seed = random.randint(0, mask)
            expected_key = state.fixed_key_session02_lvl1 if level_id == 1 else state.fixed_key_session02_lvl2
            print(f"[SEC][S02] SEED = {_fmt_hex(seed, nbytes)}  KEY(expect) = {_fmt_hex(expected_key, nbytes)}")

        elif sess == 0x03:
            seed = random.randint(0, mask)
            expected_key = (seed ^ ((seed << 1) & mask)) & mask
            print(f"[SEC][S03] SEED = {_fmt_hex(seed, nbytes)}  KEY(expect) = {_fmt_hex(expected_key, nbytes)}")

        elif sess == 0x04:
            seed = random.randint(0, mask)
            _set_last_and_prev(level_id, prev_val=last_seed)  # keep previous for XOR
            _, prev_now = _get_last_and_prev(level_id)
            expected_key = (seed ^ (prev_now & mask)) & mask
            print(f"[SEC][S04] SEED = {_fmt_hex(seed, nbytes)}  prev={_fmt_hex(prev_now, nbytes)}  "
                  f"KEY(expect) = {_fmt_hex(expected_key, nbytes)}")

        # persist last seed
        _set_last_and_prev(level_id, last_val=seed)

        # DEBUG: return seed + expected key in positive response (non-UDS!)
        seed_bytes = _pack_be(seed, nbytes)
        key_bytes  = _pack_be(expected_key, nbytes)
        payload_len = 2 + nbytes + nbytes
        response = [payload_len, 0x67, 0x01] + seed_bytes + key_bytes
        send_can_frame(ARB_ID_RESPONSE, response)
        print(f"[RESPONSE][DEBUG] 0x67 0x01 SEED={_fmt_hex(seed, nbytes)} KEY={_fmt_hex(expected_key, nbytes)}")
        return

    # ---------------- sendKey (0x27 0x02) ----------------
    last_seed, prev_seed = _get_last_and_prev(level_id)
    if last_seed == 0:
        send_negative_response(0x27, 0x24)  # sequence error
        return

    if not data or len(data) < nbytes:
        print(f"[WARNING] sendKey length wrong for session 0x{sess:02X}: got {len(data) if data else 0}, need {nbytes}")
        send_negative_response(0x27, 0x13)
        return

    key_value = (data[0] & 0xFF) if nbytes == 1 else ((data[0] << 8) | data[1]) & mask

    if sess == 0x01:
        expected_key = (last_seed + 0x01) & mask
    elif sess == 0x02:
        expected_key = state.fixed_key_session02_lvl1 if level_id == 1 else state.fixed_key_session02_lvl2
    elif sess == 0x03:
        expected_key = (last_seed ^ ((last_seed << 1) & mask)) & mask
    elif sess == 0x04:
        expected_key = (last_seed ^ (prev_seed & mask)) & mask
    else:
        send_negative_response(0x27, 0x7F)
        return

    print(f"[DEBUG] sendKey recv={_fmt_hex(key_value, nbytes)} expect={_fmt_hex(expected_key, nbytes)} "
          f"(session 0x{sess:02X}, width={nbytes}B)")

    
    if key_value == expected_key:
        # Mark authenticated
        state.security_level = 0x01
        if sess in (0x01, 0x02, 0x03, 0x04):
            state.security_granted_level = sess
        else:
            # Fallback (shouldn't happen if _params_for_session guarded above)
            state.security_granted_level = max(getattr(state, "security_granted_level", 0), 0x00)
        
        if sess == 0x01: 
            send_flag(FLAG027_1_HEX)
        elif sess == 0x02:
            send_flag(FLAG027_2_HEX)
        elif sess == 0x03:
            send_flag(FLAG027_3_HEX)
        elif sess == 0x04:
            send_flag(FLAG027_4_HEX)

        # Positive response to sendKey
        send_can_frame(ARB_ID_RESPONSE, [0x02, 0x67, subfunction])
        print(f"[SEC] Authenticated 0x10{sess:02X} → security access level = 0x{state.security_granted_level:02X}")
        return
    
    else:
        send_negative_response(0x27, 0x35)
        print("[RESPONSE] Invalid key")
