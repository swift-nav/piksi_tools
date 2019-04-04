#!/usr/bin/env bash

# Pre-populate the kiva "font cache" so that
# it doesn't spew a bunch error logging.

python -c 'import kiva.fonttools.font_manager' &>/dev/null
