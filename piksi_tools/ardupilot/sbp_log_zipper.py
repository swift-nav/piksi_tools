
import argparse
import json

import sbp.client.loggers.json_logger as json_logger
import sbp.observation as ob
import sbp.navigation as nav
from sbp.msg import SBP

msgs_filter = [
  ob.SBP_MSG_OBS,
  ob.SBP_MSG_EPHEMERIS_GPS,
  ob.SBP_MSG_EPHEMERIS_SBAS,
  ob.SBP_MSG_EPHEMERIS_GLO,
  ob.SBP_MSG_IONO,
  ob.SBP_MSG_BASE_POS_LLH,
  ob.SBP_MSG_BASE_POS_ECEF
  ]


def extract_gpstime(msg, last_gpstime=(0,0)):
  '''
  Returns (wn,tow) tuple. returns last_gpstime if none in this message
  '''
  if msg.msg_type == ob.SBP_MSG_OBS:
    return (msg.header.t.wn, msg.header.t.tow)
  elif msg.msg_type == ob.SBP_MSG_EPHEMERIS_GPS or msg.msg_type == ob.SBP_MSG_EPHEMERIS_SBAS or msg.msg_type == ob.SBP_MSG_EPHEMERIS_GLO:
    return (msg.toc.wn, msg.toc.tow)
  elif msg.msg_type == ob.SBP_MSG_IONO:
    return (msg.t_nmct.wn, msg.t_nmct.tow)
  elif msg.msg_type == ob.SBP_MSG_BASE_POS_ECEF or msg.msg_type == ob.SBP_MSG_BASE_POS_LLH:
    return last_gpstime


def compare_gpstime(g0, g1):
  '''
  Returns the index of the earlier GPSTIME (wn,tow) tow.
  '''
  if g0[0] < g1[0]:
    return 0
  elif g0[0] > g1[0]:
    return 1
  else:
    if g0[1] < g1[1]:
      return 0
    elif g0[1] > g1[1]:
      return 1
    else:
      return 0

def print_emit(msg):
  print msg.to_json()

def zip_json_generators(base_gen, rove_gen, emit_fn):
  '''
  Zips together two generators.
  Runs in constant space.
  Sends messages to the emit_fn

  Here's the algorithm:
    We assume we might have a message from every logfile
    For the logfiles we don't have a message, we retrieve one.
    We get timestamps for all our messages.
    We consume and discard the one with the oldest timestamp, keeping the other around
    Repeat!
  '''
  base_msg = None
  rove_msg = None

  last_gpstime = (0,0)
  while True:

    # Get a base_msg if we don't have one waiting
    while base_msg is None:
      try:
        base_msg = base_gen.next()[0]
        if base_msg.msg_type in msgs_filter:
          # Fix up base id
          base_msg.sender = 0
          break;
        else:
          base_msg = None
      except StopIteration:
        base_done = True
        break;

    # Get a rove_msg if we don't have one waiting
    while rove_msg is None:
      try:
        rove_msg = rove_gen.next()[0]
        if rove_msg.msg_type in msgs_filter:
          break;
        else:
          rove_msg = None
      except StopIteration:
        rove_done = True
        break;


    if base_msg is None and rove_msg is None:
      return; # We are done.

    if base_msg is None:
      emit_fn(rove_msg)
      rove_msg = None
      continue # Loop!

    if rove_msg is None:
      emit_fn(base_msg)
      base_msg = None
      continue #Loop!

    # We have a message from both. Which one do we emit?
    base_time = extract_gpstime(base_msg, last_gpstime)
    rove_time = extract_gpstime(rove_msg, last_gpstime)

    which = compare_gpstime(rove_time, base_time)
    if which == 1:
      emit_fn(base_msg)
      base_msg = None
      last_gpstime = base_time
    else:
      emit_fn(rove_msg)
      rove_msg = None
      last_gpstime = rove_time

def zip_json_files(base_log_handle, rove_log_handle, emit_fn):
  with json_logger.JSONLogIterator(base_log_handle) as base_logger:
    with json_logger.JSONLogIterator(rove_log_handle) as rove_logger:

      base_gen = base_logger.next()
      rove_gen = rove_logger.next()

      zip_json_generators(base_gen, rove_gen, emit_fn)


def main():
  parser = argparse.ArgumentParser(description="Swift Navigation SBP Rover-Base Log Zipper")
  parser.add_argument("base_log")
  parser.add_argument("rover_log")
  args = parser.parse_args()

  with open(args.base_log, 'r') as base_log_handle:
    with open(args.rover_log, 'r') as rove_log_handle:
      zip_json_files(base_log_handle, rove_log_handle, print_emit)


if __name__ == "__main__":
  main()