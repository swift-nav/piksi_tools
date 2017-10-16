#!/usr/bin/env python

import os

from setuptools import setup

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

PACKAGES = ['piksi_tools', 'piksi_tools.console', 'piksi_tools.ardupilot']

PLATFORMS = [
    'linux',
    'osx',
    'win32',
]

PACKAGE_DATA = {
    'piksi_tools': [
        'console/settings.yaml',
        'console/images',
        'console/images/icon.png',
        'console/images/fontawesome/download.svg',
        'console/images/fontawesome/exclamation-triangle.svg',
        'console/images/fontawesome/floppy-o.svg',
        'console/images/fontawesome/refresh.svg',
        'console/images/fontawesome/stop.svg',
        'console/images/iconic/fullscreen.svg',
        'console/images/iconic/arrows_blue.png',
        'console/images/iconic/arrows_grey.png',
        'console/images/iconic/move.svg',
        'console/images/iconic/pause.svg',
        'console/images/iconic/play.svg',
        'console/images/iconic/stop.svg',
        'console/images/iconic/target.svg',
        'console/images/iconic/x.svg',
    ]
}

cwd = os.path.abspath(os.path.dirname(__file__))
with open(cwd + '/README.rst') as f:
    readme = f.read()

with open(cwd + '/requirements.txt') as f:
    INSTALL_REQUIRES = [i.strip() for i in f.readlines()]

setup(
    name='piksi_tools',
    description='Python tools for the Piksi GNSS receiver.',
    long_description=readme,
    use_scm_version={
        'write_to': 'piksi_tools/_version.py',
    },
    setup_requires=['setuptools_scm'],
    author='Swift Navigation',
    author_email='dev@swiftnav.com',
    url='https://github.com/swift-nav/piksi_tools',
    classifiers=CLASSIFIERS,
    packages=PACKAGES,
    package_data=PACKAGE_DATA,
    platforms=PLATFORMS,
    install_requires=INSTALL_REQUIRES,
    include_package_data=True,
    use_2to3=False,
    zip_safe=False)
