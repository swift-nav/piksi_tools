'''
Takes in a dataflish BIN file and produces an SBP JSON log file with the following record fields:

 {"delta": msec offset since beginning of run,
  "timestamp": UTC timestamp (sec),
  "data":  JSON representation of SBP message specialized to message type (like MsgBaselineNED),
  "metadata": dictionary of tags, optional
  }

Requirements:

  pip install pymavlink
  sudo pip install sbp (see https://github.com/swift-nav/libsbp/tree/master/python/sbp for object definitions)

'''
from pymavlink.DFReader import *
from construct import *
from sbp.table import dispatch,  _SBP_TABLE
from sbp.msg import SBP

import time
import binascii
import json

SBR1_DATASTART = 16
SBR2_DATASTART = 13

'''
This function takes in a filename for a ArduPilot dataflash log,
and returns an array of (timestamp, bytearray) tuples.
The bytearray contains raw SBP binary data logged directly from the serial port.
Each tuple should contain exactly one SBP message.

This decoder requires commit 0b6e5ab1f6d7911d408aaee8a4ec7a457e238399
which is currentl in the denniszollo fork on Github as a pull request
'''
def extractSBP(filename):
  extractedData = []
  log = DFReader_binary(filename)
  log.Verbose = True
  last_m = None
  num_msgs=0
  while True:
    m = log.recv_match(type=['SBR1', 'SBR2'])
    if m is None:
        break
    m.Verbose = True
    bin_data = None
    timestamp = None
    msg_type = None
    sender_id = None
    msg_len = None
    if last_m != None and last_m.get_type() == 'SBR1' and m.get_type() == 'SBR2':
      #append the two
      msg_len = last_m.msg_len
      timestamp = getattr(last_m, '_timestamp', 0.0)
      binary = last_m.binary
      bin_data = bytearray(last_m.get_raw_msgbuf()[SBR1_DATASTART:SBR1_DATASTART+64]
                 + m.get_raw_msgbuf()[SBR2_DATASTART:SBR2_DATASTART+msg_len-64])
      assert(len(bin_data) == msg_len) , "Length of binary data decoded from dataflash does not match msg_len in header"
      msg_type = last_m.msg_type
      sender_id = last_m.sender_id
      last_m = m
    elif last_m != None and last_m.get_type() == 'SBR1' and m.get_type() == 'SBR1':
      #extract the last one, save this one
      msg_len = last_m.msg_len
      binary = last_m.binary
      assert binary, "binary empty"
      timestamp = getattr(last_m, '_timestamp', 0.0)
      msg_type = last_m.msg_type
      sender_id = last_m.sender_id
      bin_data = bytearray(last_m.get_raw_msgbuf()[SBR1_DATASTART:SBR1_DATASTART+msg_len])
      last_m = m
    else:
      #just save this one
      last_m = m
    if bin_data != None:
      if(len(bin_data) != msg_len):
        print ("Length of SBP message inconsitent for msg_type {0}. "
          "Expected Lenght {1}, Actual Length {2}").format(msg_type, msg_len, len(bin_data))
      extractedData.append((timestamp, msg_type, sender_id, msg_len, bin_data))
      num_msgs+=1
  print "extracted {0} messages".format(num_msgs)
  return extractedData

def rewrite(records, outfile):
  """returns array of (time delta offset from beginning of log in msec,
  timestamp in sec, SBP object, parsed). skips unparseable objects.

  """
  new_datafile = open(outfile, 'w')
  protocol = 2
  if not records:
    print "No SBP log records passed to rewrite function. Exiting."
    return
  start_t, msg_type, sender_id, msg_len, bin_data = records[0]
  items = []
  i = 0
  for (timestamp, msg_type, sender_id, msg_len, bin_data) in records:
    sbp = SBP(msg_type, sender_id, msg_len, bin_data, 0x1337)
    try:
      _SBP_TABLE[msg_type](sbp)
      deltat = (timestamp - start_t)*1000.
      item = (deltat, timestamp, sbp, dispatch(sbp))
      items.append(item)
      m = {"delta": deltat,
           "timestamp": timestamp,
           "data": dispatch(sbp).to_json_dict(),
           "metadata": {}}
      new_datafile.write(json.dumps(m) + "\n")
    except Exception as exc_info:
      print "Exception received for message type {0}".format(_SBP_TABLE[msg_type])
      i += 1
      continue
  print "Of %d records, skipped %i." % (len(records), i)
  return items

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Mavlink to SBP JSON converter')
  parser.add_argument("dataflashfile",
                      help="the dataflashfile to convert.")
  parser.add_argument('-o', '--outfile',
                      default=["serial_link_datflash_convert.log.json"], nargs=1,
                      help='specify the name of the file output.')
  args = parser.parse_args()
  return args

def main():
  args = get_args()
  filename = args.dataflashfile
  outfile = args.outfile[0]
  f = extractSBP(filename)
  g = rewrite(f,outfile)
  print "JSON SBP log succesfully written to {0}.".format(outfile)

if __name__ == "__main__":
  main()
