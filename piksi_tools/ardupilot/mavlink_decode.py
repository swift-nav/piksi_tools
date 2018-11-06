"""
Takes in a dataflash BIN file and produces an SBP JSON log file with the following record fields:

 {"time": UTC timestamp (sec),
  "data":  JSON representation of SBP message specialized to message type (like MsgBaselineNED),
  "metadata": dictionary of tags, optional
  }

Requirements:

  sudo pip install sbp

"""
from sbp.table import dispatch, _SBP_TABLE
from sbp.msg import SBP
from struct import unpack
from datetime import datetime, timedelta

import json

ARDUPILOT_LOG_HEADER = bytearray([0xA3, 0x95])  # each Ardupilot log frame starts with "0xA3 0x95"

# Timestamp format : 2017-05-26T21:40:15.717000
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"
TIME_ORIGIN = "1980-01-06T00:00:00.000000"

FORMAT_SIZE_BYTES = {'B': 1,
                     'H': 2,
                     'I': 4,
                     'Q': 8,
                     }

"""
Format characters in the format string for mavlink binary log messages
(https://github.com/ArduPilot/ardupilot/blob/master/libraries/DataFlash/LogStructure.h)
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
Read a binary file until one of the searched keys is found

Parameters
----------
  log : File, rb
    Binary file to read
  searched_keys : tuple of bytearrays
    List of keys to search
    
Returns
-------
  key : bytearray
    First key found in the file from the searched_keys
"""


def search_binary_key(log, searched_keys):
  key = bytearray()
  for k in range(len(searched_keys[0])):
    key.append(bytes(0x0))
  while key not in searched_keys:
    byte = log.read(1)
    if len(byte):
      for i in range(len(key) - 1):
        key[i] = key[i + 1]
      key[2] = byte
    else:
      return None
  return key


class SBR:
  def __init__(self):
    self.time_us = None
    self.msg_type = None
    self.sender_id = None
    self.index = None
    self.pages = None
    self.msg_len = None
    self.msg = None


class SBRH(SBR):
  HEADER = bytearray([0xA3, 0x95, 0xE9])
  LABELS = "TimeUS,msg_flag,1,2,3,4,5,6"
  FORMAT_HEADER = 'QHHBBBB'  # Data format before binary message
  # Original FORMAT_HEADER = 'QQ' but msg_flag is a 8-bytes flag
  # (1-2:msg_type, 3-4:sender_id, 5:index, 6:pages, 7:msg_len, 8:reserved)
  FORMAT_BINARY = 'QQQQQQ'  # Data format for binary message
  SIZE = 64
  BINARY_SIZE = 48

  def __init__(self, binary):
    SBR.__init__(self)
    self.read_bytes(binary)
    print "SBRH: time_us = %d, msg_type = %d, sender_id = %d, index = %d, pages = %d, msg_len = %d" % \
          (self.time_us, self.msg_type, self.sender_id, self.index, self.pages, self.msg_len)

  def read_bytes(self, binary):
    if len(binary) == self.SIZE:
      start_index = 0
      end_index = FORMAT_SIZE_BYTES[self.FORMAT_HEADER[0]]
      self.time_us = unpack('<' + self.FORMAT_HEADER[0], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[1]]
      self.msg_type = unpack('<' + self.FORMAT_HEADER[1], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[2]]
      self.sender_id = unpack('<' + self.FORMAT_HEADER[2], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[3]]
      self.index = unpack('<' + self.FORMAT_HEADER[3], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[4]]
      self.pages = unpack('<' + self.FORMAT_HEADER[4], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[5]]
      self.msg_len = unpack('<' + self.FORMAT_HEADER[5], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[6]]
      # DO NOTHING CAUSE THIS IS A RESERVED FIELD
      self.msg = binary[end_index:]
    else:
      raise ValueError("Binary size inconsistent")


class SBRM(SBR):
  HEADER = bytearray([0xA3, 0x95, 0xEA])
  LABELS = "TimeUS,msg_flag,1,2,3,4,5,6,7,8,9,10,11,12,13"
  FORMAT_HEADER = 'QHHBBBB'  # Data format before binary message
  # Original FORMAT_HEADER = 'QQ' but msg_flag is a 8-bytes flag
  # (1-2:msg_type, 3-4:sender_id, 5:index, 6:pages, 7:msg_len, 8:reserved)
  FORMAT_BINARY = 'QQQQQQQQQQQQQ'  # Data format for binary message
  SIZE = 120
  BINARY_SIZE = 104

  def __init__(self, binary):
    SBR.__init__(self)
    self.read_bytes(binary)
    print "SBRM: time_us = %d, msg_type = %d, sender_id = %d, index = %d, pages = %d, msg_len = %d" % \
          (self.time_us, self.msg_type, self.sender_id, self.index, self.pages, self.msg_len)

  def read_bytes(self, binary):
    if len(binary) == self.SIZE:
      start_index = 0
      end_index = FORMAT_SIZE_BYTES[self.FORMAT_HEADER[0]]
      self.time_us = unpack('<' + self.FORMAT_HEADER[0], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[1]]
      self.msg_type = unpack('<' + self.FORMAT_HEADER[1], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[2]]
      self.sender_id = unpack('<' + self.FORMAT_HEADER[2], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[3]]
      self.index = unpack('<' + self.FORMAT_HEADER[3], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[4]]
      self.pages = unpack('<' + self.FORMAT_HEADER[4], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[5]]
      self.msg_len = unpack('<' + self.FORMAT_HEADER[5], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT_HEADER[6]]
      # DO NOTHING CAUSE THIS IS A RESERVED FIELD
      self.msg = binary[end_index:]
    else:
      raise ValueError("Binary size inconsistent")


class GPS:
  HEADER = bytearray([0xA3, 0x95, 0x82])
  HEADER2 = bytearray([0xA3, 0x95, 0x83])
  FORMAT = "QBIHBcLLefffB"
  LABELS = "TimeUS,Status,GMS,GWk,NSats,HDop,Lat,Lng,Alt,Spd,GCrs,VZ,U"
  SIZE = 43

  def __init__(self, binary):
    self.time_us = None
    self.gms = None
    self.gwk = None
    self.read_bytes(binary)

  def read_bytes(self, binary):
    if len(binary) == self.SIZE:
      start_index = 0
      end_index = FORMAT_SIZE_BYTES[self.FORMAT[0]]
      self.time_us = unpack('<' + self.FORMAT[0], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT[1]]
      # DO NOTHING CAUSE WE DON'T CARE OF STATUS
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT[2]]
      self.gms = unpack('<' + self.FORMAT[2], binary[start_index:end_index])[0]
      start_index = end_index
      end_index = start_index + FORMAT_SIZE_BYTES[self.FORMAT[3]]
      self.gwk = unpack('<' + self.FORMAT[3], binary[start_index:end_index])[0]
    else:
      raise ValueError("Binary size inconsistent")


def get_first_gps_message(filename):
  with open(filename, "rb") as log:
    last_gps = None
    headers = [GPS.HEADER, GPS.HEADER2]
    while True:
      key = search_binary_key(log, headers)
      headers = [key]
      binary = log.read(GPS.SIZE)
      gps = GPS(binary)
      if last_gps and last_gps.gwk and gps.gwk and last_gps.gwk == gps.gwk:
        return gps
      last_gps = gps


def gps_time_to_datetime(gps_week, gps_milliseconds, time_us):
  epoch = datetime.strptime(TIME_ORIGIN, TIMESTAMP_FORMAT)
  elapsed = timedelta(days=(gps_week * 7), microseconds=(gps_milliseconds * 1000 + time_us))
  return datetime.strftime(epoch + elapsed, TIMESTAMP_FORMAT)


class SBPExtractor:
  def __init__(self, sender_id, gps):
    self.gps = gps
    self.last_m = None
    self.last_last_m = None
    self.num_msgs = 0
    self.sender_id = sender_id
    self.extracted_data = []
    self.messages = []

  def treat_message(self, m):
    self.messages.append(m)
    if m.index == m.pages:
      self.flush()

  def flush(self):
    timestamp = gps_time_to_datetime(self.gps.gwk, self.gps.gms, self.messages[0].time_us - self.gps.time_us)
    msg_type = self.messages[0].msg_type
    msg_len = self.messages[0].msg_len
    bin_data = ''
    for message in self.messages:
      bin_data += message.msg
    bin_data = bin_data[:msg_len]
    if len(bin_data) != msg_len:
      print "Length of SBP message inconsistent for msg_type {0}.".format(msg_type)
      print "Expected Length {0}, Actual Length {1}".format(msg_len, len(bin_data))
    else:
      self.extracted_data.append((timestamp, msg_type, self.sender_id, msg_len, bin_data))
      self.num_msgs += 1
      self.messages = []


"""
This function takes in a filename for a ArduPilot dataflash log,
and returns an array of (timestamp, bytearray) tuples.
The bytearray contains raw SBP binary data logged directly from the serial port.
Each tuple should contain exactly one SBP message.
"""


def extract_sbp(filename):
  gps = get_first_gps_message(filename)
  extractors = {}

  with open(filename, "rb") as log:
    while True:
      # We iterate through logs to find the SBRH or SBRM message
      # SBRH msgs are the first 64 bytes of any sbp message, or the entire message
      # if the message is smaller than 64 bytes
      # SBRM msgs are the next n bytes if the original message is longer than 64 bytes
      key = search_binary_key(log, [SBRH.HEADER, SBRM.HEADER])
      if key == SBRH.HEADER:
        binary = log.read(SBRH.SIZE)
        if len(binary) == SBRH.SIZE:
          m = SBRH(binary)
        else:
          break
      elif key == SBRM.HEADER:
        binary = log.read(SBRM.SIZE)
        if len(binary) == SBRM.SIZE:
          m = SBRM(binary)
        else:
          break
      else:
        break

      if m.msg_len:
        if m.sender_id in extractors.keys():
          extractors[m.sender_id].treat_message(m)
        else:
          extractors[m.sender_id] = SBPExtractor(m.sender_id, gps)
          extractors[m.sender_id].treat_message(m)

    extracted_data = {}
    for sender_id, extractor in extractors.iteritems():
      print "sender_id : {0}, extracted {1} messages".format(sender_id, extractor.num_msgs)
      extracted_data[sender_id] = extractor.extracted_data

    return extracted_data


def rewrite(records_dict, outfile):
  """
  Returns array of (timestamp in sec, SBP object, parsed).
  skips unparseable objects.

  """
  total_items = []
  for sender, records in records_dict.iteritems():
    new_datafile = open("{0}_{1}.{2}".format(outfile, sender, "sbp.json"), 'w')
    if not records:
      print "No SBP log records passed to rewrite function. Exiting."
      return

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
      except Exception:
        print "Exception received for message type {0}.".format(_SBP_TABLE[msg_type])
        import traceback
        print traceback.format_exc()
        i += 1
        continue
    print "sender_id: %d, of %d records, skipped %i." % (sender, len(records), i)
    total_items.append(items)
  return total_items


def get_args():
  """
  Get and parse arguments.

  """
  import argparse
  parser = argparse.ArgumentParser(description='Mavlink to SBP JSON converter')
  parser.add_argument("dataflashfile",
                      help="the dataflashfile to convert.")
  parser.add_argument('-o', '--outfile',
                      default=["serial_link_dataflash_convert.log.json"], nargs=1,
                      help='specify the name (without the extension) of the file output.')
  args = parser.parse_args()
  return args


def main():
  args = get_args()
  filename = args.dataflashfile
  outfile = args.outfile[0]
  f = extract_sbp(filename)
  rewrite(f, outfile)
  print "JSON SBP log successfully written to {0}.".format(outfile)
  return 0


if __name__ == "__main__":
  main()
