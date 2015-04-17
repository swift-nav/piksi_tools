#!/usr/bin/env python

from setuptools import setup
import os

VERSION = "0.9"

CLASSIFIERS = [
  'Intended Audience :: Developers',
  'Intended Audience :: Science/Research',
  'Operating System :: POSIX :: Linux',
  'Operating System :: MacOS :: MacOS X',
  'Operating System :: Microsoft :: Windows',
  'Programming Language :: Python',
  'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
  'Topic :: Software Development :: Libraries :: Python Modules',
  'Programming Language :: Python :: 2.7',
]

PACKAGES = [
  'piksi_tools',
]

PLATFORMS = [
  'linux',
  'osx',
  'win32',
]

DATA_FILES = [
  ('piksi_tools', 'settings.yaml'),
]

PACKAGE_DATA = { 'piksi_tools' : [
  'settings.yaml',
  'images/fontawesome/download.svg',
  'images/fontawesome/exclamation-triangle.svg',
  'images/fontawesome/floppy-o.svg',
  'images/fontawesome/refresh.svg',
  'images/fontawesome/stop.svg',
  'images/iconic/fullscreen.svg',
  'images/iconic/move.svg',
  'images/iconic/pause.svg',
  'images/iconic/play.svg',
  'images/iconic/stop.svg',
  'images/iconic/target.svg',
  'images/iconic/x.svg',
] }

cwd = os.path.abspath(os.path.dirname(__file__))
with open(cwd + '/README.rst') as f:
  readme = f.read()

with open(cwd + '/requirements.txt') as f:
  INSTALL_REQUIRES = [i.strip() for i in f.readlines()]

setup(name='piksi_tools',
      description='Python tools for the Piksi GNSS receiver.',
      long_description=readme,
      version=VERSION,
      author='Swift Navigation',
      author_email='dev@swiftnav.com',
      url='https://github.com/swift-nav/piksi_tools',
      classifiers=CLASSIFIERS,
      packages=PACKAGES,
      package_data=PACKAGE_DATA,
      platforms=PLATFORMS,
      install_requires=INSTALL_REQUIRES,
      use_2to3=False,
      zip_safe=False)
