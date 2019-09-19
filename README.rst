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

It is advised to install ``piksi_tools`` inside a virtualenv to avoid modifying global system state.  To create a virtualenv, run::

  virtualenv py2
  source py2/bin/activate

Or, on Linux Mint, run::

  virtualenv py2 --system-site-packages
  source py2/bin/activate

To setup a python 3.5 virtual environment if your default python is 2.7, first
install python 3.5 via your package manager if needed, and then run::

  virtualenv -p python3.5 ~/py3
  source ~/py3/bin/activate

To install the dependencies for the basic tools: ``pip install -r requirements.txt``

To install the dependencies for the console GUI, run ``make deps``. Besides
system packages, this also installs python dependencies into the current
(virtual) environment, and includes the deps for the aforementioned basic tools.

Finally, ``pip install -e .`` to set up a dev install in the local dev environment.

To run the installed console from the current env, use ``python -m piksi_tools.console.console``

Python version support
~~~~~~~~~~~~~~~~~~~~~~

* The most important command line tools - ``bootload_v3.py``, ``fileio.py``,
  ``serial_link.py``, and ``settings.py`` - support Python 2.7, 3.5, and 3.7

* Console GUI under Linux supports 2.7 and 3.5

* Console GUI under MacOS and Windows is tested against Python 3.5 but probably
  would support all versions that Linux GUI supports, but some of those might
  need a manual GUI backend change/installation

* Pre-built (pyinstaller) binaries for most platforms use Python 3.5.  On Ubuntu,
  Python 3.6 is used.

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

To run the tests (excluding some graphical ones) and check for coverage::

  $ PYTHONPATH=. tox

This by default attempts to run tests for all supported Python versions. To skip
those versions that you don't have installed, run::

  $ PYTHONPATH=. tox --skip-missing-interpreters

To run some extra tests for the GUI (excluding the non-graphical tests)::

  $ PYTHONPATH=. tox -e gui35,gui37

Finally, to run *all* tests for all supported Python versions::

  $ PYTHONPATH=. tox -e py27,py35,py37,gui35,gui37

USB issues on OS X
------------------
The ftdi USB drivers are finicky on some versions of OS X. See their `docs <http://pylibftdi.readthedocs.io/en/latest/troubleshooting.html#where-did-my-ttyusb-devices-go>`__ for help debugging (tl;dr if you try to plug in multiple USB devices to the same port, the subsequent ones may not appear through ftdi even if they appear in the result of ``sudo dmesg``. Only restarting your machine will fix this.)

License
-------
Copyright (C) 2019 Swift Navigation
Distributed under LGPLv3.0
