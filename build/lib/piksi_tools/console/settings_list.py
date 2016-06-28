#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

import yaml
import pprint
import sys
from piksi_tools.console.utils import determine_path
import os

class SettingsList():
  list_of_dicts = list()

  def __str__(self):
    pp = pprint.PrettyPrinter(indent=2)
    pp.pprint(self.list_of_dicts)

  def get_dict(self, group, name):
    for element in self.list_of_dicts:
        if element['name'] == name and element['group'] == group:
          return element

  def get_field(self, group, name,field):
    returnvar = ""
    # confirm our class actually has list_of_dicts
    if self.list_of_dicts:
      thisdict = self.get_dict(group, name)
      if thisdict and isinstance(thisdict, dict):
        returnvar = thisdict.get(field,"")
      else:
        if not self.warned_dict.get(name+group, False):
          print "Error in settings list parsed yaml file."
          print "No entry for name  {0} and group is {1}".format(name,group)
          self.warned_dict[name+group] = True
    if not returnvar:
      returnvar = ""
    return returnvar

  def return_groups(self):
    output = []
    # confirm our class actually has list_of_dicts
    group_set = set()
    for element in self.list_of_dicts:
      group = element['group']
      if group not in group_set:
        output.append(element['group'])
        group_set.add(group)
    return output


  def __init__(self,filename):
    try:
      # check if filename exists (absolute or relative path can be given)
      if os.path.isfile(filename):
        path_to_file = filename
      # if it doesn't exist, try and see if it's in the dir as the script
      else:
        path_to_file = os.path.join(determine_path(), filename)
      stram = open(path_to_file, "r")
      temp_dict = yaml.load(stram)
      self.list_of_dicts = temp_dict
      self.warned_dict = {}
      # inform user of success or failure
      print "Loaded settings yaml file from path " + path_to_file
      print "Number of settings loaded {0}".format(len(self.list_of_dicts))
    except:
      import traceback
      traceback.print_exc()
