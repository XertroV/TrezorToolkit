#!/usr/bin/python

import sys

from binascii import unhexlify
from threading import Thread
import time

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import QThread, SIGNAL

from pycoin.key.bip32 import Wallet

from trezorlib.client import TrezorClient
from trezorlib.transport_hid import HidTransport
import trezorlib

import mnemonic

from gui import Ui_MainWindow

devices = HidTransport.enumerate()
transport = HidTransport(devices[0])

client = TrezorClient(transport)

#netcode = "BTC"
#xpub = Wallet(False, netcode, node.chain_code, node.depth, unhexlify("%08x" % node.fingerprint), node.child_num)

#
# Wrap trezor functions in a with statement (using this) to show on the UI that
# interaction is required on the trezor
#

class TrezorWarning:

    def __init__(self):
        self.waiting = False

    def start_warning(self, message):
        # borrowed mostly from electrum trezor plugin
        self.d = QtGui.QDialog()
        self.d.setModal(1)
        self.d.setWindowTitle('Please Check Trezor Device')
        self.d.setWindowFlags(self.d.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        l = QtGui.QLabel(message)
        vbox = QtGui.QVBoxLayout(self.d)
        vbox.addWidget(l)
        self.d.show()
        if not self.waiting:
            self.waiting = True
            self.d.connect(trezor_operations, QtCore.SIGNAL('trezor_done'), self.kill_warning)

    def kill_warning(self):
        self.waiting = False
        self.d.hide()

class TrezorOperations(QThread):
    def __init__(self):
        QThread.__init__(self)
        self.waiting = False
        self.trezor_operations = []

    def run(self):
        while len(self.trezor_operations) > 0:
            try:
                f, args, kwargs = self.trezor_operations.pop(0)
                f(*args, **kwargs)
            except Exception as e:
                print e
                self.emit(SIGNAL('trezor_exception'), e)
        self.emit(SIGNAL('trezor_done'))

    def add_operation(self, f, *args, **kwargs):
        self.trezor_operations.append((f, args, kwargs))

    def add_operation_then_start(self, f, *args, **kwargs):
        self.add_operation(f, *args, **kwargs)
        self.start()

trezor_operations = TrezorOperations()
trezor_warning = TrezorWarning()

def trezor_warn_and_start(message, f, *args, **kwargs):
    trezor_warning.start_warning(message)
    trezor_operations.add_operation_then_start(f, *args, **kwargs)

#
# Ui Classes
#

class GeneralAlert():

    def __init__(self):
        self.d = QtGui.QMessageBox()
        self.d.connect(trezor_operations, SIGNAL('trezor_exception'), self.generate_alert)

    def generate_alert(self, msg):
        self.d.setText(str(msg))
        self.d.show()

#
# UI Functions
#

def click_set_label():
    trezor_warn_and_start("Look to Trezor for set-label confirmation...", client.apply_settings, label=str(ui.line_edit_tlabel.text()))

def update_label():
    try:
        curr_label = client.features.label
    except trezorlib.client.CallException as e:
        if e.message[0] == 11:
            print 'device not initialized'
            curr_label = "Not Initialized"
        else:
            raise e
    ui.line_edit_tlabel.setText(curr_label)

def wipe_device():
    trezor_warn_and_start("CONFIRM WIPE ON TREZOR! (OR CANCEL NOW)", client.wipe_device)

def load_new_key_128(): load_new_key_from_scratch(128)
def load_new_key_192(): load_new_key_from_scratch(192)
def load_new_key_256(): load_new_key_from_scratch(256)

def load_new_key_from_scratch(entropy_in_bits):
    m = mnemonic.Mnemonic('english')
    priv = m.generate(entropy_in_bits)
    _restore_from_mnemonic(priv, "Fresh Trezor")
    ui.text_mnemonic.setPlainText(priv)

def restore_from_mnemonic():
    mnemonic_string = str(ui.text_mnemonic.toPlainText())
    label=str(ui.line_edit_tlabel.text())
    _restore_from_mnemonic(mnemonic_string, label)

def _restore_from_mnemonic(mnemonic_string, label):
    trezor_warn_and_start("CONFIRM RESTORE ON TREZOR!", client.load_device_by_mnemonic, mnemonic=mnemonic_string, pin="",
                          passphrase_protection=False, label=label, language='en')

#
# UI Execution
#

app = QtGui.QApplication(sys.argv)

class MyWindow(QtGui.QMainWindow):
    pass


main_window = MyWindow()
ui = Ui_MainWindow()
ui.setupUi(main_window)
main_window.show()

general_alert = GeneralAlert()


def setup():
    # update label
    ui.label_tid.setText(client.features.device_id)
    ui.button_t_set_label.clicked.connect(click_set_label)
    update_label()

    # wipe
    ui.button_wipe.clicked.connect(wipe_device)

    # reload from mnemonic or xprv
    ui.button_restore_mnemonic.clicked.connect(restore_from_mnemonic)
    ui.button_new_keys_128.clicked.connect(load_new_key_128)
    ui.button_new_keys_192.clicked.connect(load_new_key_192)
    ui.button_new_keys_256.clicked.connect(load_new_key_256)

setup()

sys.exit(app.exec_())