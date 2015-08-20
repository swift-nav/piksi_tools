"""
Takes in a dataflish BIN file and produces an SBP JSON log file with the following record fields:

 {"delta": msec offset since beginning of run,
  "timestamp": UTC timestamp (sec),
  "data":  JSON representation of SBP message specialized to message type (like MsgBaselineNED),
  "metadata": dictionary of tags, optional
  }

Requirements:

  pip install pymavlink
  sudo pip install sbp

"""
from pymavlink.DFReader import DFReader_binary




"""
This function takes in a filename for a ArduPilot dataflash log,
and writes a separate file to disk when a timegap is greater than
the value passed in

"""
def split_logs(filename, seconds2split, prefix=None):
  log = DFReader_binary(filename)
  first = True
  previous_ts = 0
  starting_offset = 0
  part = 0
  if prefix:
    outfile= prefix+filename
  else:
    outfile = filename
  while True:
    m = log.recv_msg()
    if m is None:
      with open(outfile+"."+str(part), 'w') as fd :
        fd.write(log.data[starting_offset:])
      print "split {0} into {1} segments".format(filename, part+1)
      break
    elif not first:
      timediff = m._timestamp - previous_ts
      if timediff > seconds2split:
        with open(outfile+"."+str(part), 'w') as fd :
          before_message = log.offset-len(m.binary)
          fd.write(log.data[starting_offset:before_message])
          starting_offset = before_message
          part+=1
    else:
      first = False
    previous_ts = m._timestamp


def get_args():
  """
  Get and parse arguments.

  """
  import argparse
  parser = argparse.ArgumentParser(description='Mavlink to SBP JSON converter')
  parser.add_argument("dataflashfile",
                      help="the dataflashfile to convert.")
  parser.add_argument('-t', '--timestep',
                      default=[10], nargs=1,
                      help='number of seconds gap at which to split a file')
  parser.add_argument('-prefix', '--prefix',
                     default=[None], nargs=1,
                     help='file prefix')
  args = parser.parse_args()
  return args

def main():
  args = get_args()
  filename = args.dataflashfile
  split_logs(filename, float(args.timestep[0]), args.prefix[0])
  return 0
if __name__ == "__main__":
  main()
