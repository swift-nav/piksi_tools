#!/bin/bash

# Usage: ./grab_core_on_segfault.sh <piksi_dev> <bmp_dev> <seconds-to-sleep>
#
# Intended to be called from HITL log capture:
# if [ -e $MD_EXTERNAL_RESOURCES_LOCKED_BMP1 ]; then
#   ./grab_core_on_segfault.sh $MD_EXTERNAL_RESOURCES_LOCKED_PORT1 \
#                              $MD_EXTERNAL_RESOURCES_LOCKED_BMP1 \
#                              $SECONDS
# fi

set -e

[ -e $1 ]
[ -e $2 ]

# Find serial number from Piksi device name
export PIKSI=`echo $1 | egrep -o "PK[0-9]{4}"`

gdb-multiarch -batch -nx \
              -ex "tar ext $2" \
              -ex "source coredump3.py" \
              -ex "set gcore-file-name core-$PIKSI" \
              -ex "mon jtag 4 5 6" \
              -ex "att 1" \
              -ex "run" \
              ~/Projects/piksi_firmware/build/piksi_firmware.elf \
              &>gdblog.$PIKSI &

sleep 1
trap 'kill $(jobs -p)' SIGINT SIGTERM EXIT
tail -f gdblog.$PIKSI | grep "core dumped" &

sleep $3

