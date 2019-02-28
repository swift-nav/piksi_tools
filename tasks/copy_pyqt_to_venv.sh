#!/bin/bash
set -eu

if [[ "$OSTYPE" != "linux-gnu" ]]; then
    echo "This script only supports (Debian-based) Linux"
    exit 1
fi

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo -e "copying system's pyqt4 and sip into current python venv ${VIRTUAL_ENV}..."
    python_version=`python --version 2>&1`
    package_dir=`find "${VIRTUAL_ENV}/lib" -name "site-packages"`
    if [[ ${python_version} == *"2.7"* ]]; then
        source_dir=`dpkg -L python-qt4|grep -m 1 "dist-packages$"`
    elif [[ ${python_version} == *"3"* ]]; then
        source_dir=`dpkg -L python3-pyqt4|grep -m 1 "dist-packages$"`
    else
        echo "unsupported python version"
        exit 1
    fi
    cp ${source_dir}/{sipconfig*.py,sip*.so} "${package_dir}"
    cp -r ${source_dir}/PyQt4/ "${package_dir}"
else
    echo "Not inside a Python virtual env; skipping copying PyQt4 and sip"
fi
