# Convenience Makefile for dealing with the Piksi tools and console
# client. Please read and understand the contents of this file before
# using it to do Crazy Things.

SWIFTNAV_ROOT := $(shell pwd)
MAKEFLAGS += SWIFTNAV_ROOT=$(SWIFTNAV_ROOT)
export PYTHONPATH := .

ifneq (,$(findstring /cygdrive/,$(PATH)))
    UNAME := Windows
else
ifneq (,$(findstring WINDOWS,$(PATH)))
    UNAME := Windows
else
    UNAME := $(shell uname -s)
endif
endif

.PHONY: help deps serial_deps build_console build_console_posix build_console_Darwin build_console_Linux build_console_Windows

help:
	@echo
	@echo "Piksi Tools helper"
	@echo
	@echo "(Please read before using!)"
	@echo
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  help           to display this help message"
	@echo "  deps           to install all dependencies (includes UI deps)"
	@echo "  serial_deps    to install serial dependencies (no UI deps)"
	@echo "  build_console  to build the console binary and installer"
	@echo

all: deps

deps:
	cd $(SWIFTNAV_ROOT)/tasks && bash setup.sh && cd $(SWIFTNAV_ROOT)

serial_deps:
	sudo pip install -r requirements.txt

build_console:
	make build_console_$(UNAME)

build_console_posix:
	cd $(SWIFTNAV_ROOT)/piksi_tools/console/pyinstaller; \
	sudo make clean && sudo make; \
	cd $(SWIFTNAV_ROOT);
	@echo
	@echo "Finished! Please check $(SWIFTNAV_ROOT)/piksi_tools/console/pyinstaller."

build_console_Darwin: build_console_posix

build_console_Linux: build_console_posix

build_console_Windows:
	@echo "Alas! Makefile setup for console building not supported on Windoze!"
