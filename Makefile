CR := conda run -n piksi_tools --live-stream
VERSION ?= Piksi Firmware version v3.0.17-2-AAR

settings-pdf:
	cd settings; $(CR) python ./generate_settings.py "$(VERSION)"
	cp settings/settings_out.pdf settings.pdf

install:
	$(CR) pip install -e .[test,settings]

setup:
	conda create -n piksi_tools python=3.9
