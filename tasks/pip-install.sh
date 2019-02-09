#!/bin/bash

# Hack to make sure pip is always updated to the version specified
pip install --upgrade pip==19.0.1 setuptools_scm

pip install "$@"
