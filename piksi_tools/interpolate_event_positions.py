"""
interpolate_event_trigger.py allows user to analyze log files
with external event triggers.
"""

from sbp.client.loggers.json_logger import JSONLogIterator
from sbp.ext_events import SBP_MSG_EXT_EVENT
import csv

def lin_interp(oldpos, newpos, oldtow, newtow, triggertow):
  """
  Linearly interpolates distance.
  Interpolation accurate to the mm.
  
  Parameters
  ----------
  o : integer
    distance previous to trigger
  n : integer
    distance prior to trigger
  oldtow : integer
    TOW of data packet previous to trigger
  newtow : integer
    TOW of data packet after trigger
  triggertow : integer
    TOW of trigger 
  """
  #Warning for not logical TOW values 
  if not(oldtow<triggertow<newtow) :
    print 'TOW values ERROR at {0}'.format(triggertow)

  #Warning for big end-point differences
  if (newtow- oldtow)>3000 :
    print "Interpolation end-points for Trigger at TOW {0} too far away".format(triggertow)

  d = float(newpos-oldpos)
  t = (newtow-oldtow) 
  v = d/t
  return oldpos+(v*(triggertow-oldtow))


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
    
    #declaring all lists 
    message_type=[]
    msg_tow=[]
    msg_horizontal=[]
    msg_vertical=[]
    msg_depth=[]
    msg_sats=[]
    msg_flag=[]
    numofmsg=0;



    while True:
      try:
        msg, metadata = log.next()
        hostdelta = metadata['delta']
        hosttimestamp = metadata['timestamp']
        valid_msg=["MsgBaselineECEF","MsgPosECEF","MsgBaselineNED","MsgPosLLH","MsgExtEvent"]
        #collect all data in lists
        if msg.__class__.__name__ in valid_msg :
          message_type.append(msg.__class__.__name__)
          msg_tow.append(msg.tow)
          msg_flag.append(msg.flags)
          if msg.__class__.__name__== "MsgBaselineECEF" or msg.__class__.__name__== "MsgPosECEF" :
            msg_horizontal.append(msg.x)
            msg_vertical.append(msg.y)
            msg_depth.append(msg.z)
            msg_sats.append(msg.n_sats)
          elif msg.__class__.__name__== "MsgBaselineNED":
            msg_horizontal.append(msg.n)
            msg_vertical.append(msg.e)
            msg_depth.append(msg.d)
            msg_sats.append(msg.n_sats)
          elif msg.__class__.__name__== "MsgPosLLH":
            msg_horizontal.append(msg.lat)
            msg_vertical.append(msg.lon)
            msg_depth.append(msg.height)
            msg_sats.append(msg.n_sats)
          elif msg.__class__.__name__ == "MsgExtEvent":
            print msg.tow
            msg_horizontal.append("0")
            msg_vertical.append("0")
            msg_depth.append("0")
            msg_sats.append("0")
          numofmsg+=1

      except StopIteration:
        print "reached end of file after {0} seconds".format(hostdelta)
        organize_trigger(message_type, msg_tow, numofmsg)
        print msg_tow
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
