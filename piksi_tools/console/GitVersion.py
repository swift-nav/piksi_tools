import collections
import re

__all__ = [
    "GitVersion"
]

def parse(version):
    """
    Parse a version string and return either a :class:`GitVersion` object
    or throw an exception
    """
    return GitVersion(version)


class InvalidVersion(ValueError):
    """
    An invalid version was found, users should only pass in the output 
    of a 'git describe' command
    """

class GitVersion(object):

    def __hash__(self):
        return hash(self._key)

    def __lt__(self, other):
        return self._compare(other) < 0

    def __le__(self, other):
        return self._compare(other) <= 0

    def __eq__(self, other):
        return self._compare(other) == 0

    def __ge__(self, other):
        return self._compare(other) >= 0

    def __gt__(self, other):
        return self._compare(other) > 0

    def __ne__(self, other):
        return self._compare(other) != 0

    def _compare(self, other):
        if not isinstance(other, GitVersion):
            return NotImplemented

        if self.marketing != other.marketing:
            return self.marketing - other.marketing

        if self.major != other.major:
            return self.major - other.major

        return self.minor - other.minor

    def __str__(self):
        return self._version

    def __repr__(self):
        return "<GitVersion({0})>".format(self._version)

    def compare_dev_string(self, other):
        return self.devstring.compare(other.devstring)

    def _is_dev(self):
        return len(self.devstring) > 0 and self.devstring != 'v'

    @property
    def marketing(self):
        return self._marketing

    @property
    def major(self):
        return self._major

    @property
    def minor(self):
        return self._minor

    @property
    def devstring(self):
        return self._devstring

    @property
    def isdev(self):
        return self._is_dev()

    _regex = re.compile(
        r"^\s*(?P<leader>[^0-9]*)(?P<marketing>[0-9]+)\.(?P<major>[0-9]+)\.(?P<minor>[0-9]+)(?P<dev>.*)$",
        re.VERBOSE | re.IGNORECASE,
        )

    def __init__(self, version):
        match = self._regex.search(version)
        if not match:
            raise InvalidVersion("Invalid version: '{0}'".format(version))

        self._version = version
        self._marketing = int(match.group("marketing"))
        self._major = int(match.group("major"))
        self._minor = int(match.group("minor"))
        self._devstring = ""
        if match.group("leader"):
            self._devstring = self._devstring + match.group("leader")
        if match.group("dev"):
            self._devstring = self._devstring + match.group("dev")





