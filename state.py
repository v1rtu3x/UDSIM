# UDSIM/state.py
import random

# Global variables to track current session and security status
current_session = 0x01  # Default to standard session
security_level = 0x00   # Not authenticated by default
security_granted_level = 0x00  

# Per-auth-level seed tracking:
# auth 0x01/0x02 -> 1 byte, auth 0x03/0x04 -> 2 bytes
last_seed_1 = 0      # last seed for auth type 0x01/0x02 (1 byte)
prev_seed_1 = 0      # previous seed for session 0x04 logic
last_seed_2 = 0      # last seed for auth type 0x03/0x04 (2 bytes)
prev_seed_2 = 0      # previous seed for session 0x04 logic

# Fixed keys for session type 0x02 (constant for the lifetime of the program)
fixed_key_session02_lvl1 = random.randint(0x00, 0xFF)      # 1 byte key
fixed_key_session02_lvl2 = random.randint(0x0000, 0xFFFF)  # 2 byte key
