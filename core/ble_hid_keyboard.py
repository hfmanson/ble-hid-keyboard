import logging
import signal

import dbus

from core.ble_dbus import Service, Characteristic, Application, BLUEZ_SERVICE_NAME, GATT_MANAGER_IFACE, Descriptor
from core.bluetooth_utils import turn_off
from core.hidraw_keyboard_mouse import keyboards
from core.hidraw_keyboard_mouse import mice

HID_REPORT_DESCRIPTOR = (
    # Keyboard (Report ID 1)
    "05010906A1018501"
    "050719E029E715002501750195088102"
    "750895018101"
    "0507190029FF150026FF00750895068100"
    "C0"
    # Mouse (Report ID 2)
    "05010902A1018502"
    "0901A100"
    "05091901290315002501750195038102"
    "750595018103"
    "0501093009311581257F750895028106"
    "09381581257F750895018106"
    "C0C0"
)

BATTERY_SERVICE_UUID = '180f'
BATTERY_LVL_UUID = '2a19'
DEVICE_INFO_SERVICE_UUID = '180A'
VENDOR_CHARACTERISTIC_UUID = '2A29'
PRODUCT_CHARACTERISTIC_UUID = '2A24'
VERSION_CHARACTERISTIC_UUID = '2A28'
PNP_CHARACTERISTIC_UUID = '2A50'
HID_SERVICE_UUID = '1812'
PROTOCOL_MODE_CHARACTERISTIC_UUID = '2A4E'
HID_INFO_CHARACTERISTIC_UUID = '2A4A'
CONTROL_POINT_CHARACTERISTIC_UUID = '2A4C'
REPORT_MAP_CHARACTERISTIC_UUID = '2A4B'
REPORT_CHARACTERISTIC_UUID = '2A4D'


class BleHidKeyboardApplication(Application):
    def __init__(self, bus, mainloop):
        Application.__init__(self, bus)
#        self.services = [HIDService(bus), DeviceInfoService(bus), BatteryService(bus)]
        self.services = [HIDService(bus), DeviceInfoService(bus), BatteryService(bus)]

        self.mainloop = mainloop
        self.bus = bus

    def register_callback(self):
        logging.info('GATT application registered')

    def error_callback(self, error):
        logging.error('Failed to register application: ' + str(error))
        self.mainloop.quit()

    def sigint_handler(self, sig, frame):
        logging.info("Signal Handler")
        if sig != signal.SIGINT:
            raise ValueError("Undefined handler for '{sig}'")
        else:
            logging.info('SIGINT RECEIVED')
            turn_off(self.bus)
            self.mainloop.quit()


class BatteryService(Service):
    def __init__(self, bus):
        Service.__init__(self, bus, BATTERY_SERVICE_UUID, True)
        self.characteristics = [BatteryLevelCharacteristic(self)]


class BatteryLevelCharacteristic(Characteristic):
    def __init__(self, service):
        Characteristic.__init__(self, self.__class__.__name__, service, BATTERY_LVL_UUID, ["read", "notify"])
        self.battery_lvl = 100

    def ReadValue(self, options):
        logging.info("Battery Level read: " + repr(self.battery_lvl))
        return [dbus.Byte(self.battery_lvl)]

    def StartNotify(self):
        logging.info("Start Battery Notify")

    def StopNotify(self):
        logging.info("Stop Battery Notify")


class DeviceInfoService(Service):
    def __init__(self, bus):
        Service.__init__(self, bus, DEVICE_INFO_SERVICE_UUID, True)
        self.characteristics = [self.ro_charateristic("PnP", PNP_CHARACTERISTIC_UUID, hex_2_dbus_array("02C41001000100")),
                                self.ro_charateristic("Vendor", VENDOR_CHARACTERISTIC_UUID, str_2_dbus_array("artyomsoft")),
                                self.ro_charateristic("Product", PRODUCT_CHARACTERISTIC_UUID, str_2_dbus_array("BLE Keyboard")),
                                self.ro_charateristic("Version", VERSION_CHARACTERISTIC_UUID, str_2_dbus_array("1.0.0"))
                                ]


class HIDService(Service):

    def __init__(self, bus):
        Service.__init__(self, bus, HID_SERVICE_UUID, True)
        self.characteristics = [
            ProtocolModeCharacteristic(self),
            HIDInfoCharacteristic(self),
            ControlPointCharacteristic(self),
            ReportMapCharacteristic(self),
            KeyboardInputReport(self),
            MouseInputReport(self)
        ]


class ProtocolModeCharacteristic(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(self, self.__class__.__name__,
                                service, PROTOCOL_MODE_CHARACTERISTIC_UUID, ["read", "write-without-response"])
        self.value = hex_2_dbus_array("01")
        logging.info(f"Created {self.name}: {self.value}")

    def ReadValue(self, options):
        logging.info(f"Read {self.value}: {self.value}")
        return self.value

    def WriteValue(self, value, options):
        logging.info(f"Write {self.value}: {value}")
        self.value = value


class HIDInfoCharacteristic(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(self, self.__class__.__name__,
                                service, HID_INFO_CHARACTERISTIC_UUID, ['read'])
        self.value = hex_2_dbus_array("01110002")
        logging.info(f"Created {self.name} value: {self.value}")

    def ReadValue(self, options):
        logging.info(f"Read {self.name}: {self.value}")
        return self.value


class ControlPointCharacteristic(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(self, self.__class__.__name__, service,
                                CONTROL_POINT_CHARACTERISTIC_UUID, ["write-without-response"])
        self.value = hex_2_dbus_array("00")
        logging.info(f"Created {self.name}: {self.value}")

    def WriteValue(self, value, options):
        logging.info(f"Write {self.name} {value}")
        self.value = value


class ReportMapCharacteristic(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(self, self.__class__.__name__, service, REPORT_MAP_CHARACTERISTIC_UUID, ['read'])
        # USB HID Report Descriptor
        self.value = hex_2_dbus_array(HID_REPORT_DESCRIPTOR)
        logging.info(f"Created {self.name}: {self.value}")

    def ReadValue(self, options):
        logging.info(f"Read {self.name}: {self.value}")
        return self.value


class ReportReferenceDescriptor(Descriptor):
    UUID = '2908'

    def __init__(self, bus, index, characteristic, report_id):
        Descriptor.__init__(
            self,
            bus,
            index,
            self.UUID,
            ['read'],
            characteristic
        )

        # [Report ID, Report Type]
        # Report Type 0x01 = Input Report
        self.value = dbus.Array(
            [report_id, 0x01],
            signature=dbus.Signature('y')
        )

    def ReadValue(self, options):
        return self.value

class KeyboardInputReport(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(
            self,
            self.__class__.__name__,
            service,
            REPORT_CHARACTERISTIC_UUID,
            ["read", "notify"]
        )

        REPORT_ID = 1
        # 8-byte leeg keyboard report
        self.value = dbus.Array([0] * 8, signature=dbus.Signature("y"))

        # Report Reference Descriptor (Report ID 1, Input Report)
        self.descriptors = [
            ReportReferenceDescriptor(service.bus, 0, self, REPORT_ID)
        ]

        logging.info("Created KeyboardInputReport characteristic")

    def send(self, raw):
        """
        raw = exact 8 bytes van HIDRAW:
        [modifier, reserved, key1, key2, key3, key4, key5, key6]
        """
        if len(raw) != 8:
            logging.warning(f"KeyboardInputReport: invalid length {len(raw)}")
            return False

        report = list(raw)

        #logging.info(f"KeyboardInputReport SEND: {report}")

        super().properties_changed({
            "Value": dbus.Array(report, signature=dbus.Signature("y"))
        })

        return True

    def ReadValue(self, options):
        return self.value

    def StartNotify(self):
        logging.info("KeyboardInputReport: StartNotify")
        keyboards.watch(self.send)

    def StopNotify(self):
        logging.info("KeyboardInputReport: StopNotify")


class MouseInputReport(Characteristic):

    def __init__(self, service):
        Characteristic.__init__(
            self,
            self.__class__.__name__,
            service,
            REPORT_CHARACTERISTIC_UUID,
            ["read", "notify"]
        )

        REPORT_ID = 2
        # 4-byte leeg mouse report
        # [buttons, dx, dy, wheel]
        self.value = dbus.Array([0] * 4, signature=dbus.Signature("y"))

        # Report Reference Descriptor (Report ID 2, Input Report)
        self.descriptors = [
            ReportReferenceDescriptor(service.bus, 1, self, REPORT_ID)
        ]

        logging.info("Created MouseInputReport characteristic")

    def send(self, raw):
        """
        raw = HIDRAW mouse report:
        [buttons, dx, dy, wheel]
        """
        if len(raw) < 3:
            logging.warning("MouseInputReport: invalid mouse report")
            return False

        # Zorg dat het altijd 4 bytes zijn
        report = list(raw[:4])
        while len(report) < 4:
            report.append(0)

        #logging.info(f"MouseInputReport SEND: {report}")

        super().properties_changed({
            "Value": dbus.Array(report, signature=dbus.Signature("y"))
        })

        return True

    def ReadValue(self, options):
        return self.value

    def StartNotify(self):
        logging.info("MouseInputReport: StartNotify")
        mice.watch(self.send)

    def StopNotify(self):
        logging.info("MouseInputReport: StopNotify")

def hex_2_dbus_array(value):
    return dbus.Array(bytearray.fromhex(value))


def str_2_dbus_array(value):
    return dbus.Array(value.encode(), signature=dbus.Signature("y"))


def register_application(adapter, bus, mainloop):
    logging.info("Registering GATT application...")
    app = BleHidKeyboardApplication(bus, mainloop)
    signal.signal(signal.SIGINT, app.sigint_handler)

    service_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter), GATT_MANAGER_IFACE)

    service_manager.RegisterApplication(app.get_path(), {},
                                        reply_handler=app.register_callback,
                                        error_handler=app.error_callback)
