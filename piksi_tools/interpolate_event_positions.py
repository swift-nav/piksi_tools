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

def fix_trigger_rollover(message_type,msg_tow, numofmsg):
  # fix all roll-overs 
  pre_tow = msg_tow[0]
  itt=1
  while itt<numofmsg :
    if (pre_tow- msg_tow[itt]) > 261000 and (pre_tow- msg_tow[itt]) < 263000 and message_type[itt] == "MsgExtEvent":
      msg_tow[itt] +=  ((1/16368000.0 * 2**32) * 1000)
    pre_tow=msg_tow[itt]
    itt+=1
  return

def fix_trigger_debounce(message_type, msg_tow, numofmsg, debouncetime):
  # replaces all trigger debouncws with TOW value 0 
  prev_trigger_tow = 0
  itt=0
  while itt<numofmsg:
    if (msg_tow[itt]- prev_trigger_tow)<debouncetime and message_type[itt]=="MsgExtEvent":
      msg_tow[itt]=0
    elif message_type[itt]=="MsgExtEvent" :
      prev_trigger_tow = msg_tow[itt]

    itt += 1
  return

def get_leftbound (message_type, msg_tow, trigger_tow,msgout, numofmsg):
  itt=0
  leftbound=0
  while itt<numofmsg:
    if msg_tow[itt]<trigger_tow and msg_tow[itt]>leftbound and message_type[itt] == msgout:
      leftbound = msg_tow[itt]
    itt+=1
  return leftbound

def get_rightbound (message_type, msg_tow, trigger_tow,msgout, numofmsg):
  itt=0
  rightbound=msg_tow[numofmsg-1]
  while itt<numofmsg:
    if msg_tow[itt]>trigger_tow and msg_tow[itt]<rightbound and message_type[itt] == msgout:
      rightbound = msg_tow[itt]
    itt+=1
  return rightbound
def get_position_parameter(message_type,msg_tow,msg_position, tow, numofmsg, msgout):
  itt=0
  value=0
  while itt<numofmsg:
    if msg_tow[itt]==tow and message_type[itt]== msgout:
      value= msg_position[itt]
    itt+=1
  return value

def get_trigger_positions(message_type,msg_tow,msgout,numofmsg, msg_horizontal, msg_vertical, msg_depth):
  # extracts the position at the trigger tow using interpolation subroutine
  itt=0
  while itt<numofmsg:
    if message_type[itt] == "MsgExtEvent" and msg_tow[itt] > 0:
      #get left and right tow bounds 
      left = get_leftbound(message_type,msg_tow,msg_tow[itt],msgout,numofmsg)
      right = get_rightbound(message_type,msg_tow,msg_tow[itt],msgout,numofmsg)

      # get left and right vertical horizontal and depth positions
      left_h = get_position_parameter(message_type,msg_tow,msg_horizontal, left, numofmsg, msgout)
      right_h = get_position_parameter(message_type,msg_tow,msg_horizontal, right, numofmsg, msgout)
      left_v = get_position_parameter(message_type,msg_tow,msg_vertical, left, numofmsg, msgout)
      right_v= get_position_parameter(message_type,msg_tow,msg_vertical, right, numofmsg, msgout)
      left_d= get_position_parameter(message_type,msg_tow,msg_depth, left, numofmsg, msgout)
      right_d= get_position_parameter(message_type,msg_tow,msg_depth, right, numofmsg, msgout)


      # interpolate trigger position
      msg_horizontal[itt]=lin_interp(left_h, right_h, left, right, msg_tow[itt])
      msg_vertical[itt]=lin_interp(left_v, right_v, left, right, msg_tow[itt])
      msg_depth[itt]=lin_interp(left_d, right_d, left, right, msg_tow[itt])
    itt+=1
  return 

def display_data(message_type,msg_tow,msg_horizontal,msg_vertical,msg_depth,msgtype,outfile, numofmsg,msg_flag):
  fout= open(outfile,'wt')
  writer = csv.writer(fout)
  if msgtype == 'MsgBaselineNED' :
    indexdata = ("TOW (ms)", "N (mm)", "E (mm)", "D (mm)")
  elif msgtype == 'MsgPosECEF' or msgtype == 'MsgBaselineECEF' :
    indexdata = ("TOW (ms)", "X (m)", "Y (m)", "Z (m)")
  elif msgtype == 'MsgPosLLH' :
    indexdata = ("TOW (ms)", "Lat (deg)", "Lon (deg)", "Height (m)")
  writer.writerow(indexdata + ("# of Sats", "Flags"))

  itt=0
  while itt<numofmsg:
    if message_type[itt]=="MsgExtEvent" and msg_tow[itt] > 0 :
      writer.writerow((msg_tow[itt],msg_horizontal[itt],msg_vertical[itt],msg_depth[itt],"0",msg_flag[itt]))
    itt+=1
  return 





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
        fix_trigger_rollover(message_type, msg_tow, numofmsg)
        print 'done roll'
        fix_trigger_debounce(message_type, msg_tow, numofmsg, debouncetime)
        print ' done bebounce'
        get_trigger_positions(message_type,msg_tow,msgtype,numofmsg, msg_horizontal, msg_vertical, msg_depth)
        print 'done interpolation'
        display_data(message_type,msg_tow,msg_horizontal,msg_vertical,msg_depth,msgtype,outfile, numofmsg,msg_flag)
        print 'done outputing data '

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
