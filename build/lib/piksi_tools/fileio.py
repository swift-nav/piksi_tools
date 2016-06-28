#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Gareth McMullin <gareth@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import serial_link
import random
import array

from sbp.file_io import *
from sbp.client import *

MAX_PAYLOAD_SIZE = 255

class FileIO(object):
  def __init__(self, link):
    self.link = link
    self._seq = random.randint(0, 0xffffffff)

  def next_seq(self):
    self._seq += 1
    return self._seq

  def read(self, filename):
    """
    Read the contents of a file.

    Parameters
    ----------
    filename : str
        Name of the file to read.

    Returns
    -------
    out : str
        Contents of the file.
    """
    chunksize = MAX_PAYLOAD_SIZE
    seq = self.next_seq()
    buf = []
    while True:
      msg = MsgFileioReadReq(sequence=seq,
                             offset=len(buf),
                             chunk_size=chunksize,
                             filename=filename)
      self.link(msg)
      reply = self.link.wait(SBP_MSG_FILEIO_READ_RESP, timeout=1.0)
      if not reply:
        raise Exception("Timeout waiting for FILEIO_READ reply")
      # Why isn't this already decoded?
      reply = MsgFileioReadResp(reply)
      if reply.sequence != seq:
        raise Exception("Reply FILEIO_READ doesn't match request")
      chunk = reply.contents
      buf += chunk
      if len(chunk) == 0:
        return bytearray(buf)

  def readdir(self, dirname='.'):
    """
    List the files in a directory.

    Parameters
    ----------
    dirname : str (optional)
        Name of the directory to list. Defaults to the root directory.

    Returns
    -------
    out : [str]
        List of file names.
    """
    files = []
    seq = self.next_seq()
    while True:
      msg = MsgFileioReadDirReq(sequence=seq,
                                offset=len(files),
                                dirname=dirname)
      self.link(msg)
      reply = self.link.wait(SBP_MSG_FILEIO_READ_DIR_RESP, timeout=1.0)
      if not reply:
        raise Exception("Timeout waiting for FILEIO_READ_DIR reply")
      # Why isn't this already decoded?
      reply = MsgFileioReadDirResp(reply)
      if reply.sequence != seq:
        raise Exception("Reply FILEIO_READ_DIR doesn't match request")
      chunk = str(bytearray(reply.contents)).rstrip('\0')
      if len(chunk) == 0:
        return files
      files += chunk.split('\0')

  def remove(self, filename):
    """
    Delete a file.

    Parameters
    ----------
    filename : str
        Name of the file to delete.
    """
    msg = MsgFileioRemove(filename=filename)
    self.link(msg)

  def write(self, filename, data, offset=0, trunc=True):
    """
    Write to a file.

    Parameters
    ----------
    filename : str
        Name of the file to write to.
    data : str
        Data to write
    offset : int (optional)
        Offset into the file at which to start writing in bytes.
    trunc : bool (optional)
        Overwite the file, i.e. delete any existing file before writing. If
        this option is not specified and the existing file is longer than the
        current write then the contents of the file beyond the write will
        remain. If offset is non-zero then this flag is ignored.

    Returns
    -------
    out : str
        Contents of the file.
    """
    if trunc and offset == 0:
      self.remove(filename)
    # How do we calculate this from the MsgFileioWriteRequest class?
    chunksize = MAX_PAYLOAD_SIZE - len(filename) - 8
    seq = self.next_seq()
    while data:
      chunk = data[:chunksize]
      data = data[chunksize:]
      msg = MsgFileioWriteReq(sequence=seq,
                              filename=(filename + '\0' + chunk),
                              offset=offset)
      self.link(msg)
      reply = self.link.wait(SBP_MSG_FILEIO_WRITE_RESP, timeout=1.0)
      if not reply:
        raise Exception("Timeout waiting for FILEIO_WRITE reply")
      # Why isn't this already decoded?
      reply = MsgFileioWriteResp(reply)
      if reply.sequence != seq:
        raise Exception("Reply FILEIO_WRITE doesn't match request")
      offset += len(chunk)

def hexdump(data):
  """
  Print a hex dump.

  Parameters
  ----------
  data : indexable
      Data to display dump of, can be anything that supports length and index
      operations.
  """
  ret = ''
  ofs = 0
  while data:
    chunk = data[:16]
    data = data[16:]
    s = "%08X  " % ofs
    s += " ".join("%02X" % ord(c) for c in chunk[:8]) + "  "
    s += " ".join("%02X" % ord(c) for c in chunk[8:])
    s += "".join(" " for i in range(60 - len(s))) + "|"
    for c in chunk:
      s += c if 32 <= ord(c) < 128 else '.'
    s += '|\n'
    ofs += 16
    ret += s
  return ret

def print_dir_listing(files):
  """
  Print a directory listing.

  Parameters
  ----------
  files : [str]
      List of file names in the directory.
  """
  for f in files:
    print f

def get_args():
  """
  Get and parse arguments.
  """
  import argparse
  parser = argparse.ArgumentParser(description='Swift Nav File I/O Utility.')
  parser.add_argument('-r', '--read', nargs=1,
                     help='read a file')
  parser.add_argument('-l', '--list', default=None, nargs=1,
                     help='list a directory')
  parser.add_argument('-d', '--delete', nargs=1,
                     help='delete a file')
  parser.add_argument('-p', '--port',
                     default=[serial_link.SERIAL_PORT], nargs=1,
                     help='specify the serial port to use.')
  parser.add_argument("-b", "--baud",
                     default=[serial_link.SERIAL_BAUD], nargs=1,
                     help="specify the baud rate to use.")
  parser.add_argument("-v", "--verbose",
                     help="print extra debugging information.",
                     action="store_true")
  parser.add_argument("-x", "--hex",
                     help="output in hex dump format.",
                     action="store_true")
  parser.add_argument("-f", "--ftdi",
                     help="use pylibftdi instead of pyserial.",
                     action="store_true")
  return parser.parse_args()

def main():
  args = get_args()
  port = args.port[0]
  baud = args.baud[0]
  # Driver with context
  with serial_link.get_driver(args.ftdi, port, baud) as driver:
    # Handler with context
    with Handler(Framer(driver.read, driver.write, args.verbose)) as link:
      f = FileIO(link)

      try:
        if args.read:
          data = f.read(args.read[0])
          if args.hex:
            print hexdump(data)
          else:
            print data
        elif args.delete:
          f.remove(args.delete[0])
        elif args.list is not None:
          print_dir_listing(f.readdir(args.list[0]))
        else:
          print "No command given, listing root directory:"
          print_dir_listing(f.readdir())
      except KeyboardInterrupt:
        pass

if __name__ == "__main__":
  main()
