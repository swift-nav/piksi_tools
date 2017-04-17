
from sbp.client.loggers.json_logger import JSONLogIterator
from sbp.client.loggers.pickle_logger import PickleLogIterator
import json
import struct
import sbp
import sbp.table
import sys
sys.modules['sbp_piksi'] = sbp  # creates a packageA entry in sys.modules

def rewrite(datafiles, process_functions=[]):
  """
  Rewrite pickle file as a json file with a similar name
  Parameters
  ----------
  datafiles : list
      list of files on which to operate.
  process_functions : list
      list of functions to call on the message as it is converted
  """
  for f in datafiles:
      with open(f + ".json", 'w+') as log_file:
        with PickleLogIterator(f) as log:
          for delta, timestamp, msg in log.next():
            for process in process_functions:
                msg = process(msg)
            m = struct.pack("<HHB", msg.msg_type, msg.sender, len(msg.payload))
            m += msg.payload
            crc = sbp.crc16(m[1:])
            msg.crc = crc
            m = {"delta": delta,
                 "timestamp": timestamp,
                 "data": sbp.table.dispatch(msg).to_json_dict()}
            log_file.write(json.dumps(m) + "\n")
          print "Succesfully wrote json output to {0}".format(log_file)

def translate_emphemeris(msg):
  """
  Handle legacy ephemeris messages
  Parameters
  ----------
  msg : dictionary representing a SBP message
  Returns
  ----------
  updated message
  """
  if msg.msg_type==26:
    msg.msg_type = 70
  return msg

if __name__ == "__main__":
  """
  Main function for log translating.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Swift Nav SBP log converter.')
  parser.add_argument('datafiles',
                      nargs='+',
                      help='Specify the file(s) to rewrite from pickle to json')
  args = parser.parse_args()
  datafiles = args.datafiles
  rewrite(datafiles,[translate_emphemeris])


