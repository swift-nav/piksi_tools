"""
interpolate_event_trigger.py allows user to analyze log files
with external event triggers.
"""

from sbp.client.loggers.json_logger import JSONLogIterator
from sbp.ext_events import SBP_MSG_EXT_EVENT
import csv

def lin_interp(o, n, otow, ntow, ttow):
  """
  Linearly interpolates distance.
  
  Parameters
  ----------
  o : integer
    distance previous to trigger
  n : integer
    distance prior to trigger
  otow : integer
    TOW of data packet previous to trigger
  ntow : integer
    TOW of data packet after trigger
  ttow : integer
    TOW of trigger 
  """
  d = float(n-o)
  t = (ntow-otow) 
  v = d/t
  return o+(v*(ttow-otow))


def write_positions(infile, outfile, msgtype):
  """
  Organize and output data to log file.

  Parameters
  ----------
  infile : string
    Log file to get data from.
  outfile : string
    Output file.
  """

  with JSONLogIterator(infile) as log:
    log = log.next()
    lasttow = 0
    deltalasttrigger = 0
    positiondesplayed = 1
    debouncetime = 1000
    previous_msg = None
    fileoutput = open(outfile, 'wt')
    writer = csv.writer(fileoutput)
    if msgtype == 'MsgBaselineNED' :
      writer.writerow(("TOW (ms)","N (mm)","E (mm)","D (mm)","# of Sats",
                     "Flags","H Accuracy (mm)","V Accuracy (mm)"))
    if msgtype == 'MsgPosECEF' :
      writer.writerow(("TOW (ms)","X (m)","Y (m)","Z (m)","# of Sats",
                     "Flags","Accuracy (mm)"))
    if msgtype == 'MsgPosLLH' :
      writer.writerow(("TOW (ms)","Lat (deg)","Lon (deg)","Height (m)","# of Sats",
                     "Flags","H Accuracy (mm)","V Accuracy (mm)"))
    if msgtype == 'MsgBaselineECEF' :
      writer.writerow(("TOW (ms)","X (mm)","Y (mm)","Z (mm)","# of Sats",
                     "Flags","Accuracy (mm)")) 

    while True:
      try:
        msg, metadata = log.next()
        hostdelta = metadata['delta']
        hosttimestamp = metadata['timestamp']
        
        if msg.__class__.__name__ == "MsgExtEvent" :
          deltalasttrigger = msg.tow - lasttow
          if deltalasttrigger > debouncetime:
            lasttow = msg.tow
            positiondesplayed = 0

        if msg.__class__.__name__ == msgtype and positiondesplayed == 0 :
          if msgtype == "MsgBaselineECEF" or msgtype == "MsgPosECEF" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_x = lin_interp(previous_msg.x,msg.x,previous_msg.tow,msg.tow,lasttow)
              trigger_y = lin_interp(previous_msg.y,msg.y,previous_msg.tow,msg.tow,lasttow)
              trigger_z = lin_interp(previous_msg.z,msg.z,previous_msg.tow,msg.tow,lasttow)
              writer.writerow((lasttow,trigger_x,trigger_y,trigger_z,previous_msg.n_sats,
                               msg.flags,previous_msg.accuracy))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((lasttow,previous_msg.x,previous_msg.y,previous_msg.z,previous_msg.n_sats,
                               msg.flags,previous_msg.accuracy))
          if msgtype == "MsgBaselineNED" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_n = lin_interp(previous_msg.n,msg.n,previous_msg.tow,msg.tow,lasttow)
              trigger_e = lin_interp(previous_msg.e,msg.e,previous_msg.tow,msg.tow,lasttow)
              trigger_d = lin_interp(previous_msg.d,msg.d,previous_msg.tow,msg.tow,lasttow)
              writer.writerow((lasttow,trigger_n,trigger_e,trigger_d,previous_msg.n_sats,
                               msg.flags,previous_msg.h_accuracy,previous_msg.v_accuracy))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((lasttow,previous_msg.n,previous_msg.e,previous_msg.d,previous_msg.n_sats,
                               msg.flags,previous_msg.h_accuracy,previous_msg.v_accuracy))
          if msgtype == "MsgPosLLH" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_lat = lin_interp(previous_msg.lat,msg.lat,previous_msg.tow,msg.tow,lasttow)
              trigger_lon = lin_interp(previous_msg.lon,msg.lon,previous_msg.tow,msg.tow,lasttow)
              trigger_height = lin_interp(previous_msg.height,msg.height,previous_msg.tow,msg.tow,lasttow)
              writer.writerow((lasttow,trigger_lat,trigger_lon,trigger_height,previous_msg.n_sats,
                               msg.flags,previous_msg.h_accuracy,previous_msg.v_accuracy))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((lasttow,previous_msg.lat,previous_msg.lon,previous_msg.height,previous_msg.n_sats,
                               msg.flags,previous_msg.h_accuracy,previous_msg.v_accuracy))
          positiondesplayed = 1
        if msg.__class__.__name__ == msgtype :
          previous_msg = msg
      except StopIteration:
        print "reached end of file after {0} seconds".format(hostdelta)
        fileoutput.close()
        return

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='MetaData xml creator')
  parser.add_argument('-f', '--filename',
                      default=[None], nargs=1,
                      help="the template file from which to start")
  parser.add_argument('-o', '--outfile',
                      default=["output.csv"], nargs=1,
                      help='specify the name of the metadata xml file output.')
  parser.add_argument('-t', '--type', nargs=1,
                      default=['MsgBaselineNED'],
                      help='Type of message to interpolate')
  args = parser.parse_args()
  return args

if __name__ == '__main__':
  args = get_args()
  if args.type[0] == 'MsgBaselineNED' or args.type[0] == 'MsgPosECEF' or args.type[0] == 'MsgPosLLH' or args.type[0] == 'MsgBaselineECEF'  :
    if args.filename[0]:
      write_positions(args.filename[0], args.outfile[0], args.type[0])
    else :
      print "Please provide a filename argument"
  else :
    print "Incorrect Message Type!!"


