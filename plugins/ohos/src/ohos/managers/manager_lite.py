#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2022 Huawei Device Co., Ltd.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import time
import threading

from xdevice import DeviceOsType
from xdevice import ManagerType
from xdevice import DeviceAllocationState
from xdevice import Plugin
from xdevice import get_plugin
from xdevice import IDeviceManager
from xdevice import platform_logger
from xdevice import convert_ip
from xdevice import convert_port
from xdevice import convert_serial
from xdevice import ConfigConst
from xdevice import check_mode_in_sys
from xdevice import XMLNode

from ohos.exception import LiteDeviceError
from ohos.config.config_manager import OHOSUserConfigManager

__all__ = ["ManagerLite"]

LOG = platform_logger("ManagerLite")


@Plugin(type=Plugin.MANAGER, id=ManagerType.lite_device)
class ManagerLite(IDeviceManager):
    """
    Class representing device manager that
    managing the set of available devices for testing
    """

    instance = None

    def __new__(cls):
        """
        Singleton instance
        """
        if cls.instance is None:
            cls.instance = object.__new__(cls)
        return cls.instance

    def __init__(self):
        self.devices_list = []
        self.list_con = threading.Condition()
        self.support_labels = ["ipcamera", "wifiiot", "watchGT"]
        self.support_types = ["device"]

    def init_environment(self, environment: str = "", user_config_file: str = "") -> bool:
        device_lite = get_plugin(plugin_type=Plugin.DEVICE,
                                 plugin_id=DeviceOsType.lite)[0]

        devices = OHOSUserConfigManager(
            config_file=user_config_file, env=environment).get_com_device(
            "environment/device")
        if not devices:
            return False
        for device in devices:
            try:
                device_lite_instance = device_lite.__class__()
                device_lite_instance.__init_device__(device)
                device_lite_instance.device_allocation_state = \
                    DeviceAllocationState.available
            except LiteDeviceError as exception:
                LOG.warning(exception)
                continue

            self.devices_list.append(device_lite_instance)
        return True

    def env_stop(self):
        pass

    def apply_device(self, device_option, timeout=10):
        """
        Request a device for testing that meets certain criteria.
        """
        del timeout
        LOG.debug("Lite apply device: apply lock")
        self.list_con.acquire()
        try:
            allocated_device = None
            for device in self.devices_list:
                if device_option.matches(device):
                    device.device_allocation_state = \
                        DeviceAllocationState.allocated
                    LOG.debug("Allocate device sn: %s, type: %s" % (
                        convert_serial(device.__get_serial__()),
                        device.__class__))
                    return device
            time.sleep(10)
            return allocated_device
        finally:
            LOG.debug("Lite apply device: release lock")
            self.list_con.release()

    def release_device(self, device):
        LOG.debug("Lite release device: apply lock")
        self.list_con.acquire()
        try:
            if device.device_allocation_state == \
                    DeviceAllocationState.allocated:
                device.device_allocation_state = \
                    DeviceAllocationState.available
            LOG.debug("Free device sn: %s, type: %s" % (
                device.__get_serial__(), device.__class__))
        finally:
            LOG.debug("Lite release device: release lock")
            self.list_con.release()

    def reset_device(self, device):
        pass

    def list_devices(self):
        if check_mode_in_sys(ConfigConst.app_test):
            return self.get_device_info()
        else:
            print("Lite devices:")
            print("{0:<20}{1:<16}{2:<16}{3:<16}{4:<16}{5:<16}{6:<16}".
                  format("SerialPort/IP", "Baudrate/Port", "OsType",
                         "Allocation",
                         "Product", "ConnectType", "ComType"))
            for device in self.devices_list:
                if device.device_connect_type == "remote" or \
                        device.device_connect_type == "agent":
                    print("{0:<20}{1:<16}{2:<16}{3:<16}{4:<16}{5:<16}".format(
                        convert_ip(device.device.host),
                        convert_port(device.device.port),
                        device.device_os_type,
                        device.device_allocation_state,
                        device.label,
                        device.device_connect_type))
                else:
                    for com_controller in device.device.com_dict:
                        print(
                            "{0:<20}{1:<16}{2:<16}{3:<16}{4:<16}{5:<16}{6:<16}".
                            format(convert_port(device.device.com_dict[
                                                    com_controller].serial_port),
                                   device.device.com_dict[
                                       com_controller].baud_rate,
                                   device.device_os_type,
                                   device.device_allocation_state,
                                   device.label,
                                   device.device_connect_type,
                                   com_controller))
            return ""

    def get_device_info(self):
        devices_info = {}
        return devices_info


class LiteNode(XMLNode):

    def __init__(self, usb_type, label):
        super().__init__()
        self.usb_type = usb_type
        self.label = label

    def __on_root_attrib__(self, attrib_dict):
        attrib_dict.update({"type": self.usb_type})
        attrib_dict.update({"label": self.label})

    def add_address(self, host, port):
        host_ele = self.create_node("ip")
        port_ele = self.create_node("port")
        host_ele.text = host
        port_ele.text = port
        self.get_root_node().append(host_ele)
        self.get_root_node().append(port_ele)
        return self

    def add_serial(self):
        self.get_root_node().append(self.create_node("serial"))
        return self

    def add_serial_connect(self, serial_index, com, _type):
        child_dict = {"com": com, "type": _type}
        return self.add_serial_child(serial_index, child_dict=child_dict)

    def add_serial_baund_rate(self, serial_index, baund_rate):
        child_dict = {"baund_rate": baund_rate}
        return self.add_serial_child(serial_index, child_dict=child_dict)

    def add_serial_data_bits(self, serial_index, data_bits):
        child_dict = {"data_bits": data_bits}
        return self.add_serial_child(serial_index, child_dict=child_dict)

    def add_serial_stop_bits(self, serial_index, stop_bits):
        child_dict = {"stop_bits": stop_bits}
        return self.add_serial_child(serial_index, child_dict=child_dict)

    def add_serial_timeout(self, serial_index, timeout):
        child_dict = {"timeout": timeout}
        return self.add_serial_child(serial_index, child_dict=child_dict)

    def add_serial_child(self, serial_index, child_dict):
        count = 0
        for serial in self.get_root_node().iter("serial"):
            if serial_index != count:
                continue
            count += 1
            for tag, text in dict(child_dict).items():
                ele = self.create_node(tag)
                ele.text = text
                serial.append(ele)
        return self
