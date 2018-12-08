# http://pseudofish.com/elementary-bluetooth-using-pyobjc.html
# https://github.com/0-1-0/lightblue-0.4/blob/master/build/lib/lightblue/_lightblue.py

# this is ugly code that allows you to load any class from Cocoa APIs
# here we load IOBluetooth - presumably this loads the API into globals()
import objc as _objc
import Foundation
import time

from Foundation import NSObject, NSDate, NSPoint, NSDefaultRunLoopMode, NSTimer
from AppKit import NSApplication, NSEvent, NSApplicationDefined, NSAnyEventMask

_objc.loadBundle('IOBluetooth', globals(), bundle_path=u'/System/Library/Frameworks/IOBluetooth.framework')

LIGHTBLUE_NOTIFY_ID = 5444 # any old number
WAIT_MAX_TIMEOUT = 3

def interruptwait():
    """
    If waituntil() has been called, this will interrupt the waiting process so
    it can check whether it should stop waiting.
    """
    evt = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(NSApplicationDefined, NSPoint(), NSApplicationDefined, 0, 1, None, LIGHTBLUE_NOTIFY_ID, 0, 0)
    NSApplication.sharedApplication().postEvent_atStart_(evt, True)

def formatdevaddr(addr):
    """
    Returns address of a device in usual form e.g. "00:00:00:00:00:00"

    - addr: address as returned by device.getAddressString() on an
      IOBluetoothDevice
    """
    # make uppercase cos PyS60 & Linux seem to always return uppercase
    # addresses
    # can safely encode to ascii cos BT addresses are only in hex (pyobjc
    # returns all strings in unicode)
    return addr.replace("-", ":").encode('ascii').upper()

def waituntil(conditionfunc, timeout=None):
    """
    Waits until conditionfunc() returns true, or <timeout> seconds have passed.
    (If timeout=None, this waits indefinitely until conditionfunc() returns
    true.) Returns false if the process timed out, otherwise returns true.

    Note!! You must call interruptwait() when you know that conditionfunc()
    should be checked (e.g. if you are waiting for data and you know some data
    has arrived) so that this can check conditionfunc(); otherwise it will just
    continue to wait. (This allows the function to wait for an event that is
    sent by interruptwait() instead of polling conditionfunc().)

    This allows the caller to wait while the main event loop processes its
    events. This must be done for certain situations, e.g. to receive socket
    data or to accept client connections on a server socket, since IOBluetooth
    requires the presence of an event loop to run these operations.

    This function doesn't need to be called if there is something else that is
    already processing the main event loop, e.g. if called from within a Cocoa
    application.
    """
    app = NSApplication.sharedApplication()
    starttime = time.time()
    if timeout is None:
        timeout = NSDate.distantFuture().timeIntervalSinceNow()
    if not isinstance(timeout, (int, float)):
        raise TypeError("timeout must be int or float, was %s" % \
                        type(timeout))
    endtime = starttime + timeout
    while True:
        currtime = time.time()
        if currtime >= endtime:
            return False
        # use WAIT_MAX_TIMEOUT, don't wait forever in case of KeyboardInterrupt
        e = app.nextEventMatchingMask_untilDate_inMode_dequeue_(NSAnyEventMask, NSDate.dateWithTimeIntervalSinceNow_(
            min(endtime - currtime, WAIT_MAX_TIMEOUT)), NSDefaultRunLoopMode, True)
        if e is not None:
            if (e.type() == NSApplicationDefined and e.subtype() == LIGHTBLUE_NOTIFY_ID):
                if conditionfunc():
                    return True
            else:
                app.postEvent_atStart_(e, True)

# values of constants used in _IOBluetooth.framework
kIOReturnSuccess = 0       # defined in <IOKit/IOReturn.h>
kIOBluetoothUserNotificationChannelDirectionIncoming = 1
        # defined in <IOBluetooth/IOBluetoothUserLib.h>
kBluetoothHCIErrorPageTimeout = 0x04   # <IOBluetooth/Bluetooth.h>

# defined in <IOBluetooth/IOBluetoothUserLib.h>
kIOBluetoothServiceBrowserControllerOptionsNone = 0o0


def _getdevicetuple(iobtdevice):
    """
    Returns an (addr, name, COD) device tuple from a IOBluetoothDevice object.
    """
    addr = formatdevaddr(iobtdevice.getAddressString())
    name = iobtdevice.getName()
    cod = iobtdevice.getClassOfDevice()
    rssi = iobtdevice.rawRSSI()
    return addr, name, cod, rssi


class _AsyncDeviceInquiry(Foundation.NSObject):

    # NSObject init, not python __init__
    def init(self):
        try:
            attr = IOBluetoothDeviceInquiry
        except AttributeError:
            raise ImportError("Cannot find IOBluetoothDeviceInquiry class " +
                              "to perform device discovery. This class was introduced in " +
                              "Mac OS X 10.4, are you running an earlier version?")

        self = super(_AsyncDeviceInquiry, self).init()
        self._inquiry = IOBluetoothDeviceInquiry.inquiryWithDelegate_(self)

        # callbacks
        self.cb_started = None
        self.cb_completed = None
        self.cb_founddevice = None

        return self

    # length property
    def _setlength_(self, length):
        self._inquiry.setInquiryLength_(length)

    length = property(
        lambda self: self._inquiry.inquiryLength(),
        _setlength_)

    # updatenames property
    def _setupdatenames_(self, update):
        self._inquiry.setUpdateNewDeviceNames_(update)

    updatenames = property(
        lambda self: self._inquiry.updateNewDeviceNames(),
        _setupdatenames_)

    # returns error code
    def start(self):
        return self._inquiry.start()

    # returns error code
    def stop(self):
        return self._inquiry.stop()

    # returns list of IOBluetoothDevice objects
    def getfounddevices(self):
        return self._inquiry.foundDevices()

    def __del__(self):
        super(_AsyncDeviceInquiry, self).dealloc()

    #
    # delegate methods follow (these are called by the internal
    # IOBluetoothDeviceInquiry object when inquiry events occur)
    #

    # - (void)deviceInquiryDeviceFound:(IOBluetoothDeviceInquiry*)sender
    #                           device:(IOBluetoothDevice*)device;
    def deviceInquiryDeviceFound_device_(self, inquiry, device):
        if self.cb_founddevice:
            self.cb_founddevice(device)

    deviceInquiryDeviceFound_device_ = _objc.selector(
        deviceInquiryDeviceFound_device_, signature=b'v@:@@')

    # - (void)deviceInquiryComplete:error:aborted;
    def deviceInquiryComplete_error_aborted_(self, inquiry, err, aborted):
        if self.cb_completed:
            self.cb_completed(err, aborted)

    deviceInquiryComplete_error_aborted_ = _objc.selector(
        deviceInquiryComplete_error_aborted_, signature=b'v@:@iB')

    # - (void)deviceInquiryStarted:(IOBluetoothDeviceInquiry*)sender;
    def deviceInquiryStarted_(self, inquiry):
        if self.cb_started:
            self.cb_started()


class _SyncDeviceInquiry(object):

    def __init__(self):
        super(_SyncDeviceInquiry, self).__init__()

        self._inquiry = _AsyncDeviceInquiry.alloc().init()
        self._inquiry.cb_completed = self._inquirycomplete

        self._inquiring = False

    def run(self, getnames, duration):
        if self._inquiring:
            print("Another inquiry in process")

        # set inquiry attributes
        self._inquiry.updatenames = getnames
        self._inquiry.length = duration

        # start the inquiry
        err = self._inquiry.start()
        if err != kIOReturnSuccess:
            print("Error starting")

            # if error occurs during inquiry, set _inquiryerr to the error code
        self._inquiryerr = kIOReturnSuccess

        # wait until the inquiry is complete
        self._inquiring = True
        waituntil(lambda: not self._inquiring, timeout=10)

        # if error occured during inquiry, raise exception
        if self._inquiryerr != kIOReturnSuccess:
            print("Error during")

    def getfounddevices(self):
        # return as list of device-info tuples
        return [_getdevicetuple(device) for device in self._inquiry.getfounddevices()]

    def _inquirycomplete(self, err, aborted):
        if err != 188:  # no devices found
            self._inquiryerr = err
        self._inquiring = False
        interruptwait()

    def __del__(self):
        pass
        #self._inquiry.__del__()


def finddevices(getnames=True, length=10):
    inquiry = _SyncDeviceInquiry()
    inquiry.run(getnames, length)
    devices = inquiry.getfounddevices()
    return devices


def print_devices(devices):
    for device in devices:
        labels = ["Address", "Name", "Class of Device", "RSSI"]
        output = []
        for label, value in zip(labels, device):
            output.append(label + ": " + str(value))
        print(', '.join(output))


print_devices(finddevices(True))
