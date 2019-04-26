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
    'Programming Language :: Python :: 2.7',
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


def scmtools_parse(root,
                   describe_command=None,
                   config=None):
    """
    rewriting of setuptools_scm.git.parse method to remove -branch string
    from any tags.  This library is clearly not designed for people to adjust
    its function so I had to lift entire function from Aug 8 master with SHA
    a91b40c99ea9bfc4289272285f17e1d43c243b76
    """

    from setuptools_scm.git import GitWorkdir, _git_parse_describe
    from setuptools_scm.config import Configuration
    from setuptools_scm.utils import has_command
    from setuptools_scm.version import meta

    if describe_command is None:
        from setuptools_scm.git import DEFAULT_DESCRIBE
        describe_command = DEFAULT_DESCRIBE

    if not config:
        config = Configuration(root=root)

    if not has_command("git"):
        return

    wd = GitWorkdir.from_potential_worktree(config.absolute_root)
    if wd is None:
        return

    out, unused_err, ret = wd.do_ex(describe_command)
    if ret:
        # If 'git describe' failed, try to get the information otherwise.
        rev_node = wd.node()
        dirty = wd.is_dirty()

        if rev_node is None:
            return meta("0.0", distance=0, dirty=dirty, config=config)

        return meta(
            "0.0",
            distance=wd.count_all_nodes(),
            node="g" + rev_node,
            dirty=dirty,
            branch=wd.get_branch(),
            config=config,
        )
    else:
        tag, number, node, dirty = _git_parse_describe(out)
        branch = wd.get_branch()
        if number:
            return meta(
                tag.replace('-branch', ''),
                config=config,
                distance=number,
                node=node,
                dirty=dirty,
                branch=branch,
            )
        else:
            return meta(tag.replace('-branch', ''), config=config, node=node, dirty=dirty, branch=branch)


def version_scheme_add_v(version):
    from setuptools_scm.version import guess_next_dev_version
    scm_version = guess_next_dev_version(version)
    v_version = scm_version if scm_version[0] == 'v' else "v" + scm_version
    return v_version


if __name__ == '__main__':

    cwd = os.path.abspath(os.path.dirname(__file__))

    with open(cwd + '/README.rst') as f:
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
            'parse': scmtools_parse,
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
