Tools for the Piksi GNSS receiver
=================================

.. image:: https://travis-ci.org/swift-nav/piksi_tools.png
    :target: https://travis-ci.org/swift-nav/piksi_tools

.. image:: https://badge.fury.io/py/piksi_tools.png
    :target: https://pypi.python.org/pypi/piksi_tools

Python tools for the Piksi GNSS receiver. This repository includes a
Swift console UI application, as well as a variety of command line
utilities (firmware bootloader, serial port data logging, etc.).

Setup
-----

It is advised to install ``piksi_tools`` inside a virtualenv to avoid modifying global system state.

To install the dependencies for the basic tools: ``pip install -r requirements.txt``

To install the dependencies for the console GUI, first run ``make deps`` to install the systemwide deps and then ``pip install -r requirements_gui.txt pyside`` for the python deps.

Finally, ``pip install -e .`` to set up a dev install in the local dev environment.

To run the installed console from the current env, use ``python -m piksi_tools.console.console``


Usage Examples
--------------

Console example
~~~~~~~~~~~~~~~

To just use the Swift console, download binary installers for Windows and OS X.

  Latest console for `Piksi Multi <http://downloads.swiftnav.com/swift_console>`__

  Older versions of console for use with `Piksi v2 <http://downloads.swiftnav.com/piksi_console>`__

  For x86-64 Linux, tar.gz distributions are available for Swift Console `Piksi Multi <http://downloads.swiftnav.com/swift_console>`__

To run the console GUI from the command line, install dependencies and run ``PYTHONPATH=. python piksi_tools/console/console.py``.

For command line arguments, see `console.py <https://github.com/swift-nav/piksi_tools/blob/master/piksi_tools/console/console.py>`__

Testing
-------

To run the tests and check for coverage::

  $  PYTHONPATH=. tox

USB issues on OS X
------------------
The ftdi USB drivers are finicky on some versions of OS X. See their `docs <http://pylibftdi.readthedocs.io/en/latest/troubleshooting.html#where-did-my-ttyusb-devices-go>`__ for help debugging (tl;dr if you try to plug in multiple USB devices to the same port, the subsequent ones may not appear through ftdi even if they appear in the result of ``sudo dmesg``. Only restarting your machine will fix this.)

License
-------

Copyright © 2015 Swift Navigation

Distributed under LGPLv3.0.
