#!/bin/bash

# Copyright (C) 2014-2015 Swift Navigation Inc.
# Contact: Bhaskar Mookerji <mookerji@swiftnav.com>

# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.

# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
#
# Script for setting up piksi_tools development environment across
# different development environments. It's not guaranteed to be
# idempotent, or have any other guarantees for that matter, but if
# you're having issues with your particular development platform,
# please let us know: we are trying to account for as many hacks as
# possible

####################################################################
## Utilities.

function color () {
    # Print with color.
    printf '\033[%sm%s\033[m\n' "$@"
}

purple='35;1'
red_flashing='31;5'
message_color=$purple
error_color=$red_flashing

function log_info () {
    color $message_color "$@"
}

function log_error () {
    color $error_color "$@"
}

####################################################################
## Linux dependency management and build

function piksi_splash_linux () {
    # Splash screen. Generated by http://patorjk.com/software/taag/.
    log_info "
          _/\/\/\/\/\____/\/\____/\/\____________________/\/\___
          _/\/\____/\/\__________/\/\__/\/\____/\/\/\/\_________
          _/\/\/\/\/\____/\/\____/\/\/\/\____/\/\/\/\____/\/\___
          _/\/\__________/\/\____/\/\/\/\__________/\/\__/\/\___
         _/\/\__________/\/\/\__/\/\__/\/\__/\/\/\/\____/\/\/\__

         Welcome to piksi_tools development installer!

    "
}


function install_dev_libs(){
    sudo apt-get install \
      build-essential \
      cmake \
      libgl1-mesa-dev \
      libgl1-mesa-glx \
      libgl1-mesa-dri \
      libglu1-mesa-dev \
      libx11-dev \
      python2.7-dev \
      pyqt4-dev-tools \
      qt4-qmake \
      qt4-default \
      qt4-dev-tools \
      x11-apps
}

function bionic_like() {
  # Ubuntu 18.04 -> bionic
  # Mint 19 -> tara
  [[ $(lsb_release -c -s) == "bionic" ]] || \
    [[ $(lsb_release -c -s) == "tara" ]]
}

function all_dependencies_debian () {
    sudo apt-get install git \
         build-essential \
         python \
         python-setuptools \
         python-virtualenv \
         swig
    sudo apt-get install git \
         libicu-dev \
         libqt4-scripttools \
         libffi-dev \
         libssl-dev \
         python-chaco \
         python-qt4-dev \
         python-sip \
         python-qt4-gl \
         libgtk2.0-0
    if bionic_like; then
        sudo apt-get install \
            python-software-properties \
            python-vtk \
            python-pip \
            python-wxgtk2.8
    else
        sudo apt-get install \
            software-properties-common \
            python-wxgtk3.0 \
            python-vtk6
        sudo apt-get purge python-pip
	sudo python -m easy_install pip
    fi
    install_dev_libs
    pip install --upgrade pip
    pip install -r ../requirements.txt
    pip install -r ../requirements_gui.txt
    pip install PyInstaller
    pip install PySide==1.2.4
}


####################################################################
## Mac OS X dependency management and build

function piksi_splash_osx () {
    # Splash screen. Generated by http://patorjk.com/software/taag/.
    log_info "
         '7MM\"\"\"Mq.    db   '7MM                    db
           MM   'MM.          MM
           MM   ,M9  '7MM     MM  ,MP'  ,pP\"Ybd   '7MM
           MMmmdM9     MM     MM ;Y     8I    '\"    MM
           MM          MM     MM;Mm     'YMMMa.     MM
           MM          MM     MM  Mb.  L.    I8     MM
         .JMML.      .JMML. .JMML. YA.  M9mmmP'   .JMML.

         Welcome to piksi_tools development installer!

    "
}

function homebrew_install () {
    # Provides homebrew for OS X and fixes permissions for brew
    # access. Run this if you need to install brew by:
    #    source ./setup.sh
    #    homebrew_install
    ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    brew doctor
    brew update
    # Homebrew apparently requires the contents of /usr/local to be
    # chown'd to your username.  See:
    # http://superuser.com/questions/254843/cant-install-brew-formulae-correctly-permission-denied-in-usr-local-lib
    sudo chown -R "$(whoami)" /usr/local
}

function bootstrap_osx () {
    sw_vers
    log_info "Checking base OS X development tools..."
    # Download and install Homebrew
    if [[ ! -x /usr/local/bin/brew ]]; then
        log_info "Installing homebrew..."
        homebrew_install
    fi
    brew update
    brew upgrade
    brew install openssl
    brew link openssl
}

function install_swig_osx () {
    log_info "Installing swig...."
    brew install https://gist.github.com/denniszollo/e09e8b074d6699d77937483b899129ee/raw/7c43bc024053d74bb604488e457f9eb3a4e6a45c/swig@2.rb
    brew link --overwrite --force swig2
}

function install_python_deps_osx () {
    # Uses brew to install system-wide dependencies and pip to install
    # python dependencies.
    log_info "Installing Python dependencies..."

    if [[ ! -x /usr/local/bin/python ]]; then 
      brew install python@2 --framework --with-brewed-openssl 2>&1 || :
    fi

    brew install python@2
    brew link python@2 --force

    pip install --upgrade pip
    brew tap-unpin cartr/qt4 | true # If brew tap-pin is run twice, it errors.
    brew untap cartr/qt4 | true     # If brew tap is run twice, it errors.
    brew tap cartr/qt4
    brew tap-pin cartr/qt4
    brew install qt@4 shiboken@1.2 qt-webkit@2.3
    brew install libftdi sip --force 2>&1 || :
    
    pip install -r ../requirements.txt
    pip install -r ../requirements_gui.txt
    pip install PySide==1.2.2
    curl -O https://raw.githubusercontent.com/PySide/pyside-setup/1.2.2/pyside_postinstall.py
    python pyside_postinstall.py -install
    pip install PyInstaller==3.2.1
}



####################################################################
## Entry points

function run_all_platforms () {
    if [[ "$OSTYPE" == "linux-"* ]]; then
        piksi_splash_linux
        log_info "Checking system dependencies for Linux..."
        log_info "Please enter your password for apt-get..."
        log_info "Updating..."
        sudo apt-get update
        all_dependencies_debian
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        piksi_splash_osx
        log_info "Checking system dependencies for OSX..."
        log_info "Please enter your password..."
        log_info ""
        bootstrap_osx &&
            install_swig_osx &&
            install_python_deps_osx
    else
        log_error "This script does not support this platform. Please contact mookerji@swiftnav.com."
        exit 1
    fi
    log_info "Done!"
}

set -e -u

run_all_platforms
