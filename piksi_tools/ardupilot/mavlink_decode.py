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
from sbp.table import dispatch, _SBP_TABLE
from sbp.msg import SBP
from struct import unpack

import json

ARDUPILOT_LOG_HEADER = bytearray([0xA3, 0x95])  # each Ardupilot log frame starts with "0xA3 0x95"

FORMAT_SIZE_BYTES = {'B': 1,
                     'H': 2,
                     'Q': 8,
                     }

"""
Format characters in the format string for mavlink binary log messages
  b   : int8_t
  B   : uint8_t
  h   : int16_t
  H   : uint16_t
  i   : int32_t
  I   : uint32_t
  f   : float
  d   : double
  n   : char[4]
  N   : char[16]
  Z   : char[64]
  c   : int16_t * 100
  C   : uint16_t * 100
  e   : int32_t * 100
  E   : uint32_t * 100
  L   : int32_t latitude/longitude
  M   : uint8_t flight mode
  q   : int64_t
  Q   : uint64_t
"""

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


def search_binary_key(file, searched_keys):
  key = bytearray()
  for k in range(len(searched_keys[0])):
    key.append(bytes(0x0))
  byte = bytes(0x0)
  while len(byte):
    if key in searched_keys:
      return key
    else:
      byte = file.read(1)
      for i in range(len(key)-1):
        key[i] = key[i+1]
      key[2] = byte
  return None


class SBR1:

  HEADER = bytearray([0xA3, 0x95, 0xE5])
  FORMAT_HEADER = 'QHHB'  # Data format before binary message
  FORMAT_BINARY = 'QQQQQQQQ'  # Data format for binary message
  SIZE = 77
  BINARY_SIZE = 64

  def __init__(self, bytes):
    self.time_us = None
    self.msg_type = None
    self.sender_id = None
    self.msg_len = None
    self.msg = None
    self.read_bytes(bytes)

  def read_bytes(self, bytes):
    if len(bytes) == self.SIZE:
      start_index = 0
      end_index = FORMAT_SIZE_BYTES[self.FORMAT_HEADER[0]]
      self.time_us = unpack('<'+self.FORMAT_HEADER[0], bytes[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[1]]
      self.msg_type = unpack('<'+self.FORMAT_HEADER[1], bytes[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[2]]
      self.sender_id = unpack('<'+self.FORMAT_HEADER[2], bytes[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[3]]
      self.msg_len = unpack('<'+self.FORMAT_HEADER[3], bytes[start_index:end_index])[0]
      self.msg = bytes[end_index:]


class SBR2:

  HEADER = bytearray([0xA3, 0x95, 0xE6])
  FORMAT_HEADER = 'QH'  # Data format before binary message
  FORMAT_BINARY = 'QQQQQQQQQQQQQ'  # Data format for binary message
  SIZE = 114
  BINARY_SIZE = 104

  def __init__(self, bytes):
    self.time_us = None
    self.msg_type = None
    self.msg = None
    self.read_bytes(bytes)

  def read_bytes(self, bytes):
    if len(bytes) == self.SIZE:
      start_index = 0
      end_index = FORMAT_SIZE_BYTES[self.FORMAT_HEADER[0]]
      self.time_us = unpack('<'+self.FORMAT_HEADER[0], bytes[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[1]]
      self.msg_type = unpack('<'+self.FORMAT_HEADER[1], bytes[start_index:end_index])[0]
      self.msg = bytes[end_index:]


def extractSBP(filename):
  extracted_data = []

  with open(filename, "rb") as log:
    last_m = None
    last_last_m = None
    num_msgs = 0

    while True:
      # We iterate through logs to find the SBR1 or SBR2 message
      # SBR1 msgs are the first 64 bytes of any sbp message, or the entire message
      # if the message is smaller than 64 bytes
      # SBR2 msgs are the next n bytes if the original message is longer than 64 bytes
      key = search_binary_key(log, [SBR1.HEADER, SBR2.HEADER])
      if key == SBR1.HEADER:
        bytes = log.read(SBR1.SIZE)
        if len(bytes) == SBR1.SIZE:
          m = SBR1(bytes)
        else:
          break
      elif key == SBR2.HEADER:
        bytes = log.read(SBR2.SIZE)
        if len(bytes) == SBR2.SIZE:
          m = SBR2(bytes)
        else:
          break
      else:
        break

      bin_data = None
      msg_type = None
      sender_id = None
      msg_len = None
      timestamp = None

      if last_m and isinstance(last_m, SBR1) and isinstance(m, SBR2):
        if last_m.BINARY_SIZE + m.BINARY_SIZE < last_m.msg_len:
          last_last_m = last_m
          last_m = m
        else:
          # If the last message was an SBR1 and the current message is SBR2
          # we combine the two into one SBP message
          msg_len = last_m.msg_len
          timestamp = last_m.time_us
          bin_data = last_m.msg + m.msg
          bin_data = bin_data[:msg_len]
          msg_type = last_m.msg_type
          sender_id = last_m.sender_id
          last_m = m

      elif last_last_m and last_m and isinstance(last_last_m, SBR1) and isinstance(last_m, SBR2) and isinstance(m, SBR2):
        # If the last message was an SBR1 and the current message is SBR2
        # we combine the two into one SBP message
        msg_len = last_last_m.msg_len
        timestamp = last_last_m.time_us
        bin_data = last_last_m.msg + last_m.msg + m.msg
        bin_data = bin_data[:msg_len]
        msg_type = last_last_m.msg_type
        sender_id = last_last_m.sender_id
        last_last_m = None
        last_m = m

      elif last_m and isinstance(last_m, SBR1) and isinstance(m, SBR1):
        # If the last message  was SBR1 and this one is SBR1, we extract the last one
        # and save this one until the next iteration
        msg_len = last_m.msg_len
        timestamp = last_m.time_us
        msg_type = last_m.msg_type
        sender_id = last_m.sender_id
        bin_data = last_m.msg[:msg_len]
        last_m = m
      elif last_m and isinstance(last_m, SBR2) and isinstance(m, SBR1):
        # just save current message as the last_m.
        # We wait until next message received to know whether it is a complete message
        last_m = m
      else:
        # This should only happen on our first iteration
        if last_m:
          assert num_msgs == 0, "This branch is expected to execute on first message" \
                              " only.  This is a serious logical error in the decoder."
        last_m = m
      if bin_data:
        if len(bin_data) != msg_len:
          print "Length of SBP message inconsitent for msg_type {0}.".format(msg_type)
          print "Expected Length {0}, Actual Length {1}".format(msg_len, len(bin_data))
        else :
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
