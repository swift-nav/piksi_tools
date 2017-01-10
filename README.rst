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

Note on ``virtualenv`` and ``conda``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If want to use a `virtualenv <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`__ while developing the console, you should activate it before running the install scripts, as they will ``pip install`` requirements.

The unittests do not work with the ``conda`` package manager because ``tox`` uses ``virtualenv``, which is not compatible with ``conda``.

Scripts
~~~~~~~
Install all dependencies (including console libraries)::

  $ make deps

Install dependencies (without console libraries)::

  $ make serial_deps

Install from repo::

  $ sudo python setup.py install

Install package from pypi::

  $ sudo pip install piksi_tools

On OS X, you may need to add ``export PYTHONPATH=/usr/local/lib/python2.7/site-packages:$PYTHONPATH`` to your ``~/.bash_profile`` in order to use libraries installed via ``brew``.


Usage Examples
--------------

Bootloader example
~~~~~~~~~~~~~~~~~~

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
