# Convenience Makefile for dealing with the Piksi tools and console
# client. Please read and understand the contents of this file before
# using it to do Crazy Things.

SWIFTNAV_ROOT := $(CURDIR)
export PYTHONPATH := .

ifeq ("$(OS)","Windows_NT")
UNAME := Windows
else
UNAME := $(shell uname -s)
endif

MAKEFLAGS += SWIFTNAV_ROOT=$(SWIFTNAV_ROOT)

.PHONY: help deps serial_deps build_console

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
	@echo "  docs           to build settings documentation from settings.yaml"
	@echo

all: deps

deps:
	cd $(SWIFTNAV_ROOT)/tasks && bash setup.sh && cd $(SWIFTNAV_ROOT)

.conda_py27:
	conda create -p $(PWD)/.conda_py27 python=2.7 --yes

.conda_py35:
	conda create -p $(PWD)/.conda_py35 python=3.5 --yes

tox_all:
	@echo Using TESTENV=$(TESTENV), TOXENV=$(TOXENV)...
	tox $(if $(filter y,$(VERBOSE)), -v,)

tox_Darwin: export TESTENV:=$(TESTENV)
tox_Darwin: export TOXENV:=$(TOXENV)
tox_Darwin: tox_all

tox: .conda_py35
tox: export PATH:=$(CURDIR)/.conda_py35/bin:$(PATH)
tox: tox_$(UNAME)

test: tox
docs: piksi_tools/console/settings.yaml latex/settings_template.tex piksi_tools/generate_settings_doc.py 
	rm -f docs/settings.pdf && cd $(SWIFTNAV_ROOT) && PYTHONPATH=. python piksi_tools/generate_settings_doc.py
	mv docs/settings.pdf docs/PiksiMulti-settings-v2.4.15.pdf

serial_deps:
	pip install -r requirements.txt

gen_readme:
	PYTHONPATH=. piksi_tools/console/console.py -h > piksi_tools/console/README.txt 
	tail -n +2  piksi_tools/console/README.txt > tmp.txt && mv tmp.txt piksi_tools/console/README.txt

build_console_all:
	python ./scripts/build_release.py

build_console_Darwin: export PATH:=$(CURDIR)/.conda_py35/bin:$(PATH)
build_console_Darwin: .conda_py35
build_console_Darwin: build_console_all

build_console_Linux: build_console_all

build_console_Windows: build_console_all

build_console: build_console_$(UNAME)

release:
	$(call announce-begin,"Run release boilerplate")
	github_changelog_generator --no-author \
				   -t $(CHANGELOG_GITHUB_TOKEN)$ \
				   -o DRAFT_CHANGELOG.md \
				   swift-nav/piksi_tools
