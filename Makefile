CR := conda run -n piksi_tools --live-stream

settings-pdf:
	cd settings; $(CR) python ./generate_settings.py

install:
	$(CR) pip install -e .[test,settings]

setup:
	conda create -n piksi_tools python=3.9
