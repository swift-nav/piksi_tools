#!/usr/bin/env python

from piksi_tools import __version__
from setuptools import setup
import os

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

PACKAGE_DATA = {
  'piksi_tools': ['*.yaml', 'images/*.svg']
}

PLATFORMS = [
  'linux',
  'osx',
  'win32',
]

cwd = os.path.abspath(os.path.dirname(__file__))
with open(cwd + '/README.rst') as f:
  readme = f.read()

with open(cwd + '/requirements.txt') as f:
  INSTALL_REQUIRES = [i.strip() for i in f.readlines()]

setup(name='piksi_tools',
      description='Python tools for the Piksi GNSS receiver.',
      long_description=readme,
      version=__version__,
      author='Swift Navigation',
      author_email='dev@swiftnav.com',
      url='https://github.com/swift-nav/piksi_tools',
      classifiers=CLASSIFIERS,
      packages=PACKAGES,
      platforms=PLATFORMS,
      package_data=PACKAGE_DATA,
      install_requires=INSTALL_REQUIRES,
      use_2to3=False,
      zip_safe=False)
