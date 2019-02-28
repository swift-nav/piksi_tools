# a hack for:
# ValueError: API 'QDate' has already been set to version 1. Pyface expects
# PyQt API 2 under Python 2. Either import Pyface before any other Qt-using
# packages, or explicitly set the API before importing any other Qt-using packages.
import pyface.qt
