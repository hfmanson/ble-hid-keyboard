import array
import ctypes
import logging
import os

import ioctl
import pyudev
from gi.repository import GLib


class Hidraw(object):
    """
    Constants from linux/hidraw.h
    """
    HIDIOCGRDESCSIZE = 0x01
    HIDIOCGRDESC = 0x02
    HIDIOCGRAWINFO = 0x03
    HIDIOCGRAWNAME = 0x04
    HIDIOCGRAWPHYS = 0x05
    HIDIOCSFEATURE = 0x06
    HIDIOCGFEATURE = 0x07
    HIDIOCGRAWUNIQ = 0x08

    def __init__(self, path, read_length=1024):
        self._path = path
        self._fd = os.open(path, os.O_RDWR)
        self.read_length = read_length

    @property
    def path(self):
        return self._path

    @property
    def fd(self):
        return self._fd

    @property
    def report_descriptor_size(self):
        result = ctypes.c_uint.from_buffer(
            ioctl.IOCTL.IOR('H', self.HIDIOCGRDESCSIZE, ctypes.sizeof(ctypes.c_uint)).perform(self._fd)
        ).value
        return result

    @property
    def report_descriptor(self):
        buf = array.array(
            'B', self.report_descriptor_size.to_bytes(4, 'little') +
            HidrawReportDescriptor.HID_MAX_DESCRIPTOR_SIZE * b'\x00'
        )

        ioctl.IOCTL.IOR('H', self.HIDIOCGRDESC, ctypes.sizeof(HidrawReportDescriptor)).perform(self._fd, buf)

        ret = HidrawReportDescriptor.from_buffer(buf)
        return list(ret.value)[:ret.size]

    @property
    def info(self):
        dev_info = HidrawDevinfo.from_buffer(ioctl.IOCTL.IOR('H', self.HIDIOCGRAWINFO, ctypes.sizeof(HidrawDevinfo))
                                             .perform(self._fd))

        return dev_info.bustype, dev_info.vendor, dev_info.product

    @property
    def name(self):
        return (ioctl.IOCTL.IOR('H', self.HIDIOCGRAWNAME, self.read_length)
                .perform(self._fd)
                .decode('utf-8')
                .strip('\x00'))

    @property
    def phys(self):
        return (ioctl.IOCTL.IOR('H', self.HIDIOCGRAWPHYS, self.read_length)
                .perform(self._fd)
                .decode('utf-8')
                .strip('\x00'))

    @property
    def uniq(self):
        return (ioctl.IOCTL.IOR('H', self.HIDIOCGRAWUNIQ, self.read_length)
                .perform(self._fd)
                .decode('utf-8')
                .strip('\x00'))


class HidrawReportDescriptor(ctypes.Structure):
    HID_MAX_DESCRIPTOR_SIZE = 4096
    _fields_ = [
        ('size', ctypes.c_uint),
        ('value', ctypes.c_ubyte * HID_MAX_DESCRIPTOR_SIZE),
    ]


class HidrawDevinfo(ctypes.Structure):
    _fields_ = [
        ('bustype', ctypes.c_uint),
        ('vendor', ctypes.c_ushort),
        ('product', ctypes.c_ushort),
    ]

# Keyboard
class Keyboard:
    def __init__(self, dev_node, name, descriptor):
        self.dev_node = dev_node
        self.name = name
        self.descriptor = descriptor

    def print(self):
        descriptor_hex = bytearray(self.descriptor).hex()
        logging.info(f"{self.dev_node} - {self.name}")
        logging.info(f"Descriptor: {descriptor_hex}")


class Keyboards:
    def __init__(self):
        self.keyboards = {}
        self.context = pyudev.Context()
        self.event_callback = None
 
    def callback(self, fd, cond, device):
        loop = True
        while loop:
            data = os.read(device.fileno(), 4096)
            self.event_callback(data)
            if not data:
                break
            if len(data) < 4096:
                loop = False
        return True

    def on_device_event(self, action, device):
        logging.info(action)
        logging.info(device)
        if action == 'remove':
            self.on_remove(device)
        elif action == 'add':
            self.on_add(device)

    def monitor_devices(self):
        logging.info("Monitor devices")
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by(subsystem='hidraw')
        observer = pyudev.MonitorObserver(monitor, self.on_device_event)
        observer.start()

    def watch(self, event_callback):
        logging.info("HID keyboard event watching started")
        self.event_callback = event_callback
        for device in self.context.list_devices(subsystem='hidraw'):
            self.on_add(device)
        self.monitor_devices()
        logging.info("Watching")

    def on_add(self, device):
        logging.info(device)
        hidraw = Hidraw(device.device_node)
        if is_keyboard(hidraw):
            keyboard = Keyboard(device.device_node, hidraw.name, hidraw.report_descriptor)
            keyboard.print()
            dev_file = open(keyboard.dev_node, "r+b")
            keyboard.source = GLib.io_add_watch(dev_file, GLib.IO_IN, self.callback, dev_file)
            self.keyboards[device.device_node] = keyboard

    def on_remove(self, device):
        if device.device_node in self.keyboards:
            keyboard = self.keyboards[device.device_node]
            keyboard.print()
            del self.keyboards[device.device_node]

    def print(self):
        for key, device in self.keyboards.items():
            hid_raw = Hidraw(device.device_node)
            d = hid_raw.report_descriptor
            s = bytearray(d).hex()
            logging.info(len(d))
            logging.info(hid_raw.name)
            logging.info(s)


def is_keyboard(hidraw):
    descriptor = hidraw.report_descriptor
    hex_string = bytearray(descriptor).hex()
    return hex_string.startswith("05010906a101050719e0")




# Mouse
class Mouse:
    def __init__(self, dev_node, name, descriptor):
        self.dev_node = dev_node
        self.name = name
        self.descriptor = descriptor

    def print(self):
        descriptor_hex = bytearray(self.descriptor).hex()
        logging.info(f"{self.dev_node} - {self.name}")
        logging.info(f"Descriptor: {descriptor_hex}")


class Mice:
    def __init__(self):
        self.mice = {}
        self.context = pyudev.Context()
        self.event_callback = None

    def callback(self, fd, cond, device):
        loop = True
        while loop:
            data = os.read(device.fileno(), 4096)
            self.event_callback(data)
            if not data:
                break
            if len(data) < 4096:
                loop = False
        return True

    def on_device_event(self, action, device):
        logging.info(action)
        logging.info(device)
        if action == 'remove':
            self.on_remove(device)
        elif action == 'add':
            self.on_add(device)

    def monitor_devices(self):
        logging.info("Monitor mouse devices")
        monitor = pyudev.Monitor.from_netlink(self.context)
        monitor.filter_by(subsystem='hidraw')
        observer = pyudev.MonitorObserver(monitor, self.on_device_event)
        observer.start()

    def watch(self, event_callback):
        logging.info("HID mouse event watching started")
        self.event_callback = event_callback
        for device in self.context.list_devices(subsystem='hidraw'):
            self.on_add(device)
        self.monitor_devices()
        logging.info("Watching mice")

    def on_add(self, device):
        logging.info(device)
        hidraw = Hidraw(device.device_node)
        if is_mouse(hidraw):
            mouse = Mouse(device.device_node, hidraw.name, hidraw.report_descriptor)
            mouse.print()
            dev_file = open(mouse.dev_node, "r+b")
            mouse.source = GLib.io_add_watch(dev_file, GLib.IO_IN, self.callback, dev_file)
            self.mice[device.device_node] = mouse

    def on_remove(self, device):
        if device.device_node in self.mice:
            mouse = self.mice[device.device_node]
            mouse.print()
            del self.mice[device.device_node]

    def print(self):
        for key, device in self.mice.items():
            hid_raw = Hidraw(device.device_node)
            d = hid_raw.report_descriptor
            s = bytearray(d).hex()
            logging.info(len(d))
            logging.info(hid_raw.name)
            logging.info(s)


def is_mouse(hidraw):
    """
    HID Usage Page 0x01 (Generic Desktop)
    HID Usage 0x02 (Mouse)
    Descriptor starts with: 05 01 09 02 A1 01 ...
    """
    descriptor = hidraw.report_descriptor
    hex_string = bytearray(descriptor).hex()
    return hex_string.startswith("05010902a101")



keyboards = Keyboards()
mice = Mice()
