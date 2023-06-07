Tools for the Piksi GNSS receiver
=================================

.. image:: https://travis-ci.org/swift-nav/piksi_tools.svg?branch=master
    :target: https://travis-ci.org/swift-nav/piksi_tools

.. image:: https://badge.fury.io/py/piksi_tools.png
    :target: https://pypi.python.org/pypi/piksi_tools

Python tools for the Piksi GNSS receiver. This repository includes a a variety
of command line utilities (firmware bootloader, serial port data logging,
etc.).

Setup
-----

It is advised to install ``piksi_tools`` inside a conda environment to avoid modifying
global system state.  To setup a conda environment first install
Miniconda via your package manager if needed, and then run::

  conda create -n piksi_tools python=3.7
  conda activate piksi_tools

Run ``pip install -e .[test]`` to set up a dev install in the local dev environment.

Python version support
~~~~~~~~~~~~~~~~~~~~~~

* The most important command line tools - ``bootload_v3.py``, ``fileio.py``,
  ``serial_link.py``, and ``settings.py`` - support Python 3.7 onward.

Testing
-------

To run the tests and check for coverage::

  $ PYTHONPATH=. tox

This by default attempts to run tests for all supported Python versions. To skip
those versions that you don't have installed, run::

  $ PYTHONPATH=. tox --skip-missing-interpreters

Finally, to run *all* tests for all supported Python versions::

  $ PYTHONPATH=. tox -e py37

USB issues on OS X
------------------
The ftdi USB drivers are finicky on some versions of OS X. See their `docs <http://pylibftdi.readthedocs.io/en/latest/troubleshooting.html#where-did-my-ttyusb-devices-go>`__ for help debugging (tl;dr if you try to plug in multiple USB devices to the same port, the subsequent ones may not appear through ftdi even if they appear in the result of ``sudo dmesg``. Only restarting your machine will fix this.)

License
-------
Copyright (C) 2011-2023 Swift Navigation
Distributed under LGPLv3.0
