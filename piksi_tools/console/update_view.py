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

from __future__ import absolute_import, print_function

import os
import errno
import re

from threading import Thread
from time import sleep
from urllib2 import URLError

from pkg_resources import parse_version as pkparse_version
from pyface.api import GUI, OK, FileDialog, DirectoryDialog, ProgressDialog
from sbp.logging import SBP_MSG_LOG
from sbp.piksi import MsgReset
from traits.api import Bool, Button, HasTraits, Instance, String
from traitsui.api import HGroup, InstanceEditor, Item, UItem, VGroup, View, Spring

import piksi_tools.console.callback_prompt as prompt
from piksi_tools import __version__ as CONSOLE_VERSION
from piksi_tools.bootload_v3 import shell_command
from piksi_tools.fileio import FileIO

from .output_stream import OutputStream
from .update_downloader import INDEX_URL, UpdateDownloader

HT = 8
COLUMN_WIDTH = 100

HW_REV_LOOKUP = {
    'Piksi Multi': 'piksi_multi',
    'piksi_2.3.1': 'piksi_v2.3.1',
}

UPGRADE_WHITELIST = [
    "ok", "writing.*", "erasing.*", "\s*[0-9]* % complete",
    "Error.*", "error.*", ".*Image.*", ".*upgrade.*",
    "Warning:*", ".*install.*", "upgrade completed successfully"]

V2_LINK = "https://www.swiftnav.com/resource-files/Piksi%20Multi/v2.0.0/Firmware/PiksiMulti-v2.0.0.bin"


def parse_version(version):
    if version[0] == 'v':
        version = version[1:]
    return pkparse_version(version.replace(
        "dirty",
        "", ))


class FirmwareFileDialog(HasTraits):
    file_wildcard = String("Binary image set (*.bin)|*.bin|All files|*")
    status = String('Please choose a file')
    choose_fw = Button(label='...', padding=-1)
    view = View(
        HGroup(
            UItem('status', resizable=True), UItem('choose_fw', width=-0.1)), )

    def __init__(self, default_dir):
        """
        Pop-up file dialog to choose an IntelHex file, with status and button to
        display in traitsui window.
        """
        self.ihx = None
        self.blob = None
        self.default_dir = default_dir

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

    def load_bin(self, filepath):
        try:
            self.blob = open(filepath, 'rb').read()
            self.status = os.path.split(filepath)[1]
        except:  # noqa
            self.clear('Error: Failed to read binary file')

    def _choose_fw_fired(self):
        """ Activate file dialog window to choose IntelHex firmware file. """
        dialog = FileDialog(
            label='Choose Firmware File',
            action='open',
            default_directory=self.default_dir,
            wildcard=self.file_wildcard)
        dialog.open()
        if dialog.return_code == OK:
            filepath = os.path.join(dialog.directory, dialog.filename)
            self.load_bin(filepath)
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

    def open_in_gui_thread(self, timeout_secs=5):
        """
        Open dialog in gui thread and wait to return until open up to timeout_sec seconds
        The superclass open method sets the _start_time variable which is used as a signal
        for whether open has occured.

        Parameters
        ----------
        timeouts_secs : int
            Number of seconds to wait for widget to initialize.

        Returns
        ----------
            True if widget was opened (i.e _start_time var exists)
            False if otherwise
        """
        GUI.invoke_later(self.open)
        counter = 0
        while(getattr(self, '_start_time', -1) == -1 and counter < timeout_secs * 2):
            sleep(0.5)
            counter += 1
        return getattr(self, '_start_time', -1) != -1

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
                GUI.invoke_later(self.update,
                                 int(100 * float(count) / self.passed_max))
        else:
            self.max = 100
            GUI.invoke_later(self.update,
                             int(100 * float(count) / self.passed_max))


class UpdateView(HasTraits):
    piksi_hw_rev = String('piksi_multi')
    is_v2 = Bool(False)

    piksi_stm_vers = String(
        'Waiting for Piksi to send settings...', width=COLUMN_WIDTH)
    newest_stm_vers = String('Downloading Latest Firmware info...')
    piksi_nap_vers = String('Waiting for Piksi to send settings...')
    newest_nap_vers = String('Downloading Latest Firmware info...')
    local_console_vers = String('v' + CONSOLE_VERSION)
    newest_console_vers = String('Downloading Latest Console info...')
    download_directory_label = String('Firmware Download Directory:')

    update_stm_firmware = Button(label='Update Firmware')

    updating = Bool(False)
    update_stm_en = Bool(False)

    download_firmware = Button(label='Download Latest Firmware')
    download_directory = String()
    choose_dir = Button(label='...', padding=-1)
    download_stm = Button(label='Download', height=HT)
    downloading = Bool(False)
    download_fw_en = Bool(False)

    stm_fw = Instance(FirmwareFileDialog)

    stream = Instance(OutputStream)

    view = View(
        VGroup(
            Item(
                'piksi_hw_rev',
                label='Hardware Revision',
                editor_args={'enabled': False},
                resizable=True),
            HGroup(
                VGroup(
                    Item(
                        'piksi_stm_vers',
                        label='Current',
                        resizable=True,
                        editor_args={'enabled': False}),
                    Item(
                        'newest_stm_vers',
                        label='Latest',
                        resizable=True,
                        editor_args={
                            'enabled': False,
                            'readonly_allow_selection': True
                        }),
                    Item(
                        'stm_fw',
                        style='custom',
                        show_label=True,
                        label="Local File"),
                    Item(
                        'update_stm_firmware',
                        show_label=False,
                        enabled_when='update_stm_en'),

                    show_border=True,
                    label="Firmware Version"),
                VGroup(
                    Item(
                        'local_console_vers',
                        label='Current',
                        resizable=True,
                        editor_args={'enabled': False}),
                    Item(
                        'newest_console_vers',
                        label='Latest',
                        editor_args={'enabled': False}),
                    label="Swift Console Version",
                    show_border=True), ),
            HGroup(
                VGroup(
                    HGroup(
                        Item('download_directory', label="Directory", resizable=True),
                        UItem('choose_dir', width=-0.1),
                    ),
                    HGroup(
                        Spring(width=50, springy=False),
                        Item('download_firmware', enabled_when='download_fw_en',
                             show_label=False, resizable=True, springy=True)
                    ),
                    label="Firmware Download",
                    show_border=True),
                VGroup(
                    Item(
                        'stream',
                        style='custom',
                        editor=InstanceEditor(),
                        show_label=False, ),
                    show_border=True,
                    label="Firmware Upgrade Status"),
            ),
            show_border=True),
    )

    def __init__(self,
                 link,
                 download_dir=None,
                 prompt=True,
                 connection_info={'mode': 'unknown'}):
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
        self.connection_info = connection_info
        self.settings = {}
        self.prompt = prompt
        self.python_console_cmds = {'update': self}
        self.download_directory = download_dir
        try:
            self.update_dl = UpdateDownloader(root_dir=self.download_directory)
        except RuntimeError:
            self.update_dl = None
        self.stm_fw = FirmwareFileDialog(self.download_directory)
        self.stm_fw.on_trait_change(self._manage_enables, 'status')
        self.stream = OutputStream()
        self.stream.max_len = 1000
        self.last_call_fw_version = None
        self.link.add_callback(self.log_cb, SBP_MSG_LOG)

    def _choose_dir_fired(self):
        dialog = DirectoryDialog(
            label='Choose Download location',
            action='open',
            default_directory=self.download_directory)
        dialog.open()
        if dialog.return_code == OK:
            self.download_directory = dialog.path
        else:
            self._write('Error while selecting firmware download location')

    def _manage_enables(self):
        """ Manages whether traits widgets are enabled in the UI or not. """
        if self.updating or self.downloading:
            self.update_stm_en = False
            self.download_fw_en = False
        else:
            if getattr(self.stm_fw, 'blob', None) is not None:
                self.update_stm_en = True
            else:
                self.update_stm_en = False
            if self.download_directory != '':
                self.download_fw_en = True

    def _download_directory_changed(self):
        if getattr(self, 'update_dl', None):
            self.update_dl.set_root_path(self.download_directory)
        self._manage_enables()

    def _updating_changed(self):
        """ Handles self.updating trait being changed. """
        self._manage_enables()

    def _downloading_changed(self):
        """ Handles self.downloading trait being changed. """
        self._manage_enables()

    def _clear_stream(self):
        self.stream.reset()

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

        if self.connection_info['mode'] != 'TCP/IP':
            self._write(
                "\n"
                "-----------------------------------------------\n"
                "USB Flashdrive Upgrade Procedure\n"
                "-----------------------------------------------\n"
                "\n"
                "1.\tInsert the USB flash drive provided with your Piksi Multi into your computer.\n"
                "  \tSelect the flash drive root directory as the firmware download destination using the directory chooser above.\n"
                "  \tPress the \"Download Latest Firmware\" button. This will download the latest Piksi Multi firmware file onto\n"
                "  \tthe USB flashdrive.\n"
                "2.\tEject the drive from your computer and plug it into the USB Host port of the Piksi Multi evaluation board.\n"
                "3.\tReset your Piksi Multi and it will upgrade to the version on the USB flash drive.\n"
                "  \tThis should take less than 5 minutes.\n"
                "4.\tWhen the upgrade completes you will be prompted to remove the USB flash drive and reset your Piksi Multi.\n"
                "5.\tVerify that the firmware version has upgraded via inspection of the Current Firmware Version box\n"
                "  \ton the Update Tab of the Swift Console.\n")

            confirm_prompt = prompt.CallbackPrompt(
                title="Update device over serial connection?",
                actions=[prompt.close_button, prompt.continue_via_serial_button],
                callback=self._update_stm_firmware_fn)
            confirm_prompt.text = "\n" \
                                  + "    Upgrading your device via UART / RS232 may take up to 30 minutes.     \n" \
                                  + "                                                                          \n" \
                                  + "    If the device you are upgrading has an accessible USB host port, it   \n" \
                                    "    is recommended to instead  follow the \'USB Flashdrive Upgrade        \n" \
                                    "    Procedure\' that now appears in the Firmware upgrade status box.      \n" \
                                  + "\n" \
                                  + "    Are you sure you want to continue upgrading over serial?"
            confirm_prompt.run(block=False)
        else:
            self._update_stm_firmware_fn()

    def _replace_with_version_2(self):
        self.downloading = True
        self._write('Downloading Multi firmware v2.0.0')
        filepath = self.update_dl._download_file_from_url(V2_LINK)
        self._write('Saved file to %s' % filepath)
        self.stm_fw.load_bin(filepath)
        self.downloading = False

    def _update_stm_firmware_fn(self):
        try:
            if self._firmware_update_thread.is_alive():
                return
        except AttributeError:
            pass

        current_fw_version = parse_version(self.piksi_stm_vers)
        re_result = re.search('[a-zA-Z0-9]*-(v[0-9]*\.[0-9]*\.[0-9])', self.stm_fw.status)
        intended_version = parse_version(re_result.group(1))
        # If the current firmware is not yet beyond 2.0.0, and we are loading beyond 2.0.0
        # warn the user that this upgrade is not possible
        if (current_fw_version < pkparse_version("v2.0.0") and intended_version > pkparse_version("v2.0.0")):
            confirm_prompt = prompt.CallbackPrompt(
                title="Update to v2.0.0",
                actions=[prompt.close_button, prompt.ok_button],
                callback=self._replace_with_version_2)
            confirm_prompt.text = "\n" \
                                  + "    Upgrading to firmware v2.1.0 or later requires that the device be     \n" \
                                  + "    running firmware v2.0.0 or later. Please upgrade to firmware          \n" \
                                  + "    version 2.0.0.                                                        \n" \
                                  + "                                                                          \n" \
                                  + "    Would you like to download firmware version v2.0.0 now?               \n" \
                                  + "                                                                          \n"
            confirm_prompt.run(block=False)
            return
        self._firmware_update_thread = Thread(
            target=self.manage_firmware_updates, args=("STM",))
        self._firmware_update_thread.start()

    def _download_firmware(self):
        """ Download latest firmware from swiftnav.com. """
        self._write('')

        # Check that we received the index file from the website.
        if self.update_dl is None or self.update_dl.index is None:
            self._write("Error: Can't download firmware files")
            return

        self.downloading = True
        status = 'Downloading Latest Firmware...'
        self.stm_fw.clear(status)
        self._write(status)

        # Get firmware files from Swift Nav's website, save to disk, and load.
        if 'fw' in self.update_dl.index[self.piksi_hw_rev]:
            try:
                self._write('Downloading Latest Multi firmware')
                filepath = self.update_dl.download_multi_firmware(
                    self.piksi_hw_rev)
                self._write('Saved file to %s' % filepath)
                self.stm_fw.load_bin(filepath)
            except AttributeError:
                self._write(
                    "Error downloading firmware: index file not downloaded yet"
                )
            except RuntimeError as e:
                self._write(
                    "RunTimeError: unable to download firmware to path {0}: {1}".format(self.download_directory, e))
            except IOError as e:
                if e.errno == errno.EACCES or e.errno == errno.EPERM:
                    self._write("IOError: unable to write to path %s. "
                                "Verify that the path is writable." %
                                self.download_directory)
                else:
                    raise (e)
            except KeyError:
                self._write(
                    "Error downloading firmware: URL not present in index")
            except URLError:
                self.nap_fw.clear("Error downloading firmware")
                self._write(
                    "Error: Failed to download latest NAP firmware from Swift Navigation's website"
                )
            self.downloading = False
            return

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
            self.piksi_hw_rev = HW_REV_LOOKUP[self.settings['system_info']['hw_revision'].value]
            self.piksi_stm_vers = self.settings['system_info']['firmware_version'].value
        except KeyError:
            self._write(
                "\nError: Settings received from Piksi don't contain firmware version keys. Please contact Swift Navigation.\n"
            )
            return

        self.is_v2 = self.piksi_hw_rev.startswith('piksi_v2')

        self._get_latest_version_info()

        # Check that we received the index file from the website.
        if self.update_dl is None:
            self._write(
                "Error: No website index to use to compare versions with local firmware"
            )
            return
        # Get local stm version
        local_stm_version = None
        local_serial_number = None
        try:
            local_stm_version = self.settings['system_info'][
                'firmware_version'].value
            local_serial_number = self.settings['system_info'][
                'serial_number'].value
        except:  # noqa
            pass
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
            remote_stm_version = self.newest_stm_vers

            self.fw_outdated = remote_stm_version > local_stm_version
            if local_stm_version.startswith('DEV'):
                self.fw_outdated = False

            if self.fw_outdated:
                fw_update_prompt = \
                    prompt.CallbackPrompt(
                        title='Firmware Update',
                        actions=[prompt.close_button]
                    )

                if 'fw' in self.update_dl.index[self.piksi_hw_rev]:
                    fw_update_prompt.text = \
                        "New Piksi firmware available.\n\n" + \
                        "Please use the Update tab to update.\n\n" + \
                        "Newest Firmware Version :\n\t%s\n\n" % \
                        self.update_dl.index[self.piksi_hw_rev]['fw']['version']
                else:
                    fw_update_prompt.text = \
                        "New Piksi firmware available.\n\n" + \
                        "Please use the Update tab to update.\n\n" + \
                        "Newest STM Version :\n\t%s\n\n" % \
                        self.update_dl.index[self.piksi_hw_rev]['stm_fw']['version'] + \
                        "Newest SwiftNAP Version :\n\t%s\n\n" % \
                        self.update_dl.index[self.piksi_hw_rev]['nap_fw']['version']

                fw_update_prompt.run()

        # Check if firmware successfully upgraded and notify user if so.
        if ((self.last_call_fw_version is not None and self.last_call_fw_version != local_stm_version) and
                (self.last_call_sn is None or local_serial_number is None or self.last_call_sn == local_serial_number)):
            fw_success_str = "Firmware successfully upgraded from %s to %s." % \
                             (self.last_call_fw_version, local_stm_version)
            print(fw_success_str)
            self._write(fw_success_str)

        # Record firmware version reported each time this callback is called.
        self.last_call_fw_version = local_stm_version
        self.last_call_sn = local_serial_number

    def _get_latest_version_info(self):
        """ Get latest firmware / console version from website. """
        try:
            self.update_dl = UpdateDownloader(root_dir=self.download_directory)
        except RuntimeError:
            self._write(
                "\nError: Failed to download latest file index from Swift Navigation's website. Please visit our website to check that you're running the latest Piksi firmware and Piksi console.\n"
            )
            self.update_dl = None
            return

        # Make sure index contains all keys we are interested in.
        try:
            if 'fw' in self.update_dl.index[self.piksi_hw_rev]:
                self.newest_stm_vers = self.update_dl.index[self.piksi_hw_rev][
                    'fw']['version']
            else:
                self.newest_stm_vers = self.update_dl.index[self.piksi_hw_rev][
                    'stm_fw']['version']
                self.newest_nap_vers = self.update_dl.index[self.piksi_hw_rev][
                    'nap_fw']['version']
            self.newest_console_vers = self.update_dl.index[self.piksi_hw_rev][
                'console']['version']
        except KeyError:
            self._write(
                "\nError: Index downloaded from Swift Navigation's website (%s) doesn't contain all keys. Please contact Swift Navigation.\n"
                % INDEX_URL)
            return

    def file_transfer_progress_cb(self, arg):
        new_pcent = float(arg) / float(self.blob_size) * 100
        if new_pcent - self.pcent_complete > 0.1:
            self.pcent_complete = new_pcent
            self.stream.scrollback_write("{:2.1f} % of {:2.1f} MB transferred.".format(self.pcent_complete, self.blob_size * 1e-6))

    def log_cb(self, msg, **kwargs):
        for regex in UPGRADE_WHITELIST:
            if re.match(regex, msg.text):
                self.stream.scrollback_write(msg.text.split("\n")[-1])

    def manage_multi_firmware_update(self):
        self.blob_size = float(len(self.stm_fw.blob))
        self.pcent_complete = 0
        # Set up progress dialog and transfer file to Piksi using SBP FileIO
        self._clear_stream()
        self._write("Transferring image to device...\n\n00.0 of {:2.1f} MB trasnferred".format(self.blob_size * 1e-6))
        try:
            FileIO(self.link).write(
                "upgrade.image_set.bin",
                self.stm_fw.blob,
                progress_cb=self.file_transfer_progress_cb)
        except Exception as e:
            self._write("Failed to transfer image file to Piksi: %s\n" % e)
            self._write("Upgrade Aborted.")
            import traceback
            print(traceback.format_exc())
            return -1

        self.stream.scrollback_write("Image transfer complete: {:2.1f} MB transferred.\n".format(self.blob_size * 1e-6))
        # Setup up pulsed progress dialog and commit to flash
        self._write("Committing file to Flash...\n")
        self.link.add_callback(self.log_cb, SBP_MSG_LOG)
        code = shell_command(
            self.link,
            "upgrade_tool upgrade.image_set.bin",
            200)
        self.link.remove_callback(self.log_cb, SBP_MSG_LOG)

        if code != 0:
            self._write('Failed to perform upgrade (code = %d)' % code)
            if code == -255:
                self._write('Shell command timed out.  Please try again.')
            return
        self._write("Upgrade Complete.")
        self._write('Resetting Piksi...')
        self.link(MsgReset(flags=0))

    # Executed in GUI thread, called from Handler.
    def manage_firmware_updates(self, device):
        """
        Update Piksi firmware. Erase entire STM flash (other than bootloader)
        if so directed. Flash NAP only if new firmware is available.
        """
        self.updating = True
        self._write('')
        if not self.is_v2:
            self.manage_multi_firmware_update()
        else:
            self._write('Unable to upgrade piksi v2; please use the last supported v2 console version.')
            self._write("")
        self.updating = False
