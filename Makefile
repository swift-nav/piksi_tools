# Convenience Makefile for dealing with the Piksi tools and console
# client. Please read and understand the contents of this file before
# using it to do Crazy Things.

SWIFTNAV_ROOT := $(shell pwd)
export PYTHONPATH := .

ifneq (,$(findstring /cygdrive/,$(PATH)))
    ifeq (,$(findstring /cygdrive/,$(SWIFTNAV_ROOT)))
        ifneq (,$(findstring /c/,$(SWIFTNAV_ROOT)))
            SWIFTNAV_ROOT := /cygdrive$(SWIFTNAV_ROOT)
        endif
    endif
    UNAME := Windows
else
ifneq (,$(findstring WINDOWS,$(PATH)))
    UNAME := Windows
else
    UNAME := $(shell uname -s)
endif
endif

MAKEFLAGS += SWIFTNAV_ROOT=$(SWIFTNAV_ROOT)

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
	@echo "  gen_readme     generate console command line options readme"
	@echo

all: deps

deps:
	cd $(SWIFTNAV_ROOT)/tasks && bash setup.sh && cd $(SWIFTNAV_ROOT)

serial_deps:
	pip install -r requirements.txt

gen_readme:
	PYTHONPATH=. piksi_tools/console/console.py -h > piksi_tools/console/README.txt 
	tail -n +2  piksi_tools/console/README.txt > tmp.txt && mv tmp.txt piksi_tools/console/README.txt

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
	@echo "$(PATH)"
	@echo "$(SWIFTNAV_ROOT)"
	cd $(SWIFTNAV_ROOT)/piksi_tools/console/pyinstaller; \
	make clean && make; \
	cd $(SWIFTNAV_ROOT);
	@echo
	@echo "Finished! Please check $(SWIFTNAV_ROOT)/piksi_tools/console/pyinstaller."
