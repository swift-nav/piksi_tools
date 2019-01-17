#!/usr/bin/env python
# Copyright (C) 2016 Swift Navigation Inc.
# Contact: Dennis Zollo<dzollo@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

"""

This module provides a commandline interface for sending and receiving settings
from Swift Navigation devices.  In order for the relative import of serial_link to work
it is recommended that the script is installed and run as a module.

Example:
    to interactively read one setting:

        $ python -m piksi_tools.settings  -p /dev/ttyUSB0 read system_info firmware_version

    to interactively read all settings:

        $ python -m piksi_tools.settings  -p /dev/ttyUSB0 all

    to  read all settings to an .ini file:

        $ python -m piksi_tools.settings  -p /dev/ttyUSB0 read_to_file config.ini

    to  write all settings from an .ini file and save to the device:

        $ python -m piksi_tools.settings  -p /dev/ttyUSB0 -s write_from_file config.ini

Todo:
    * Harmonize and/or re-use logic here for settings_view in console
"""

from __future__ import absolute_import, print_function

import struct
import time
import configparser
from collections import OrderedDict

from sbp.client import Framer, Handler
from sbp.piksi import MsgReset
from sbp.settings import (
    SBP_MSG_SETTINGS_READ_BY_INDEX_DONE, SBP_MSG_SETTINGS_READ_BY_INDEX_RESP,
    SBP_MSG_SETTINGS_READ_RESP, SBP_MSG_SETTINGS_WRITE_RESP,
    MsgSettingsReadByIndexReq, MsgSettingsReadReq,
    MsgSettingsSave, MsgSettingsWrite)

from piksi_tools import serial_link

DEFAULT_READ_RETRIES = 5
DEFAULT_TIMEOUT_SECS = 0.5

KEY_ENCODING = 'ascii'    # encoding for settings sections and keys
VALUE_ENCODING = 'ascii'  # encoding for settings values


class ReadOnlySettingError(Exception):
    pass


class Settings(object):
    """
    Settings

    The :class:`Settings` class retrieves and sends settings.
    """

    def __enter__(self):
        self.link.add_callback(self._settings_callback,
                               SBP_MSG_SETTINGS_READ_RESP)
        self.link.add_callback(self._settings_list_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
        self.link.add_callback(self._settings_done_callback,
                               SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)
        return self

    def __exit__(self, *args):
        self.link.remove_callback(self._settings_callback,
                                  SBP_MSG_SETTINGS_READ_RESP)
        self.link.remove_callback(self._settings_list_callback,
                                  SBP_MSG_SETTINGS_READ_BY_INDEX_RESP)
        self.link.remove_callback(self._settings_done_callback,
                                  SBP_MSG_SETTINGS_READ_BY_INDEX_DONE)

    def __init__(self, link, timeout=DEFAULT_TIMEOUT_SECS):
        self.link = link
        self.settings_list = OrderedDict()
        self.settings_list_received = False  # switch to indicate all settings have been read
        self.read_response_wait_dict = {}  # signaling dictionary for settings reads and timeouts
        self.timeout = timeout  # how long to wait for response from device?

    def read_all(self, verbose=False):
        """Read all settings from device

        Args:
            verbose(bool): Echo settings to sdout

        Returns:
            Nested dictionary of settings[section][names] with values
            as strings

        """
        self.settings_list_received = False
        self.link(MsgSettingsReadByIndexReq(index=0))
        attempts = 0
        while not self.settings_list_received:
            time.sleep(self.timeout)
            attempts += 1
            if attempts > 10:  # wait 10 timeout periods for settings before trying again
                attempts = 0
                self.link(MsgSettingsReadByIndexReq(index=0))

        for section in self.settings_list:
            if verbose:
                print('%s:' % section)
            for setting, value in iter(self.settings_list[section].items()):
                if verbose:
                    print('- %s = %s' % (setting, value))
        return self.settings_list

    def read(self, section, setting, retries=DEFAULT_READ_RETRIES, verbose=False):

        """Read one setting from device

        Args:
            section(str): string of section name
            setting(str): string of setting name
            verbose(bool): Echo settings to sdout
        Raises:
             RunTimeError: if we were not able to read setting. It may not exist.
        Returns:
             value of the requested setting as a string

        """
        self.read_response_wait_dict[(section, setting)] = False
        attempts = 0
        response = False
        while response is False and attempts < retries:
            if verbose:
                print("Attempting to read:section={}|setting={}".format(section, setting))
            self.link(MsgSettingsReadReq(setting=b'%s\0%s\0'
                      % (section.encode(KEY_ENCODING), setting.encode(KEY_ENCODING))))
            time.sleep(self.timeout)
            response = self.read_response_wait_dict[(section, setting)]
            attempts += 1
        response = self.read_response_wait_dict[(section, setting)]
        if response is not False:
            if verbose:
                print("Successfully read setting \"{}\" in section \"{}\" with value \"{}\"".format(setting, section,
                                                                                                    response))
            return response
        else:  # never received read resp callback
            raise RuntimeError(("Unable to read setting \"{}\" in section \"{}\" after {} attempts. "
                                "Setting may not exist.".format(setting, section, retries)))

    def write(self, section, setting, value, verbose=False):
        """Write setting by name and confirm set

        Args:
            section(str): string of section name
            setting(str): string of setting name
            value(str): value to set
            verbose(bool): Echo settings to sdout
        Raises:
            KeyError if the section/setting does not exist
            ReadOnlySettingError if the section/setting is read-only
            RuntimeError if the write was otherwise unsuccessful
        Returns:
            None
        """
        if verbose:
            print("Attempting to write: section={}|setting={}|value={}".format(section, setting, value))

        key = b'%s\0%s\0' % (section.encode(KEY_ENCODING), setting.encode(KEY_ENCODING))
        request = key + b'%s\0' % value.encode(VALUE_ENCODING)

        self.link(MsgSettingsWrite(setting=request))
        reply = self.link.wait(SBP_MSG_SETTINGS_WRITE_RESP, timeout=self.timeout)

        if reply is None:
            raise RuntimeError("Settings write request {}/{} timed out"
                               .format(section, setting))
        if reply and not reply.setting.startswith(key):
            raise RuntimeError("Warning: setting write response \"{}\" with "
                               "status {} does not match the request (\"{}\")."
                               .format(reply.setting, reply.status, request))

        if reply.status == 0:  # ok
            reply_value = reply.setting.split(b'\0')[2].decode(KEY_ENCODING)
            if verbose:
                print("  Wrote: section={}|setting={}|value={}"
                      .format(section, setting, reply_value))
        elif reply.status == 1 or reply.status == 3:
            raise RuntimeError("Unable to write setting \"{}\" in section \"{}\" "
                               "with value \"{}\": Setting value rejected."
                               .format(setting, section, value))
        elif reply.status == 2:
            raise KeyError("Unable to write setting \"{}\" in section \"{}\": "
                           "The setting does not exist.".format(setting, section))
        elif reply.status == 4 or reply.status == 5:
            raise ReadOnlySettingError("Setting \"{}\" in section \"{}\" is read-only."
                                       .format(setting, section))
        elif reply.status == 6:
            raise RuntimeError("System failure when attempting to set setting "
                               "\"{}\" in section \"{}\".".format(setting, section))
        else:
            raise RuntimeError("Unknown setting write status response {} when "
                               "attempting to set setting \"{}\" in section \"{}\"."
                               .format(reply.status, setting, section))

    def save(self):
        """Save settings to flash"""
        self.link(MsgSettingsSave())

    def reset(self):
        """Reset to default settings and reset device"""
        self.link(MsgReset(flags=1))

    def read_to_file(self, output, verbose=False):
        """Read settings to output ini file."""
        settings_list = self.read_all(verbose=verbose)
        parser = configparser.RawConfigParser()
        parser.optionxform = str
        parser.read_dict(settings_list)
        with open(output, "w") as f:
            parser.write(f)

    def write_from_file(self, output, verbose=False):
        """Write settings to device from ini file."""
        parser = configparser.ConfigParser()
        parser.optionxform = str
        with open(output, 'r') as f:
            parser.read_file(f)
        for section, settings in parser.items():
            for setting, value in settings.items():
                try:
                    self.write(section, setting, value, verbose=verbose)
                except ReadOnlySettingError as e:
                    print(' ', e)

    def _settings_callback(self, sbp_msg, **metadata):
        section, setting, value, format_type = sbp_msg.payload.split(b'\0')[:4]
        self.read_response_wait_dict[(
            section.decode(KEY_ENCODING), setting.decode(KEY_ENCODING))] = value.decode(VALUE_ENCODING)

    def _settings_list_callback(self, sbp_msg, **metadata):
        section_b, setting_b, value_b, format_type_b = sbp_msg.payload[2:].split(b'\0')[:4]
        section = section_b.decode(KEY_ENCODING)
        setting = setting_b.decode(KEY_ENCODING)
        value = value_b.decode(VALUE_ENCODING)
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
    parser = serial_link.base_cl_options()
    parser.description = 'Piksi Settings Tool'
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.epilog = ("Returns:\n"
                     "  0: Upon success\n"
                     "  1: Runtime error or invalid settings request.\n"
                     "  2: Improper usage")
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECS,
        help="timeout for settings calls in seconds (default: %.1f)." % DEFAULT_TIMEOUT_SECS)
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
        'reset', help='reset settings to factory defaults.')

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
    command = args.command
    return_code = 0
    driver = serial_link.get_base_args_driver(args)
    with Handler(Framer(driver.read, driver.write)) as link:
        settings = Settings(link, timeout=args.timeout)
        with settings:
            if command == 'write':
                settings.write(args.section, args.setting, args.value, verbose=args.verbose)
            elif command == 'read':
                print(settings.read(args.section, args.setting, verbose=args.verbose))
            elif command == 'all':
                settings.read_all(verbose=True)
            elif command == 'save':
                settings.save()
            elif command == 'reset':
                settings.reset()
            elif command == 'read_to_file':
                settings.read_to_file(args.output, verbose=args.verbose)
            elif command == 'write_from_file':
                settings.write_from_file(args.filename, verbose=args.verbose)
            # If saving was requested, we have done a write command, and the write was requested, we save
            if command.startswith("write") and args.save_after_write:
                print("Saving Settings to Flash.")
                settings.save()


if __name__ == "__main__":
    main()
