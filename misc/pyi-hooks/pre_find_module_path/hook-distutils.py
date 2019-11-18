import distutils
import os

from PyInstaller.utils.hooks import logger

# https://github.com/pyinstaller/pyinstaller/issues/4064
# https://pythonhosted.org/PyInstaller/hooks.html#the-pre-find-module-path-pfmp-api-method

def pre_find_module_path(api):
    # Absolute path of the system-wide "distutils" package when run from within
    # a venv or None otherwise.
    distutils_dir = getattr(distutils, 'distutils_path', None)
    if distutils_dir is not None:
        # workaround for https://github.com/pyinstaller/pyinstaller/issues/4064
        if distutils_dir.endswith('__init__.py'):
            distutils_dir = os.path.dirname(distutils_dir)

        # Find this package in its parent directory.
        api.search_dirs = [os.path.dirname(distutils_dir)]

        logger.info('>>>>>>> CUSTOM >>>>>>>>> distutils: retargeting to non-venv dir %r' % distutils_dir)
