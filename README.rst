Tools for the Piksi GNSS receiver
=================================

.. image:: https://travis-ci.org/swift-nav/piksi_tools.png
    :target: https://travis-ci.org/swift-nav/piksi_tools

.. image:: https://badge.fury.io/py/piksi_tools.png
    :target: https://pypi.python.org/pypi/piksi_tools

Python tools for the Piksi GNSS receiver.

Setup
-----

Install dependencies only::

  $ sudo pip install -r requirements.txt

Install from repo::

  $ sudo python setup.py install

Install package from pypi::

  $ sudo pip install piksi_tools

Usage Examples
--------------

Bootloader example
~~~~~~~~~~~~~~~~~~

To load the main firmware hex file::

  $ cd piksi_tools
  $ ./bootload.py -s -p /dev/tty.usbserial-PKxxxx ~/piksi_firmware/build/piksi_firmware.hex

Console example
~~~~~~~~~~~~~~~

To use the Piksi console, binary installers (Windows and OS X) are here_.

.. _here: http://downloads.swiftnav.com/piksi_console/

or::

  $ cd piksi_tools/console
  $ ./console.py -p /dev/tty.usbserial-PKxxxx -l

The -l flag will save a json version of the console log in the current directory.
Omitting the -p flag will let you choose from a list of connected devices.

Testing
-------

To run the tests and check for coverage::

  $  tox

License
-------

Copyright © 2015 Swift Navigation

Distributed under LGPLv3.0.
