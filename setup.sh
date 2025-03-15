#!/bin/bash

# Check if the script is run with root privileges
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run the script as root or use sudo."
  exit 1
fi

# Load the can kernel modules if not already loaded
modprobe can
modprobe vcan
modprobe can_raw

# Set up the virtual CAN interface vcan0
ip link add dev vcan0 type vcan
ip link set vcan0 up
cangen vcan0

# Check if the interface was successfully created and is up
if ip link show vcan0 &>/dev/null; then
  echo "vcan0 is set up and connected successfully."
else
  echo "Failed to set up vcan0."
fi

