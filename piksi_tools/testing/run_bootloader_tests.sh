#!/bin/bash -vxe

# Run test_bootloader.py suite over various versions of the bootloader and
# firmware. This assumes a setup similar to the cards in the HITL rack:
# two Piksies, connected via the UART used for observations, with Black
# Magic Probes plugged into each of them.
# Usage:
#   ./run_bootloader_tests.sh PIKSI1 PIKSI2 BMP1 BMP2

# Check all devices exist
[ -e $1 ]
[ -e $2 ]
[ -e $3 ]
[ -e $4 ]

# Clean up any leftover firmware files from previous runs.
rm -f *.hex
rm -f *.elf

if   [[ "$OSTYPE" == 'darwin14' ]]; then
   DOWNLOAD="curl -O"
elif [[ "$OSTYPE" == 'linux-gnu' ]]; then
   DOWNLOAD="wget"
fi

# List of bootloader firmwares to test.
declare -a btldr=(
  "piksi_bootloader_v0.1.elf"
  "piksi_bootloader_v1.0.elf"
  "piksi_bootloader_v1.1.elf"
  "piksi_bootloader_v1.2.elf"
)

# List of STM firmwares to iterate through for each bootloader test.
# Mapped 1-1 to `nap` array.
declare -a fw=(
  "piksi_v2.3.1_stm_fw_v0.8.hex"
  "piksi_v2.3.1_stm_fw_v0.9-123.hex"
  "piksi_v2.3.1_stm_fw_v0.10.hex"
  "piksi_v2.3.1_stm_fw_v0.11.hex"
  "piksi_v2.3.1_stm_fw_v0.12.hex"
  "piksi_firmware_v0.13.hex"
  "piksi_firmware_v0.14.hex"
  "piksi_firmware_v0.15.hex"
  "piksi_firmware_v0.16.hex"
  "piksi_firmware_v0.17.hex"
  "piksi_firmware_v0.18.hex"
)

# List of NAP firmwares to iterate through for each bootloader test.
# Mapped 1-1 to `stm` array.
declare -a nap=(
  "piksi_v2.3.1_nap_fw_v0.8.hex"
  "piksi_v2.3.1_nap_fw_v0.9-46.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "piksi_v2.3.1_nap_fw_v0.10.hex"
  "swift_nap_v0.12.hex"
  "swift_nap_v0.13.hex"
  "swift_nap_v0.14.hex"
)

# URL prefixes for firmwares.
BTLDR_PREFIX="http://downloads.swiftnav.com/piksi_v2.3.1/bootloader"
FW_PREFIX="http://downloads.swiftnav.com/piksi_v2.3.1/stm_fw"
NAP_PREFIX="http://downloads.swiftnav.com/piksi_v2.3.1/nap_fw"

# Download firmware files.
for i in "${btldr[@]}"
do
   $DOWNLOAD $BTLDR_PREFIX"/$i"
done
for i in "${fw[@]}"
do
   $DOWNLOAD $FW_PREFIX"/$i"
done
for i in "${nap[@]}"
do
   $DOWNLOAD $NAP_PREFIX"/$i"
done

