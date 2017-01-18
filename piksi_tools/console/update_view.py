#!/usr/bin/env python
# Copyright (C) 2014 Swift Navigation Inc.
# Contact: Colin Beighley <colin@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.

from urllib2 import URLError
from time import sleep
from intelhex import IntelHex, HexRecordError
from pkg_resources import parse_version as pkparse_version

from sbp.bootload import MsgBootloaderJumpToApp
from sbp.piksi import MsgReset

from threading import Thread

from traits.api import HasTraits, String, Button, Instance, Bool, Directory
from traitsui.api import View, Item, UItem, VGroup, HGroup, InstanceEditor, Spring
from pyface.api import GUI, FileDialog, OK, ProgressDialog

from piksi_tools.version import VERSION as CONSOLE_VERSION
from piksi_tools import bootload
from piksi_tools import flash
import piksi_tools.console.callback_prompt as prompt
from piksi_tools.console.utils import determine_path

from update_downloader import UpdateDownloader, INDEX_URL
from output_stream import OutputStream

from piksi_tools.bootload_v3 import shell_command
from piksi_tools.fileio import FileIO
from sbp.logging import SBP_MSG_LOG

import sys, os
from pyface.image_resource import ImageResource
if getattr(sys, 'frozen', False):
    # we are running in a |PyInstaller| bundle
    basedir = sys._MEIPASS
    os.chdir(basedir)
else:
    # we are running in a normal Python environment
    basedir = determine_path()
icon = ImageResource('icon',
         search_path=['images', os.path.join(basedir, 'images')])

HT = 8
COLUMN_WIDTH = 100

HW_REV_LOOKUP = {
  'Piksi Multi': 'piksi_multi',
  'piksi_2.3.1': 'piksi_v2.3.1',
}

def parse_version(version):
  comp_string = version
  if version[0] == 'v':
    version = version[1:-1]
  pkparse_version(version.replace("dirty", "",))

class FirmwareFileDialog(HasTraits):

  file_wildcard = String("Intel HEX File (*.hex)|*.hex|All files|*")

  status = String('Please choose a file')
  choose_fw = Button(label='...', padding=-1)
  view = View(
               HGroup(UItem('status', resizable=True),
                      UItem('choose_fw', width=-0.1)),
             )

  def __init__(self, flash_type):
    """
    Pop-up file dialog to choose an IntelHex file, with status and button to
    display in traitsui window.
    """
    self.set_flash_type(flash_type)

  def set_flash_type(self, flash_type):
    """
    Parameters
    ----------
    flash_type : string
      Which Piksi flash to interact with ("M25" or "STM").
    """
    if not flash_type in ('bin', 'M25', 'STM'):
      raise ValueError("flash_type must be 'bin', 'M25' or 'STM'")
    if flash_type == 'bin':
      self.file_wildcard = "Binary image set (*.bin)|*.bin|All files|*"
    else:
      self.file_wildcard = "Intel HEX File (*.hex)|*.hex|All files|*"
    self._flash_type = flash_type
    self.ihx = None
    self.blob = None

  def clear(self, status):
    """
    Set text of status box and clear IntelHex file.

    Parameters
    ----------
    status : string
      Error text to replace status box text with.
    """
    self.ihx = None
    self.blob = None
    self.status = status

  def load_ihx(self, filepath):
    """
    Load IntelHex file and set status to indicate if file was
    successfully loaded.

    Parameters
    ----------
    filepath : string
      Path to IntelHex file.
    """
    if self._flash_type not in ('M25', 'STM'):
      self.clear("Error: Can't load Intel HEX File as image set binary")
      return

    try:
      self.ihx = IntelHex(filepath)
      self.status = os.path.split(filepath)[1]
    except HexRecordError:
      self.clear('Error: File is not a valid Intel HEX File')

    # Check that address ranges are valid for self._flash_type.
    ihx_addrs = flash.ihx_ranges(self.ihx)
    if self._flash_type == "M25":
      try:
        sectors = flash.sectors_used(ihx_addrs, flash.m25_addr_sector_map)
      except IndexError:
        self.clear('Error: HEX File contains restricted address ' + \
                        '(STM Firmware File Chosen?)')
    elif self._flash_type == "STM":
      try:
        sectors = flash.sectors_used(ihx_addrs, flash.stm_addr_sector_map)
      except:
        self.clear('Error: HEX File contains restricted address ' + \
                        '(NAP Firmware File Chosen?)')

  def load_bin(self, filepath):
    if self._flash_type != 'bin':
      self.clear("Error: Can't load binary file for M25 or STM flash")
      return

    try:
      self.blob = open(filepath, 'rb').read()
      self.status = os.path.split(filepath)[1]
    except:
      self.clear('Error: Failed to read binary file')

  def _choose_fw_fired(self):
    """ Activate file dialog window to choose IntelHex firmware file. """
    dialog = FileDialog(label='Choose Firmware File',
                        action='open', wildcard=self.file_wildcard)
    dialog.open()
    if dialog.return_code == OK:
      filepath = os.path.join(dialog.directory, dialog.filename)
      if self._flash_type == 'bin':
        self.load_bin(filepath)
      else:
        self.load_ihx(filepath)
    else:
      self.clear('Error while selecting file')

class PulsableProgressDialog(ProgressDialog):

  def __init__(self, max, pulsed=False):
    """
    Pop-up window for showing a process's progress.

    Parameters
    ----------
    max : int
      Maximum value of the progress bar.
    pulsed : bool
      Show non-partial progress initially.
    """
    super(PulsableProgressDialog, self).__init__()
    self.min = 0
    self.max = 0
    self.pulsed = pulsed
    self.passed_max = max

  def progress(self, count):
    """
    Update progress of progress bar. If pulsing initially, wait until count
    is at least 12 before changing to discrete progress bar.

    Parameters
    ----------
    count : int
      Current value of progress.
    """
    # Provide user feedback initially via pulse for slow sector erases.
    if self.pulsed:
      if count > 12:
        self.max = 100
        GUI.invoke_later(self.update, int(100*float(count)/self.passed_max))
    else:
      self.max = 100
      GUI.invoke_later(self.update, int(100*float(count)/self.passed_max))

class UpdateView(HasTraits):
  piksi_hw_rev = String('piksi_multi')
  is_v2 = Bool(False)

  piksi_stm_vers = String('Waiting for Piksi to send settings...', width=COLUMN_WIDTH)
  newest_stm_vers = String('Downloading Latest Firmware info...')
  piksi_nap_vers = String('Waiting for Piksi to send settings...')
  newest_nap_vers = String('Downloading Latest Firmware info...')
  local_console_vers = String('v' + CONSOLE_VERSION)
  newest_console_vers = String('Downloading Latest Console info...')

  erase_stm = Bool(True)
  erase_en = Bool(True)

  update_stm_firmware = Button(label='Update FW')
  update_nap_firmware = Button(label='Update NAP')
  update_full_firmware = Button(label='Update Piksi STM and NAP Firmware')

  updating = Bool(False)
  update_stm_en = Bool(False)
  update_nap_en = Bool(False)
  update_en = Bool(False)
  serial_upgrade = Bool(False)
  upgrade_steps = String("Firmware upgrade steps:")

  download_firmware = Button(label='Download Latest Firmware')
  download_directory = Directory("  Please choose a directory for downloaded firmware files...")
  download_stm = Button(label='Download', height=HT)
  download_nap = Button(label='Download', height=HT)
  downloading = Bool(False)
  download_fw_en = Bool(True)

  stm_fw = Instance(FirmwareFileDialog)
  nap_fw = Instance(FirmwareFileDialog)

  stream = Instance(OutputStream)

  view = View(
    VGroup(
      Item('piksi_hw_rev', label='Hardware Revision',
           editor_args={'enabled': False}, resizable=True),
      HGroup(
        VGroup(
          Item('piksi_stm_vers', label='Current', resizable=True, 
                 editor_args={'enabled': False}),
          Item('newest_stm_vers', label='Latest', resizable=True, 
                 editor_args={'enabled': False, 
                              'readonly_allow_selection': True}),
          Item('stm_fw', style='custom', show_label=True, \
               label="Local File", enabled_when='download_fw_en',
               visible_when='serial_upgrade',
               editor_args={'enabled': False}),
          HGroup(Item('update_stm_firmware', show_label=False, \
                     enabled_when='update_stm_en', visible_when='serial_upgrade'),
                Item('erase_stm', label='Erase STM flash\n(recommended)', \
                      enabled_when='erase_en', show_label=True, visible_when='is_v2')),
          show_border=True, label="Firmware Version"
        ),
        VGroup(
          Item('piksi_nap_vers', label='Current', resizable=True, 
               editor_args={'enabled': False}),
          Item('newest_nap_vers', label='Latest', resizable=True,
               editor_args={'enabled': False}),
          Item('nap_fw', style='custom', show_label=True, \
               label="Local File", enabled_when='download_fw_en',
               editor_args={'enabled': False}),
          HGroup(Item('update_nap_firmware', show_label=False, \
                      enabled_when='update_nap_en', visible_when='serial_upgrade'),
                 Item(width=50, label="                  ")),
          show_border=True, label="NAP Version",
          visible_when='is_v2'
          ),
        VGroup(
          Item('local_console_vers', label='Current', resizable=True,
               editor_args={'enabled': False}),
          Item('newest_console_vers', label='Latest',
                editor_args={'enabled': False}),
          label="Swift Console Version", show_border=True),
          ),
      UItem('download_directory', enabled_when='download_fw_en'),
      UItem('download_firmware', enabled_when='download_fw_en'),
      UItem('update_full_firmware', enabled_when='update_en', visible_when='is_v2'),
      VGroup(
        UItem('upgrade_steps', 
              visible_when='not serial_upgrade', style='readonly'),
        Item(
          'stream',
          style='custom',
          editor=InstanceEditor(),
          show_label=False,
        ),
      show_border=True,
      )
    )
  )

  def __init__(self, link, prompt=True, serial_upgrade=False):
    """
    Traits tab with UI for updating Piksi firmware.

    Parameters
    ----------
    link : sbp.client.handler.Handler
      Link for SBP transfer to/from Piksi.
    prompt : bool
      Prompt user to update console/firmware if out of date.
    """
    self.link = link
    self.settings = {}
    self.prompt = prompt
    self.python_console_cmds = {
      'update': self

    }
    try:
      self.update_dl = UpdateDownloader()
    except URLError:
      pass
    self.erase_en = True
    self.stm_fw = FirmwareFileDialog('bin')
    self.stm_fw.on_trait_change(self._manage_enables, 'status')
    self.nap_fw = FirmwareFileDialog('M25')
    self.nap_fw.on_trait_change(self._manage_enables, 'status')
    self.stream = OutputStream()
    self.serial_upgrade = serial_upgrade
    self.last_call_fw_version = None
    if not self.serial_upgrade:
      self.stream.write(
           "1. Insert the USB flash drive provided with your Piki Multi into "
           "your computer.  Select the flash drive root directory as the "
           "firmware download destination using the \"Please "
           "choose a directory for downloaded firmware files\" directory "
           "chooser above.  Press the \"Download Latest Firmware\" button.  "
           "This will download the latest Piksi Multi firmware file onto the "
           "USB flashdrive.\n"
           "2. Eject the drive from your computer and plug it "
           "into the Piksi Multi evaluation board.\n"
           "3. Reset your Piksi Multi and it will upgrade to the version "
           "on the USB flash drive. This should take less than 5 minutes.\n"
           "4. When the upgrade completes you will be prompted to remove the "
           "USB flash drive and reset your Piksi Multi.\n"
           "5. Verify that the firmware version has upgraded via inspection "
           "of the Current Firmware Version box on the Firmware Update Tab "
           "of the Swift Console.\n")

  def _manage_enables(self):
    """ Manages whether traits widgets are enabled in the UI or not. """
    if self.updating == True or self.downloading == True:
      self.update_stm_en = False
      self.update_nap_en = False
      self.update_en = False
      self.download_fw_en = False
      self.erase_en = False
    else:
      self.download_fw_en = True
      self.erase_en = True
      if self.stm_fw.ihx is not None or self.stm_fw.blob is not None:
        self.update_stm_en = True
      else:
        self.update_stm_en = False
        self.update_en = False
      if self.nap_fw.ihx is not None:
        self.update_nap_en = True
      else:
        self.update_nap_en = False
        self.update_en = False
      if self.nap_fw.ihx is not None and self.stm_fw.ihx is not None:
        self.update_en = True

  def _download_directory_changed(self):
    if self.update_dl:
      self.update_dl.set_root_path(self.download_directory)

  def _updating_changed(self):
    """ Handles self.updating trait being changed. """
    self._manage_enables()

  def _downloading_changed(self):
    """ Handles self.downloading trait being changed. """
    self._manage_enables()

  def _write(self, text):
    """
    Stream style write function. Allows flashing debugging messages to be
    routed to embedded text console.

    Parameters
    ----------
    text : string
      Text to be written to screen.
    """
    self.stream.write(text)
    self.stream.write('\n')
    self.stream.flush()

  def _update_stm_firmware_fired(self):
    """
    Handle update_stm_firmware button. Starts thread so as not to block the GUI
    thread.
    """
    try:
      if self._firmware_update_thread.is_alive():
        return
    except AttributeError:
      pass

    self._firmware_update_thread = Thread(target=self.manage_firmware_updates,
                                          args=("STM",))
    self._firmware_update_thread.start()

  def _update_nap_firmware_fired(self):
    """
    Handle update_nap_firmware button. Starts thread so as not to block the GUI
    thread.
    """
    try:
      if self._firmware_update_thread.is_alive():
        return
    except AttributeError:
      pass

    self._firmware_update_thread = Thread(target=self.manage_firmware_updates,
                                          args=("M25",))
    self._firmware_update_thread.start()

  def _update_full_firmware_fired(self):
    """
    Handle update_full_firmware button. Starts thread so as not to block the GUI
    thread.
    """
    try:
      if self._firmware_update_thread.is_alive():
        return
    except AttributeError:
      pass

    self._firmware_update_thread = Thread(target=self.manage_firmware_updates,
                                          args=("ALL",))
    self._firmware_update_thread.start()

  def _download_firmware(self):
    """ Download latest firmware from swiftnav.com. """
    self._write('')

    # Check that we received the index file from the website.
    if self.update_dl == None:
      self._write("Error: Can't download firmware files")
      return

    self.downloading = True
    status = 'Downloading Latest Firmware...'
    self.nap_fw.clear(status)
    self.stm_fw.clear(status)
    self._write(status)

    # Get firmware files from Swift Nav's website, save to disk, and load.
    if self.update_dl.index[self.piksi_hw_rev].has_key('fw'):
      try:
        self._write('Downloading Latest Multi firmware')
        filepath = self.update_dl.download_multi_firmware(self.piksi_hw_rev)
        self._write('Saved file to %s' % filepath)
        self.stm_fw.load_bin(filepath)
      except AttributeError:
        self.nap_fw.clear("Error downloading firmware")
        self._write("Error downloading firmware: index file not downloaded yet")
      except KeyError:
        self.nap_fw.clear("Error downloading firmware")
        self._write("Error downloading firmware: URL not present in index")
      except URLError:
        self.nap_fw.clear("Error downloading firmware")
        self._write("Error: Failed to download latest NAP firmware from Swift Navigation's website")
      self.downloading = False
      return

    try:
      self._write('Downloading Latest NAP firmware')
      filepath = self.update_dl.download_nap_firmware(self.piksi_hw_rev)
      self._write('Saved file to %s' % filepath)
      self.nap_fw.load_ihx(filepath)
    except AttributeError:
      self.nap_fw.clear("Error downloading firmware")
      self._write("Error downloading firmware: index file not downloaded yet")
    except KeyError:
      self.nap_fw.clear("Error downloading firmware")
      self._write("Error downloading firmware: URL not present in index")
    except URLError:
      self.nap_fw.clear("Error downloading firmware")
      self._write("Error: Failed to download latest NAP firmware from Swift Navigation's website")

    try:
      self._write('Downloading Latest STM firmware')
      filepath = self.update_dl.download_stm_firmware(self.piksi_hw_rev)
      self._write('Saved file to %s' % filepath)
      self.stm_fw.load_ihx(filepath)
    except AttributeError:
      self.stm_fw.clear("Error downloading firmware")
      self._write("Error downloading firmware: index file not downloaded yet")
    except KeyError:
      self.stm_fw.clear("Error downloading firmware")
      self._write("Error downloading firmware: URL not present in index")
    except URLError:
      self.stm_fw.clear("Error downloading firmware")
      self._write("Error: Failed to download latest STM firmware from Swift Navigation's website")

    self.downloading = False

  def _download_firmware_fired(self):
    """
    Handle download_firmware button. Starts thread so as not to block the GUI
    thread.
    """
    try:
      if self._download_firmware_thread.is_alive():
        return
    except AttributeError:
      pass

    self._download_firmware_thread = Thread(target=self._download_firmware)
    self._download_firmware_thread.start()

  def compare_versions(self):
    """
    To be called after latest Piksi firmware info has been received from
    device, to decide if current firmware on Piksi is out of date. Also informs
    user if the firmware was successfully upgraded. Starts a thread so as not
    to block GUI thread.
    """
    try:
      if self._compare_versions_thread.is_alive():
        return
    except AttributeError:
      pass

    self._compare_versions_thread = Thread(target=self._compare_versions)
    self._compare_versions_thread.start()

  def _compare_versions(self):
    """
    Compares version info between received firmware version / current console
    and firmware / console info from website to decide if current firmware or
    console is out of date. Prompt user to update if so. Informs user if
    firmware successfully upgraded.
    """
    # Check that settings received from Piksi contain FW versions.
    try:
      self.piksi_hw_rev = \
        HW_REV_LOOKUP[self.settings['system_info']['hw_revision'].value]
      self.piksi_stm_vers = \
        self.settings['system_info']['firmware_version'].value
    except KeyError:
      self._write("\nError: Settings received from Piksi don't contain firmware version keys. Please contact Swift Navigation.\n")
      return

    self.is_v2 = self.piksi_hw_rev.startswith('piksi_v2')
    if self.is_v2:
      self.stm_fw.set_flash_type('STM')
      self.serial_upgrade = True
    else:
      self.stm_fw.set_flash_type('bin')

    self._get_latest_version_info()

    # Check that we received the index file from the website.
    if self.update_dl == None:
      self._write("Error: No website index to use to compare versions with local firmware")
      return

    # Check if console is out of date and notify user if so.
    if self.prompt:
      local_console_version = parse_version(CONSOLE_VERSION)
      remote_console_version = parse_version(self.newest_console_vers)
      self.console_outdated = remote_console_version > local_console_version

      # we want to warn users using v2 regardless of version logic
      if self.console_outdated or self.is_v2:
        if not self.is_v2:
          console_outdated_prompt = \
          prompt.CallbackPrompt(
                                title="Swift Console Outdated",
                                actions=[prompt.close_button],
                                )
          console_outdated_prompt.text = \
              "Your console is out of date and may be incompatible\n" + \
              "with current firmware. We highly recommend upgrading to\n" + \
              "ensure proper behavior.\n\n" + \
              "Please visit http://support.swiftnav.com to\n" + \
              "download the latest version.\n\n" + \
              "Local Console Version :\n\t" + \
                  "v" + CONSOLE_VERSION + \
              "\nLatest Console Version :\n\t" + \
                  self.update_dl.index[self.piksi_hw_rev]['console']['version'] + "\n"
        else:
          console_outdated_prompt = \
          prompt.CallbackPrompt(
                                title="Swift Console Incompatible",
                                actions=[prompt.close_button],
                                )
          console_outdated_prompt.text = \
              "Your console is incompatible with your hardware revision.\n" + \
              "We highly recommend using a compatible console version\n" + \
              "to ensure proper behavior.\n\n" + \
              "Please visit http://support.swiftnav.com to\n" + \
              "download the latest compatible version.\n\n" + \
              "Current Hardware revision :\n\t" + \
                   self.piksi_hw_rev + \
              "\nLast supported Console Version: \n\t" + \
                  self.update_dl.index[self.piksi_hw_rev]['console']['version'] + "\n"

        console_outdated_prompt.run()

      # For timing aesthetics between windows popping up.
      sleep(0.5)

      # Check if firmware is out of date and notify user if so.
      local_stm_version = parse_version(
          self.settings['system_info']['firmware_version'].value)
      remote_stm_version = parse_version(self.newest_stm_vers)

      self.fw_outdated = remote_stm_version > local_stm_version

      # Record firmware version reported each time this callback is called.
      self.last_call_fw_version = local_stm_version

      if self.fw_outdated:
        fw_update_prompt = \
            prompt.CallbackPrompt(
                                  title='Firmware Update',
                                  actions=[prompt.close_button]
                                 )

        if self.update_dl.index[self.piksi_hw_rev].has_key('fw'):
          fw_update_prompt.text = \
            "New Piksi firmware available.\n\n" + \
            "Please use the Firmware Update tab to update.\n\n" + \
            "Newest Firmware Version :\n\t%s\n\n" % \
                self.update_dl.index[self.piksi_hw_rev]['fw']['version']
        else:
          fw_update_prompt.text = \
            "New Piksi firmware available.\n\n" + \
            "Please use the Firmware Update tab to update.\n\n" + \
            "Newest STM Version :\n\t%s\n\n" % \
                self.update_dl.index[self.piksi_hw_rev]['stm_fw']['version'] + \
            "Newest SwiftNAP Version :\n\t%s\n\n" % \
                self.update_dl.index[self.piksi_hw_rev]['nap_fw']['version']

        fw_update_prompt.run()

      # Check if firmware successfully upgraded and notify user if so.
      if not self.fw_outdated and self.last_call_fw_version is not None and \
          self.last_call_fw_version != local_stm_version:
        success_prompt = \
            prompt.CallbackPrompt(
                                  title='Firmware Update Success',
                                  actions=[prompt.close_button]
                                 )
        success_prompt.text = \
            "Firmware successfully upgraded.\n\n" + \
            "Old Firmware :\n\t%s\n\n" % \
                self.last_call_fw_version + \
            "Current Firmware :\n\t%s\n\n" % \
                local_stm_version
        success_prompt.run()

  def _get_latest_version_info(self):
    """ Get latest firmware / console version from website. """
    try:
      self.update_dl = UpdateDownloader()
    except URLError:
      self._write("\nError: Failed to download latest file index from Swift Navigation's website. Please visit our website to check that you're running the latest Piksi firmware and Piksi console.\n")
      return

    # Make sure index contains all keys we are interested in.
    try:
      if self.update_dl.index[self.piksi_hw_rev].has_key('fw'):
        self.newest_stm_vers = self.update_dl.index[self.piksi_hw_rev]['fw']['version']
      else:
        self.newest_stm_vers = self.update_dl.index[self.piksi_hw_rev]['stm_fw']['version']
        self.newest_nap_vers = self.update_dl.index[self.piksi_hw_rev]['nap_fw']['version']
      self.newest_console_vers = self.update_dl.index[self.piksi_hw_rev]['console']['version']
    except KeyError:
      self._write("\nError: Index downloaded from Swift Navigation's website (%s) doesn't contain all keys. Please contact Swift Navigation.\n" % INDEX_URL)
      return

  def manage_stm_firmware_update(self):
    # Erase all of STM's flash (other than bootloader) if box is checked.
    if self.erase_stm:
      text = "Erasing STM"
      self._write(text)
      self.create_flash("STM")
      sectors_to_erase = set(range(self.pk_flash.n_sectors)).difference(set(self.pk_flash.restricted_sectors))
      progress_dialog = PulsableProgressDialog(len(sectors_to_erase), False)
      progress_dialog.title = text
      GUI.invoke_later(progress_dialog.open)
      erase_count = 0
      for s in sorted(sectors_to_erase):
        progress_dialog.progress(erase_count)
        self._write('Erasing %s sector %d' % (self.pk_flash.flash_type,s))
        self.pk_flash.erase_sector(s)
        erase_count += 1
      self.stop_flash()
      self._write("")
      try:
        progress_dialog.close()
      except AttributeError:
        pass
    # Flash STM.
    text = "Updating STM"
    self._write(text)
    self.create_flash("STM")
    stm_n_ops = self.pk_flash.ihx_n_ops(self.stm_fw.ihx, \
                                        erase = not self.erase_stm)
    progress_dialog = PulsableProgressDialog(stm_n_ops, True)
    progress_dialog.title = text
    GUI.invoke_later(progress_dialog.open)
    # Don't erase sectors if we've already done so above.
    self.pk_flash.write_ihx(self.stm_fw.ihx, self.stream, mod_print=0x40, \
                            elapsed_ops_cb = progress_dialog.progress, \
                            erase = not self.erase_stm)
    self.stop_flash()
    self._write("")
    try:
      progress_dialog.close()
    except AttributeError:
      pass

  def manage_nap_firmware_update(self, check_version=False):
    # Flash NAP if out of date.
    try:
      local_nap_version = parse_version(
          self.settings['system_info']['nap_version'].value)
      remote_nap_version = parse_version(self.newest_nap_vers)
      nap_out_of_date = local_nap_version != remote_nap_version
    except KeyError:
      nap_out_of_date = True
    if nap_out_of_date or check_version==False:
      text = "Updating NAP"
      self._write(text)
      self.create_flash("M25")
      nap_n_ops = self.pk_flash.ihx_n_ops(self.nap_fw.ihx)
      progress_dialog = PulsableProgressDialog(nap_n_ops, True)
      progress_dialog.title = text
      GUI.invoke_later(progress_dialog.open)
      self.pk_flash.write_ihx(self.nap_fw.ihx, self.stream, mod_print=0x40, \
                              elapsed_ops_cb = progress_dialog.progress)
      self.stop_flash()
      self._write("")
      try:
        progress_dialog.close()
      except AttributeError:
        pass
      return True
    else:
      text = "NAP is already to latest version, not updating!"
      self._write(text)
      self._write("")
      return False

  def manage_multi_firmware_update(self):
    # Set up progress dialog and transfer file to Piksi using SBP FileIO
    progress_dialog = PulsableProgressDialog(len(self.stm_fw.blob))
    progress_dialog.title = "Transferring image file"
    GUI.invoke_later(progress_dialog.open)
    self._write("Transferring image file...")
    try:
      FileIO(self.link).write("upgrade.image_set.bin", self.stm_fw.blob,
                              progress_cb=progress_dialog.progress)
    except Exception as e:
      self._write("Failed to transfer image file to Piksi: %s\n" % e)
      progress_dialog.close()
      return
    try:
      progress_dialog.close()
    except AttributeError:
      pass

    # Setup up pulsed progress dialog and commit to flash
    progress_dialog = PulsableProgressDialog(100, True)
    progress_dialog.title = "Committing to flash"
    GUI.invoke_later(progress_dialog.open)
    self._write("Committing file to flash...")
    def log_cb(msg, **kwargs): self._write(msg.text)
    self.link.add_callback(log_cb, SBP_MSG_LOG)
    code = shell_command(self.link, "upgrade_tool upgrade.image_set.bin", 600,
                         progress_cb=progress_dialog.progress)
    self.link.remove_callback(log_cb, SBP_MSG_LOG)
    progress_dialog.close()

    if code != 0:
      self._write('Failed to perform upgrade (code = %d)' % code)
      if code == -255:
        self._write('Shell command timed out.  Please try again.')
      return
    self._write('Resetting Piksi...')
    self.link(MsgReset(flags=0))

  # Executed in GUI thread, called from Handler.
  def manage_firmware_updates(self, device):
    """
    Update Piksi firmware. Erase entire STM flash (other than bootloader)
    if so directed. Flash NAP only if new firmware is available.
    """
    self.updating = True
    update_nap = False
    self._write('')
    if not self.is_v2:
      self.manage_multi_firmware_update()
      self.updating = False
      return
    elif device == "STM":
      self.manage_stm_firmware_update()
    elif device == "M25":
      update_nap = self.manage_nap_firmware_update()
    else:
      self.manage_stm_firmware_update()
      update_nap = self.manage_nap_firmware_update(check_version=True)

    # Must tell Piksi to jump to application after updating firmware.
    if device == "STM" or update_nap:
        self.link(MsgBootloaderJumpToApp(jump=0))
        self._write("Firmware update finished.")
        self._write("")

    self.updating = False

  def create_flash(self, flash_type):
    """
    Create flash.Flash instance and set Piksi into bootloader mode, prompting
    user to reset if necessary.

    Parameter
    ---------
    flash_type : string
      Either "STM" or "M25".
    """
    # Reset device if the application is running to put into bootloader mode.
    self.link(MsgReset(flags=0))

    self.pk_boot = bootload.Bootloader(self.link)

    self._write("Waiting for bootloader handshake message from Piksi ...")
    reset_prompt = None
    handshake_received = self.pk_boot.handshake(1)

    # Prompt user to reset Piksi if we don't receive the handshake message
    # within a reasonable amount of tiime (firmware might be corrupted).
    while not handshake_received:
      reset_prompt = \
        prompt.CallbackPrompt(
                              title="Please Reset Piksi",
                              actions=[prompt.close_button],
                             )

      reset_prompt.text = \
            "You must press the reset button on your Piksi in order\n" + \
            "to update your firmware.\n\n" + \
            "Please press it now.\n\n"

      reset_prompt.run(block=False)

      while not reset_prompt.closed and not handshake_received:
        handshake_received = self.pk_boot.handshake(1)

      reset_prompt.kill()
      reset_prompt.wait()

    self._write("received bootloader handshake message.")
    self._write("Piksi Onboard Bootloader Version: " + self.pk_boot.version)

    self.pk_flash = flash.Flash(self.link, flash_type, self.pk_boot.sbp_version)

  def stop_flash(self):
    """
    Stop Flash and Bootloader instances (removes callback from SerialLink).
    """
    self.pk_flash.stop()
    self.pk_boot.stop()
