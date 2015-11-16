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
  Interpolation accurate to the mm.
  
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
  #print "o ",otow
  #print "t ",ttow
  #print "n ",ntow

  #assert otow<ttow<ntow , 'TOW values ERROR' 

  # assert to eliminate big end-point differences
  assert (ntow-otow)<3000, "Interpolation end-points for Trigger at TOW {0} too far away".format(ttow)

  d = float(n-o)
  t = (ntow-otow) 
  v = d/t
  return o+(v*(ttow-otow))


def write_positions(infile, outfile, msgtype, debouncetime):
  """
  Organize and output data to log file.

  Parameters
  ----------
  infile : string
    Log file to get data from.
  outfile : string
    Output file.
  msgtype : string
    type of parameters to analyze and output
  debouncetime : integer
    time in milliseconds to compensate for switch debounce 
  """

  with JSONLogIterator(infile) as log:
    log = log.next()
    triggertow = 0 # TOW of the trigger (used in interpolation function)
    deltalasttrigger = 0 # change in time of current trigger TOW to previous
    dataout = True # Boolean if interpulation of trigger TOW has happened or not
    previous_msg = None # Used to compare change in flag
    fileoutput = open(outfile, 'wt')
    writer = csv.writer(fileoutput)
    if msgtype == 'MsgBaselineNED' :
      indexdata = ("TOW (ms)", "N (mm)", "E (mm)", "D (mm)", 
                    "H Accuracy (mm)", "V Accuracy (mm)") 
    elif msgtype == 'MsgPosECEF' :
      indexdata = ("TOW (ms)", "X (m)", "Y (m)", "Z (m)", "Accuracy (mm)")
    elif msgtype == 'MsgPosLLH' :
      indexdata = ("TOW (ms)", "Lat (deg)", "Lon (deg)", "Height (m)",
                    "H Accuracy (mm)", "V Accuracy (mm)")
    elif msgtype == 'MsgBaselineECEF' :
      indexdata = ("TOW (ms)", "X (mm)", "Y (mm)", "Z (mm)", "Accuracy (mm)")
    writer.writerow(indexdata + ("# of Sats", "Flags"))

    while True:
      try:
        msg, metadata = log.next()
        hostdelta = metadata['delta']
        hosttimestamp = metadata['timestamp']
        
        if msg.__class__.__name__ == "MsgExtEvent" :
          deltalasttrigger = msg.tow - triggertow
          if deltalasttrigger > debouncetime:
            #print previous_msg.tow
            #print "trigger", msg.tow , "Flag",msg.flags
            triggertow = msg.tow
            dataout = False

        if msg.__class__.__name__ == msgtype and dataout == False :
          if (abs(triggertow - previous_msg.tow))/1000 >200 :
            writer.writerow(("RollOver ERROR!!",""))
          elif msgtype == "MsgBaselineECEF" or msgtype == "MsgPosECEF" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_x = lin_interp(previous_msg.x, msg.x, previous_msg.tow, msg.tow, triggertow)
              trigger_y = lin_interp(previous_msg.y, msg.y, previous_msg.tow, msg.tow, triggertow)
              trigger_z = lin_interp(previous_msg.z, msg.z, previous_msg.tow, msg.tow, triggertow)
              writer.writerow((triggertow, trigger_x, trigger_y, trigger_z, previous_msg.accuracy,
                              previous_msg.n_sats, msg.flags))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((triggertow, previous_msg.x, previous_msg.y, previous_msg.z,
                              previous_msg.accuracy, previous_msg.n_sats, previous_msg.flags))
          elif msgtype == "MsgBaselineNED" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_n = lin_interp(previous_msg.n, msg.n, previous_msg.tow, msg.tow, triggertow)
              trigger_e = lin_interp(previous_msg.e, msg.e, previous_msg.tow, msg.tow, triggertow)
              trigger_d = lin_interp(previous_msg.d, msg.d, previous_msg.tow, msg.tow, triggertow)
              writer.writerow((triggertow,trigger_n, trigger_e, trigger_d, previous_msg.h_accuracy,
                                previous_msg.v_accuracy, previous_msg.n_sats, msg.flags))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((triggertow, previous_msg.n, previous_msg.e, previous_msg.d, previous_msg.h_accuracy,
                                previous_msg.v_accuracy, previous_msg.n_sats, previous_msg.flags))
          elif msgtype == "MsgPosLLH" :
            if previous_msg.flags == msg.flags: #< interpolates only if lock type didn't change.
              trigger_lat = lin_interp(previous_msg.lat ,msg.lat, previous_msg.tow, msg.tow, triggertow)
              trigger_lon = lin_interp(previous_msg.lon ,msg.lon, previous_msg.tow, msg.tow, triggertow)
              trigger_height = lin_interp(previous_msg.height, msg.height, previous_msg.tow, msg.tow, triggertow)
              writer.writerow((triggertow, trigger_lat, trigger_lon, trigger_height, previous_msg.h_accuracy,
                                previous_msg.v_accuracy, previous_msg.n_sats, msg.flags))
            else: #< otherwise outputs previous data packet received.
              writer.writerow((triggertow, previous_msg.lat, previous_msg.lon, previous_msg.height, previous_msg.h_accuracy,
                                previous_msg.v_accuracy, previous_msg.n_sats, previous_msg.flags))
          #print msg.tow    
          dataout = True # boolean to make sure next position point doesn't get interpulated before a trigger
        if msg.__class__.__name__ == msgtype : 
          """ 
          stores every message being analyzed so it can be used to interpolate for next trigger.  
          """
          #print "msgtow ",msg.tow
          previous_msg = msg
        if msg.__class__.__name__=="MsgBaselineECEF":
          print msg
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
  parser.add_argument('-d', '--debouncetime', type=int ,
                      default=[1000], nargs=1,
                      help='specify the debounce time for trigger in ms')
  args = parser.parse_args()
  return args

if __name__ == '__main__':
  args = get_args()
  if args.type[0] == 'MsgBaselineNED' or args.type[0] == 'MsgPosECEF' or args.type[0] == 'MsgPosLLH' or args.type[0] == 'MsgBaselineECEF'  :
    if args.filename[0]:
      write_positions(args.filename[0], args.outfile[0], args.type[0], args.debouncetime[0])
    else :
      print "Please provide a filename argument"
  else :
    print "Incorrect Message Type!!"
