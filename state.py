# UDSIM/state.py

# Global variables to track current session and security status
current_session = 0x01  # Default to standard session
security_level = 0x00   # Not authenticated by default
last_seed = 0           # Store the last generated seed
