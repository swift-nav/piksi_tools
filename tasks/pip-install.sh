#!/bin/bash

# Hack to make sure pip is always updated to the version specified
python -m pip install --upgrade pip==19.0.1 setuptools_scm

# Do the requested install
python -m pip install "$@"
