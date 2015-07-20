#!/bin/bash

# Usage: ./gcore_on_fail.sh <firmeare.elf> \
#                                   <piksi_dev> <bmp_dev> \
#                                   <seconds-to-sleep>
#
# Intended to be called from HITL log capture:
# if [ -e $MD_EXTERNAL_RESOURCES_LOCKED_BMP1 ]; then
#   ./gcore_on_fail.sh ../../piksi_firmware_$GIT_DESCRIBE.elf \
#                      $MD_EXTERNAL_RESOURCES_LOCKED_PORT1 \
#                      $MD_EXTERNAL_RESOURCES_LOCKED_BMP1 \
#                      $SECONDS
# fi

set -e

[ -e $1 ]
[ -e $2 ]
[ -e $3 ]

# Find serial number from Piksi device name
export PIKSI=`echo $2 | egrep -o "PK[0-9]{4}"`

gdb-multiarch -batch -nx \
              -ex "tar ext $3" \
              -x coredump.gdb \
              -ex "set gcore-file-name core-$PIKSI" \
              -ex "mon jtag 4 5 6" \
              -ex "att 1" \
              -ex "run" \
              $1 \
              &>gdblog.$PIKSI &

sleep 1
trap 'kill $(jobs -p)' SIGINT SIGTERM EXIT
tail -f gdblog.$PIKSI | grep "core dumped" &

sleep $4

