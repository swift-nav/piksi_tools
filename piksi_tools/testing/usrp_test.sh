#!/bin/bash -vxe
# Copyright (C) 2015 Swift Navigation Inc.
# Contact: Bhaskar Mookerji <mookerji@swiftnav.com>
#          Henry Hallam <henry@swiftnav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE

# Script for running hardware-in-the-loop (HITL) test on prerecorded
# USRP data. Given a firmware and nap image, bootloads in-parallel a
# set of Piksi's, starts recordings in parallel, and kicks off the
# USRP recording. Also:
#
# * The list of devices to program is in piksi_tools/testing/devices.txt.
# * Programming logs are written to directories PK<serial number>/, where
#   the serial number is the Piksi serial number parsed from the USB
#   device path. Piksi with device ID 1229 will write settings,
#   session logs, and SBP serial link recordings to PK1229/. This stuff
#   persisted to S3 and cleaned up between sessions.
#
# Invoke this script via:
# PLAYBACK_DURATION=300 GIT_DESCRIBE=v0.19-rc0-52-gd7f62c0 HDL_GIT_DESCRIBE=v0.15-rc0 bash piksi_tools/testing/usrp_test.sh -x run

CWD=$(pwd)
TEST=$CWD/piksi_tools/testing
DEVICES=$TEST/devices.txt

VENV_NAME=testing_env
VENV_PATH=$VENV_NAME/bin

# Bootload/programming/diagnostics timeout of 2 minutes.
BOOTLOAD_TIMEOUT=120

set -x
set -e

function cleanup () {
    echo "Cleaning up...."
    kill "$(ps -s $$ -o pid=)"
    sleep 2
    kill -9 "$(ps -s $$ -o pid=)"
}

trap cleanup SIGINT

function check_args () {
    [ -e piksi_firmware_"$GIT_DESCRIBE".hex ]
    [ -e swift_nap_"$HDL_GIT_DESCRIBE".hex ]
}

function setup_shit () {
    # Setup a bunch of Python stuff and other dependencies.
    echo "Setting up environment...."
    virtualenv "$VENV_NAME"
    source "$VENV_PATH"/activate
    pip install -r requirements.txt
    python setup.py install
    pip install pyudev
    cd "$TEST"
    make hub_ctrl
    cd "$CWD"
}

function program_device () {
    echo "Preparing devices for test..."
    echo
    cd "$TEST"
    ./cycle_device_power.py "$1"
    sleep 2
    cd "$CWD"
    # Program application firmware
    timeout "$BOOTLOAD_TIMEOUT" python piksi_tools/bootload.py -e -s -p "$1" piksi_firmware_"$GIT_DESCRIBE".hex &>> "$2"
    cd "$TEST"
    ./cycle_device_power.py "$1"
    sleep 2
    cd "$CWD"
    # Program NAP firmware
    timeout "$BOOTLOAD_TIMEOUT" python piksi_tools/bootload.py -m -p "$1" swift_nap_"$HDL_GIT_DESCRIBE".hex &>> "$2"
}

function make_full_version () {
    # Make parseable file for expected firmware and nap versions.
    [ -e VERSION ]
    [ -e HDL_VERSION ]
    echo "GIT_DESCRIBE=fw:$(egrep -o "[^=]+$" VERSION) hdl:$(egrep -o "[^=]+$" HDL_VERSION)" > FULL_VERSION
    echo "$(egrep -o "[^=]+$" FULL_VERSION)" > version.yaml
}

function check_device_settings () {
    # After the devices have been programmed, asserts that the devices
    # have been programmed with the right firmware and nap versions by
    # reading their settings.
    export HDL_"$(cat HDL_VERSION)"
    cd "$CWD"
    timeout "$BOOTLOAD_TIMEOUT" python piksi_tools/diagnostics.py -p "$1" -o "$2"
    cat version.yaml
    cd "$TEST"
    ../../$VENV_PATH/python check_device_details.py -d ../../"$2" -v ../../version.yaml
    if [[ $? -eq 1 ]]
    then
        echo "Check device details failed!"
    fi
}

function start_scenario () {
    # Invoke a USRP testing scenario from the USRP machine.
    set +x
    ssh jenkins@nala timeout "$PLAYBACK_DURATION" \
        python -u ~henry/swift/peregrine/peregrine/stream_usrp.py -1 -u \
        name=b200_{1,2} \
        -g 30 \
        -p \
        /data/sky/{leica,novatel}-20150707-070000.1bit
}

function start_recording () {
    # Start a serial link SBP recording.
    cd "$CWD"
    echo "Starting recording on" "$1"
    echo "Writing output to " "$2"
    python piksi_tools/serial_link.py -l -r -t "$PLAYBACK_DURATION" -p "$1" -o "$2" > /dev/null &
}

function prep_logs () {
    # Create a per-device session logs and cleanup stuff if it's
    # already there.
    mkdir -p "$3"
    rm -f version.yaml
    rm -f "$3"/*
}

## Running stuff in parallel

function run_parallel_pairs () {
    # Run a function on each device in a pair, parallel across pairs
    # (rover + base station).
    while read DEV1 DEV2; do
      ROVER_DEV_ID=$(echo "$DEV1" | egrep -o 'PK[0-9]+')
      $1 "$DEV1" "$DEV2" "$ROVER_DEV_ID" &
    done < "$DEVICES"
    wait
}

function program_pair () {
    echo "Programming firmware on: " "$1" "$2"
    program_device "$1" "$3"/rover.log
    program_device "$2" "$3"/base.log
    sleep 1
}

function diagnostics_pair () {
    echo "Check diagnostics on: " "$1" "$2"
    check_device_settings "$1" "$3"/diagnostics_rover.yaml
    check_device_settings "$2" "$3"/diagnostics_base.yaml
}

function record_pair () {
    echo "Records SBP log data on:" "$1" "$2"
    start_recording "$1" "$3"/rover.json.log
    start_recording "$2" "$3"/base.json.log
}

function run_devices () {
    # Primary runner across all devices: prepare the log directory,
    # program pairs of Piksi's (rovers and base stations
    # sequentially), check that devices were programmed with the right
    # firmware, kickoff USRP recording and timeout eventually.
    run_parallel_pairs prep_logs
    run_parallel_pairs program_pair
    # Give Piksi a rest for a bit after programming.
    sleep 10
    run_parallel_pairs diagnostics_pair
    run_parallel_pairs record_pair
    start_scenario
    echo "Done!"
}

function show_help () {
    echo "Move along, nothing to see here..."
}

while getopts ":x:" opt; do
    case $opt in
        x)
            if [[ "$OPTARG" == "run" ]]; then
                check_args
                make_full_version
                setup_shit
                run_devices
                exit 0
            else
                echo "Invalid option: -x $OPTARG" >&2
            fi
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            ;;
    esac
    exit 1
done
show_help
