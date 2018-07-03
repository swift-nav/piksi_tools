#!/usr/bin/env bash

which python
if [[ $TESTENV ]]; then
  tox -e $TESTENV
else
  tox
  rm -rf ~/home/.enthought
  PYTHONPATH=. python piksi_tools/console/console.py --file --error -p ./tests/data/piksi.bin & PID=$!
  sleep 10 
  kill -n 9  $PID
  PYTHONPATH=. python piksi_tools/console/console.py --file --error -p ./tests/data/20170513-180207.1.1.26.bin & PID=$!
  sleep 10 
  kill -n 9  $PID
  make build_console
fi
