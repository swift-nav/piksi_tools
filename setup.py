#!/usr/bin/env python

import re
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
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.7',
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

   
def version_scheme_add_v(version):
    from setuptools_scm.version import guess_next_dev_version
    scm_version = guess_next_dev_version(version)
    v_version = scm_version if scm_version[0] == 'v' else "v" + scm_version
    return v_version



tag_regex = r"^([\w-]+-)?(?P<prefix>[vV])?(?P<version>\d+(\.\d+){0,2}[^+]+?)(?P<suffix>-(devel.*|release|branch|))$"




if __name__ == '__main__':

    import io

    cwd = os.path.abspath(os.path.dirname(__file__))

    with io.open(cwd + '/README.rst', encoding='utf8') as f:
        readme = f.read()

    with open(cwd + '/requirements.txt') as fp:

        INSTALL_REQUIRES = [L.strip() for L in fp if (not L.startswith('git+') and not L.startswith('--extra-index-url'))]

        def transform(link):
            link = link.strip()
            spl = re.split('[&#]', link)
            return str.join('#', spl)

        DEPENDENCY_LINKS = [transform(L) for L in fp if L.startswith('git+')]

    setup(
        name='piksi_tools',
        description='Python tools for the Piksi GNSS receiver.',
        long_description=readme,
        use_scm_version={
            'write_to': 'piksi_tools/_version.py',
            'tag_regex':  tag_regex,
            'version_scheme': version_scheme_add_v
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
        dependency_links=DEPENDENCY_LINKS,
        include_package_data=True,
        use_2to3=False,
        zip_safe=False)
