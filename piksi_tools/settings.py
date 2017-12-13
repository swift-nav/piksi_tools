#!/usr/bin/env python
# Copyright (C) 2016 Swift Navigation Inc.
# Contact: Leith Bade <leith@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from __future__ import absolute_import, print_function

import struct
import time
import configparser
import sys
from collections import OrderedDict

from sbp.client import Framer, Handler
from sbp.logging import SBP_MSG_LOG, MsgLog
from sbp.piksi import MsgReset
from sbp.settings import (
    SBP_MSG_SETTINGS_READ_BY_INDEX_DONE, SBP_MSG_SETTINGS_READ_BY_INDEX_RESP,
    SBP_MSG_SETTINGS_READ_RESP, MsgSettingsReadByIndexReq, MsgSettingsReadReq,
    MsgSettingsSave, MsgSettingsWrite)

from . import serial_link

MAX_RETRIES = 10
DEFAULT_READ_TIMEOUT_SECS = 0.5


class Settings(object):
    """
    Settings

    The :class:`Settings` class retrieves and sends settings.
    """

    def __init__(self, link, retries=MAX_RETRIES):
        self.link = link
        self.settings_list = OrderedDict()
        self.settings_list_received = False
        self.read_response_wait_dict = {}
        self.setting_received = False
        self.link.add_callback(self._settings_callback,
                               SBP_MSG_SETTINGS_READ_RESP)
        self.link.add_callback(self._settings_list_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
        self.link.add_callback(self._settings_done_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)
        self.link.add_callback(self._print_callback, [SBP_MSG_LOG])
        self.retries = retries

    def read_all(self, verbose=False):
        self.settings_list_received = False
        self.link(MsgSettingsReadByIndexReq(index=0))
        while not self.settings_list_received:
            time.sleep(DEFAULT_READ_TIMEOUT_SECS)
        for section in self.settings_list:
            if verbose:
                print('%s:' % section)
            for setting, value in self.settings_list[section].iteritems():
                if verbose:
                    print('- %s = %s' % (setting, value))
        return self.settings_list

    def read(self, section, setting, verbose=False):
        """
        read setting by name.
        returns a tuple: (return_code, setting_value)
        If return code is anything other than 0, setting_value is invalid
        """
        self.read_response_wait_dict[(section, setting)] = False
        attempts = 0
        response = False
        while response == False and attempts < self.retries:
            if verbose:
                print("Attempting to read:section={}|setting={}".format(section, setting))
            self.link(MsgSettingsReadReq(setting='%s\0%s\0' % (section, setting)))
            time.sleep(DEFAULT_READ_TIMEOUT_SECS)
            response = self.read_response_wait_dict[(section, setting)]
            attempts += 1
        response = self.read_response_wait_dict[(section, setting)]
        if response != False:
            if verbose:
                print("Successfully read:section={}|setting={}value={}".format(section, setting, response))
            return (0, response)
        elif response == False:  # never received read resp callback
            print("Settings read failed after {} attempts:section={}|setting={}".format(self.retries, section, setting))
            return (-1, None)

    def write(self, section, setting, value, verbose=False):
        """
        writes value to setting by name.
        returns return_code
        If return code is -1, we ere not able to read teh setting
        if return code is -2, we could not verify that our write was successful and the setting could be read-only
        """
        actual_value = None
        attempts = 0
        while (actual_value != value or attempts == 0):
            if verbose:
                print("Attempting to write:section={}|setting={}|value={}".format(section, setting, value))
            self.link(MsgSettingsWrite(setting='%s\0%s\0%s\0' % (section, setting, value)))
            (read_return, actual_value) = self.read(section, setting, verbose)
            if (read_return != 0):
                print(
                    "Unable to confirm write of setting. "
                    "Setting may not exist:"
                    "section={}|setting={}|value={}".format(section, setting, value))
                return -1
            attempts += 1
            if attempts == self.retries:
                print("Settings write failed after {} attempts:"
                      "section={}|setting={}|value={}".format(self.retries, section, setting, value))
                print("Settings may be read-only or attempted value invalid")
                return -2
        else:
            if verbose:
                print("Successfully set:section={}|setting={}|value={}".format(section, setting, value))
            return 0


    def save(self):
        self.link(MsgSettingsSave())

    def reset(self):
        self.link(MsgReset(flags=1))

    def read_to_file(self, output, verbose=False):
        settings_list = self.read_all(verbose=verbose)
        parser = configparser.ConfigParser()
        parser.read_dict(settings_list)
        with open(output, "w") as f:
            parser.write(f)

    def write_from_file(self, output, verbose=False):
        parser = configparser.ConfigParser()
        with open(output, 'r') as f:
            parser.read_file(f)
        for section, settings in parser.items():
            for setting, value in settings.items():
                return_code = self.write(section, setting, value, verbose)
                if (return_code != 0):
                    return return_code
        return 0

    def _print_callback(self, msg, **metadata):
        print(msg.text)

    def _settings_callback(self, sbp_msg, **metadata):
        section, setting, value, format_type = sbp_msg.payload.split(
            '\0')[:4]
        self.read_response_wait_dict[(section, setting)] = value

    def _settings_list_callback(self, sbp_msg, **metadata):
        section, setting, value, format_type = sbp_msg.payload[2:].split(
            '\0')[:4]
        if section not in self.settings_list:
            self.settings_list[section] = {}
        self.settings_list[section][setting] = value
        index = struct.unpack('<H', sbp_msg.payload[:2])[0]
        self.link(MsgSettingsReadByIndexReq(index=index + 1))

    def _settings_done_callback(self, sbp_msg, **metadata):
        self.settings_list_received = True


def get_args():
    """
    Get and parse arguments.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Piksi Settings Tool',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=("Returns:\n"
                                            "  0 upon success\n"
                                            " -1 if settings read unsuccessful\n"
                                            " -2 if settings write unsuccessful\n"
                                            "  1 general error\n"
                                            "  2 improper usage" ))
    parser.add_argument(
        "-f",
        "--ftdi",
        help="use pylibftdi instead of pyserial.",
        action="store_true")
    parser.add_argument(
        '-p',
        '--port',
        default=[serial_link.SERIAL_PORT],
        nargs=1,
        help='specify the serial port to use.')
    parser.add_argument(
        "-b",
        "--baud",
        default=[serial_link.SERIAL_BAUD],
        nargs=1,
        help="specify the baud rate to use.")
    parser.add_argument(
        '-v',
        '--verbose',
        default=False,
        action="store_true",
        help='print helpful debug info.')
    parser.add_argument(
        '-s',
        '--save_after_write',
        default=False,
        action="store_true",
        help='Save settings to flash after successful write or write_from_file')
    subparsers = parser.add_subparsers(dest="command")
    save = subparsers.add_parser(
        'save', help='save all the current settings to flash.')

    reset = subparsers.add_parser(
        'reset', help='reset the device after the action.')

    read = subparsers.add_parser('read', help='read the current setting.')
    read.add_argument("section", help="the setting section.")
    read.add_argument("setting", help="the setting name.")

    read_all = subparsers.add_parser('all', help='read all the settings.')

    write = subparsers.add_parser('write', help='write the current setting.')
    write.add_argument("section", help="the setting section.")
    write.add_argument("setting", help="the setting name.")
    write.add_argument("value", help="the setting value.")

    write = subparsers.add_parser('read_to_file', help='read the current settings file from device.')
    write.add_argument("output", help="Name of the file to write in.")

    write = subparsers.add_parser('write_from_file', help='write settings file to device.')
    write.add_argument("filename", help="Name of the file to read from.")

    return parser.parse_args()


def main():
    """
    Get configuration, get driver, and build handler and start it.
    """
    args = get_args()
    port = args.port[0]
    baud = args.baud[0]
    command = args.command
    return_code = 0

    with serial_link.get_driver(args.ftdi, port, baud) as driver:
        with Handler(Framer(driver.read, driver.write)) as link:
            settings = Settings(link)
            if command == 'write':
                return_code = settings.write(args.section, args.setting, args.value, verbose=args.verbose)
            elif command == 'read':
                (return_code, value) = settings.read(args.section, args.setting, args.verbose)
                if return_code == 0:
                    print(value)
            elif command == 'all':
                settings.read_all(True)
            elif command == 'save':
                settings.save()
            elif command == 'reset':
                settings.reset()
            elif command == 'read_to_file':
                settings.read_to_file(args.output, args.verbose)
            elif command == 'write_from_file':
                return_code = settings.write_from_file(args.filename, args.verbose)
            if command.startswith("write") and args.save_after_write and return_code == 0:
                print("Saving Settings to Flash.")
                settings.save()
                # Wait a few seconds for any relevant print messages
    if return_code == 0:
        sys.exit(0)
    else:
        settings.link.wait(MsgLog, 8)
        sys.exit(return_code)

if __name__ == "__main__":
    main()
