#!/usr/bin/env python2

import sys, os
sys.path.insert(1, os.path.join(sys.path[0], '..'))

from traits.etsconfig.api import ETSConfig
ETSConfig.toolkit = 'null'

from sbp.client.handler import Handler
from piksi_tools import serial_link
from piksi_tools.console import settings_view
import argparse
import time

parser = argparse.ArgumentParser(description='Print Piksi device details.')
parser.add_argument('-p', '--port',
                    default=[serial_link.SERIAL_PORT], nargs=1,
                    help='specify the serial port to use.')
parser.add_argument("-b", "--baud",
                    default=[serial_link.SERIAL_BAUD], nargs=1,
                    help="specify the baud rate to use.")
parser.add_argument("-v", "--verbose",
                    help="print extra debugging information.",
                    action="store_true")
parser.add_argument("-f", "--ftdi",
                    help="use pylibftdi instead of pyserial.",
                    action="store_true")
args = parser.parse_args()
port = args.port[0]
baud = args.baud[0]

settings_read = False
def callback():
  global settings_read
  settings_read = True

# Driver with context
with serial_link.get_driver(args.ftdi, port, baud) as driver:
  # Handler with context
  with Handler(driver.read, driver.write, args.verbose) as link:
    sv = settings_view.SettingsView(link, read_finished_functions=[callback], gui_mode=False)
    link.start()

    # Give the firmware time to start up and possibly send settings.
    time.sleep(10)

    # Force the firmware to send settings.
    global settings_read
    settings_read = False
    sv._settings_read_button_fired()

    while not settings_read:
      time.sleep(1)

    print "===================================="
    print "Piksi Device", port
    print "===================================="
    print
    print "System Info"
    print "-----------"
    print

    for k_, v_ in sv.settings['system_info'].iteritems():
      print "%-20s %s" % (k_, v_)

    print
    print "Settings"
    print "--------"
    print

    for k, v in sv.settings.iteritems():
      if k != 'system_info':
        print "%s:" % k
        for k_, v_ in v.iteritems():
          print "    %-20s %s" % (k_, v_)
        print

