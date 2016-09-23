"""
Takes in a dataflish BIN file and produces an SBP JSON log file with the following record fields:

 {"time": UTC timestamp (sec),
  "data":  JSON representation of SBP message specialized to message type (like MsgBaselineNED),
  "metadata": dictionary of tags, optional
  }

Requirements:

  pip install pymavlink
  sudo pip install sbp

"""
from pymavlink.DFReader import DFReader_binary
from sbp.table import dispatch, _SBP_TABLE
from sbp.msg import SBP

import json

SBR1_DATASTART = 16
SBR2_DATASTART = 13

"""
This function takes in a filename for a ArduPilot dataflash log,
and returns an array of (timestamp, bytearray) tuples.
The bytearray contains raw SBP binary data logged directly from the serial port.
Each tuple should contain exactly one SBP message.

This decoder requires pymavlink commit 0b6e5ab1f6d7911d408aaee8a4ec7a457e238399
which defines the "get_raw_msgbuf" method on the DFReader class.
This commit is currently in the denniszollo fork on Github and is
pull request #411 against master

"""
def extractSBP(filename):
  extracted_data = []
  log = DFReader_binary(filename)
  last_m = None
  num_msgs = 0
  while True:
    # we use mavlinks recv_match function to iterate through logs
    # and give us the SBR1 or SBR2 message
    # SBR1 msgs are the first 64 bytes of any sbp message, or the entire message
    # if the message is smaller than 64 bytes
    # SBR2 msgs are the next n bytes if the original message is longer than 64 bytes
    m = log.recv_match(type=['SBR1', 'SBR2'])
    if m is None:
      break
    bin_data = None
    timestamp = None
    msg_type = None
    sender_id = None
    msg_len = None
    if last_m != None and last_m.get_type() == 'SBR1' and m.get_type() == 'SBR2':
      # If the last message was an SBR1 and the current message is SBR2
      # we combine the two into one SBP message
      msg_len = last_m.msg_len
      timestamp = getattr(last_m, '_time', 0.0)
      binary = last_m.binary
      bin_data = bytearray(last_m.binary[SBR1_DATASTART:SBR1_DATASTART+64]
                 + m.binary[SBR2_DATASTART:SBR2_DATASTART+msg_len-64])
      assert len(bin_data) == msg_len, "Length of binary data decoded \
                                        from dataflash does not match msg_len in header"
      msg_type = last_m.msg_type
      sender_id = last_m.sender_id
      last_m = m
    elif last_m and last_m.get_type() == 'SBR1' and m.get_type() == 'SBR1':
      # If the last message  was SBR1 and this one is SBR1, we extract the last one
      # and save this one until the next iteration
      msg_len = last_m.msg_len
      binary = last_m.binary
      assert binary, "binary empty"
      timestamp = getattr(last_m, '_time', 0.0)
      msg_type = last_m.msg_type
      sender_id = last_m.sender_id
      bin_data = bytearray(last_m.binary[SBR1_DATASTART:SBR1_DATASTART+msg_len])
      last_m = m
    elif last_m and last_m.get_type() == "SBR2" and m.get_type() == "SBR1":
      # just save current message as the last_m.
      # We wait until next message received to know whether it is a complete message
      last_m = m
    else:
      # This should only happen on our first iteration
      if last_m:
        assert num_msgs == 0, "This branch is expected to execute on first message" \
                            " only.  This is a serious logical error in the decoder."
      last_m = m
    if bin_data != None:
      if len(bin_data) != msg_len:
        print "Length of SBP message inconsitent for msg_type {0}.".format(msg_type)
        print "Expected Length {0}, Actual Length {1}".format(msg_len, len(bin_data))
      extracted_data.append((timestamp, msg_type, sender_id, msg_len, bin_data))
      num_msgs += 1
  print "extracted {0} messages".format(num_msgs)
  return extracted_data

def rewrite(records, outfile):
  """
  Returns array of (timestamp in sec, SBP object, parsed).
  skips unparseable objects.

  """
  new_datafile = open(outfile, 'w')
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
      item = (timestamp, sbp, dispatch(sbp))
      items.append(item)
      m = {"time": timestamp,
           "data": dispatch(sbp).to_json_dict(),
           "metadata": {}}
      new_datafile.write(json.dumps(m) + "\n")
    except Exception as exc_info:
      print "Exception received for message type {0}.".format(_SBP_TABLE[msg_type])
      import traceback
      print traceback.format_exc()
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
  g = rewrite(f, outfile)
  print "JSON SBP log succesfully written to {0}.".format(outfile)
  return 0
if __name__ == "__main__":
  main()
