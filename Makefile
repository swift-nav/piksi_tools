# Convenience Makefile for dealing with the Piksi tools and console
# client. Please read and understand the contents of this file before
# using it to do Crazy Things.

SWIFTNAV_ROOT := $(shell pwd)
MAKEFLAGS += SWIFTNAV_ROOT=$(SWIFTNAV_ROOT)
export PYTHONPATH := .

.PHONY: help deps

help:
	@echo
	@echo "Piksi Tools helper"
	@echo
	@echo "(Please read before using!)"
	@echo
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  help      to display this help message"
	@echo "  deps      to install dependencies"
	@echo

all: deps

deps:
	cd $(SWIFTNAV_ROOT)/tasks && bash setup.sh && cd $(SWIFTNAV_ROOT)

serial_deps:
	sudo pip install -r requirements.txt
