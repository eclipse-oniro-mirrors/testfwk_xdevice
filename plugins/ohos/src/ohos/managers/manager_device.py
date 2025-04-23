#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2022 Huawei Device Co., Ltd.
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
import threading

from xdevice import ManagerType
from xdevice import Plugin
from xdevice import get_plugin
from xdevice import IDeviceManager
from xdevice import IFilter
from xdevice import platform_logger
from xdevice import ParamError
from xdevice import ConfigConst
from xdevice import HdcCommandRejectedException
from xdevice import ShellCommandUnresponsiveException
from xdevice import DeviceConnectorType
from xdevice import DeviceEvent
from xdevice import TestDeviceState
from xdevice import DeviceState
from xdevice import handle_allocation_event
from xdevice import DeviceAllocationState
from xdevice import DeviceStateMonitor
from xdevice import convert_serial
from xdevice import check_mode_in_sys
from xdevice import DeviceNode
from xdevice import DeviceSelector

from ohos.environment.dmlib import DeviceConnector
from ohos.environment.dmlib import HDC_NAME
from ohos.environment.dmlib import HDC_STD_NAME
from ohos.config.config_manager import OHOSUserConfigManager

__all__ = ["ManagerDevice"]

LOG = platform_logger("ManagerDevice")


@Plugin(type=Plugin.MANAGER, id=ManagerType.device)
class ManagerDevice(IDeviceManager, IFilter):
    """
    Class representing device manager
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
        self.global_device_filter = []
        self.lock_con = threading.Condition()
        self.list_con = threading.Condition()
        self.device_connectors = []
        self.usb_type = "usb-hdc"
        self.managed_device_listener = None
        self.support_labels = ["phone", "watch", "car", "tv", "tablet", "ivi", "2in1"]
        self.support_types = ["device"]
        self.wait_times = 0
        self.__device_alias = {}

    def init_environment(self, environment: str = "", user_config_file: str = "") -> bool:
        return self._start_device_monitor(environment, user_config_file)

    def env_stop(self):
        self._stop_device_monitor()

    def _start_device_monitor(self, environment: str = "", user_config_file: str = "") -> bool:
        self.managed_device_listener = ManagedDeviceListener(self)
        ohos_manager = OHOSUserConfigManager(
            config_file=user_config_file, env=environment)
        devices = ohos_manager.get_devices("environment/device")
        if devices:
            self.__set_device_alias(devices)
            try:
                for device in devices:
                    device_connector = DeviceConnector(
                        device.get("ip"), device.get("port"), device.get("usb_type"))
                    self.device_connectors.append(device_connector)
                    self.global_device_filter.extend(
                        ohos_manager.get_sn_list(device.get("sn")))
                    device_connector.add_device_change_listener(
                        self.managed_device_listener)
                    device_connector.start()
            except (ParamError, FileNotFoundError) as error:
                self.env_stop()
                for device in devices:
                    LOG.debug("Start %s error: %s" % (
                        device.get("usb_type"), error))
                    device_connector = DeviceConnector(
                        device.get("ip"), device.get("port"),
                        DeviceConnectorType.hdc)
                    self.device_connectors.append(device_connector)
                    device_connector.add_device_change_listener(self.managed_device_listener)
                    device_connector.start()
            return True
        else:
            LOG.error("OHOS Manager device is not supported, please check config user_config.xml", error_no="00108")
            return False

    def _stop_device_monitor(self):
        for device_connector in self.device_connectors:
            device_connector.monitor_lock.acquire(1)
            device_connector.remove_device_change_listener(self.managed_device_listener)
            device_connector.terminate()
            device_connector.monitor_lock.release()

    def apply_device(self, device_option, timeout=3):
        cnt = 0
        max_reply_apply_time = 3
        while cnt <= max_reply_apply_time:
            LOG.debug("Apply device: apply lock con lock")
            self.lock_con.acquire()
            try:
                device = self.allocate_device_option(device_option)
                if device or cnt == max_reply_apply_time:
                    return device
                LOG.debug("Wait for available device founded")
                self.lock_con.wait(cnt * 2 + 1)
                cnt += 1
            finally:
                LOG.debug("Apply device: release lock con lock")
                self.lock_con.release()

    def allocate_device_option(self, device_option):
        """
        Request a device for testing that meets certain criteria.
        """

        LOG.debug("Allocate device option: apply list con lock")
        if not self.list_con.acquire(timeout=5):
            LOG.debug("Allocate device option: list con wait timeout")
            return None
        try:
            allocated_device = None
            LOG.debug("Require device label is: %s" % device_option.label)
            for device in self.devices_list:
                if device_option.matches(device):
                    self.handle_device_event(device,
                                             DeviceEvent.ALLOCATE_REQUEST)
                    LOG.debug("Allocate device sn: %s, type: %s" % (
                        device.__get_serial__(), device.__class__))
                    return device
            return allocated_device

        finally:
            LOG.debug("Allocate device option: release list con lock")
            self.list_con.release()

    def release_device(self, device):
        LOG.debug("Release device: apply list con lock")
        self.list_con.acquire()
        try:
            if device.test_device_state == TestDeviceState.ONLINE:
                self.handle_device_event(device, DeviceEvent.FREE_AVAILABLE)
            else:
                self.handle_device_event(device, DeviceEvent.FREE_UNAVAILABLE)
            LOG.debug("Free device sn: %s, type: %s" % (
                device.__get_serial__(), device.__class__.__name__))
        finally:
            LOG.debug("Release_device: release list con lock")
            self.list_con.release()

    def lock_device(self, device):
        LOG.debug("Apply device: apply list con lock")
        self.list_con.acquire()
        try:
            if device.test_device_state == TestDeviceState.ONLINE:
                self.handle_device_event(device, DeviceEvent.ALLOCATE_REQUEST)

            LOG.debug("Lock device sn: %s, type: %s" % (
                device.__get_serial__(), device.__class__.__name__))

        finally:
            LOG.debug("Lock_device: release list con lock")
            self.list_con.release()

    def reset_device(self, device):
        if device and hasattr(device, "reset"):
            device.reset()

    def find_device(self, idevice):
        LOG.debug("Find device: apply list con lock")
        self.list_con.acquire()
        try:
            for device in self.devices_list:
                if device == idevice:
                    return device
            return None
        finally:
            LOG.debug("Find device: release list con lock")
            self.list_con.release()

    def append_device_by_sort(self, device_instance):
        LOG.debug("Append device: apply list con lock")
        self.list_con.acquire()
        try:
            if (not self.global_device_filter or
                    not self.devices_list or
                    device_instance.device_sn not in self.global_device_filter):
                self.devices_list.append(device_instance)
            else:
                device_dict = dict(zip(
                    self.global_device_filter,
                    list(range(1, len(self.global_device_filter) + 1))))
                for index in range(len(self.devices_list)):
                    if self.devices_list[index].device_sn not in \
                            self.global_device_filter:
                        self.devices_list.insert(index, device_instance)
                        break
                    if device_dict[device_instance.device_sn] < \
                            device_dict[self.devices_list[index].device_sn]:
                        self.devices_list.insert(index, device_instance)
                        break
                else:
                    self.devices_list.append(device_instance)
        finally:
            LOG.debug("Append device: release list con lock")
            self.list_con.release()

    def find_or_create(self, idevice):
        try:
            device = self.find_device(idevice)
            if device is None:
                device = get_plugin(
                    plugin_type=Plugin.DEVICE,
                    plugin_id=idevice.device_os_type)[0]
                device_sn = idevice.device_sn
                device_instance = device.__class__()
                device_instance.__set_serial__(device_sn)
                device_instance.device_id = self.__device_alias.get(device_sn, "")
                device_instance.host = idevice.host
                device_instance.port = idevice.port
                device_instance.usb_type = self.usb_type
                LOG.debug("Create device(%s) host is %s, "
                          "port is %s, device sn is %s, usb type is %s" %
                          (device_instance, device_instance.host,
                           device_instance.port, device_instance.device_sn,
                           device_instance.usb_type))
                device_instance.device_state = idevice.device_state
                device_instance.test_device_state = \
                    TestDeviceState.get_test_device_state(
                        device_instance.device_state)
                device_instance.device_state_monitor = \
                    DeviceStateMonitor(device_instance)
                if idevice.device_state == DeviceState.ONLINE or \
                        idevice.device_state == DeviceState.CONNECTED:
                    device_instance.get_device_type()
                self.append_device_by_sort(device_instance)
                device = device_instance
            else:
                LOG.debug("Find device(%s), host is %s, "
                          "port is %s, device sn is %s, usb type is %s" %
                          (device, device.host, device.port, device.device_sn,
                           device.usb_type))
            return device
        except (HdcCommandRejectedException, ShellCommandUnresponsiveException) as hcr_error:
            LOG.debug("%s occurs error. Reason:%s" %
                      (idevice.device_sn, hcr_error))
            return None

    def remove(self, idevice):
        LOG.debug("Remove: apply list con lock")
        self.list_con.acquire()
        try:
            self.devices_list.remove(idevice)
        finally:
            LOG.debug("Remove: release list con lock")
            self.list_con.release()

    def handle_device_event(self, device, event):
        state_changed = None
        old_state = device.device_allocation_state
        new_state = handle_allocation_event(old_state, event)

        if new_state == DeviceAllocationState.checking_availability:
            if self.global_device_filter and \
                    device.device_sn not in self.global_device_filter:
                event = DeviceEvent.AVAILABLE_CHECK_IGNORED
            else:
                event = DeviceEvent.AVAILABLE_CHECK_PASSED
            new_state = handle_allocation_event(new_state, event)

        if old_state != new_state:
            state_changed = True
            device.device_allocation_state = new_state

        if state_changed is True and \
                new_state == DeviceAllocationState.available:
            # notify_device_state_change
            LOG.debug("Handle device event apply lock con")
            self.lock_con.acquire()
            LOG.debug("Find available device")
            self.lock_con.notify_all()
            LOG.debug("Handle device event release lock con")
            self.lock_con.release()

        if device.device_allocation_state == \
                DeviceAllocationState.unknown:
            self.remove(device)
        return

    def launch_emulator(self):
        pass

    def kill_emulator(self):
        pass

    def list_devices(self):
        for device_connector in self.device_connectors:
            device_connector.monitor_lock.acquire(1)
        try:
            if check_mode_in_sys(ConfigConst.app_test):
                return self.get_device_info()
            else:
                print("OHOS devices:")
                print("{0:<20}{1:<16}{2:<16}{3:<16}{4:<16}{5:<16}{6:<16}".format(
                    "Serial", "OsType", "State", "Allocation", "Product", "host",
                    "port"))
                for device in self.devices_list:
                    print(
                        "{0:<20}{1:<16}{2:<16}{3:<16}{4:<16}{5:<16}{6:<16}".format(
                            convert_serial(device.device_sn),
                            device.device_os_type,
                            device.test_device_state.value,
                            device.device_allocation_state,
                            device.label if device.label else 'None',
                            device.host, device.port))
                return ""
        finally:
            for device_connector in self.device_connectors:
                device_connector.monitor_lock.release()

    def get_device_info(self):
        devices_info = []
        for device in self.devices_list:
            result = device.get_device_params()
            devices_info.append(result)
        return devices_info

    def __set_device_alias(self, devices):
        for device in devices:
            sn, alias = device.get("sn"), device.get("alias")
            if sn and alias:
                self.__device_alias.update({sn: alias})

    def __filter_selector__(self, selector):
        if isinstance(selector, DeviceSelector):
            return True
        return False

    def __filter_xml_node__(self, node):
        if isinstance(node, DeviceNode):
            if HDC_NAME in node.get_connectors() or \
                    HDC_STD_NAME in node.get_connectors():
                return True
        return False


class ManagedDeviceListener(object):
    """
    A class to listen for and act on device presence updates from ddmlib
    """

    def __init__(self, manager):
        self.manager = manager

    def device_changed(self, idevice):
        test_device = self.manager.find_or_create(idevice)
        if test_device is None:
            return
        new_state = TestDeviceState.get_test_device_state(idevice.device_state)
        test_device.test_device_state = new_state
        if hasattr(test_device, "_is_root"):
            test_device._is_root = None
        if new_state == TestDeviceState.ONLINE:
            self.manager.handle_device_event(test_device,
                                             DeviceEvent.STATE_CHANGE_ONLINE)
            LOG.debug("Set device %s %s to true" % (
                convert_serial(test_device.device_sn), ConfigConst.recover_state))
            test_device.set_recover_state(True)
        elif new_state == TestDeviceState.NOT_AVAILABLE:
            self.manager.handle_device_event(test_device,
                                             DeviceEvent.STATE_CHANGE_OFFLINE)
            if hasattr(test_device, "call_proxy_listener"):
                test_device.call_proxy_listener()
        test_device.device_state_monitor.set_state(
            test_device.test_device_state)
        LOG.debug("Device changed to %s: %s %s %s %s" % (
            new_state, convert_serial(idevice.device_sn),
            idevice.device_os_type, idevice.host, idevice.port))

    def device_connected(self, idevice):
        test_device = self.manager.find_or_create(idevice)
        if test_device is None:
            return

        new_state = TestDeviceState.get_test_device_state(idevice.device_state)
        test_device.test_device_state = new_state
        if test_device.test_device_state == TestDeviceState.ONLINE:
            self.manager.handle_device_event(test_device,
                                             DeviceEvent.CONNECTED_ONLINE)
        elif new_state == TestDeviceState.NOT_AVAILABLE:
            self.manager.handle_device_event(test_device,
                                             DeviceEvent.CONNECTED_OFFLINE)
        test_device.device_state_monitor.set_state(
            test_device.test_device_state)
        LOG.debug("Device connected: {} {} {} {}, state: {}".format(
            convert_serial(idevice.device_sn), idevice.device_os_type,
            idevice.host, idevice.port, test_device.test_device_state))
        LOG.debug("Set device %s %s to true" % (
            convert_serial(idevice.device_sn), ConfigConst.recover_state))
        test_device.set_recover_state(True)

    def device_disconnected(self, disconnected_device):
        test_device = self.manager.find_device(disconnected_device)
        if test_device is not None:
            test_device.test_device_state = TestDeviceState.NOT_AVAILABLE
            self.manager.handle_device_event(test_device,
                                             DeviceEvent.DISCONNECTED)
            test_device.device_state_monitor.set_state(
                TestDeviceState.NOT_AVAILABLE)
        LOG.debug("Device disconnected: %s %s %s %s" % (
            convert_serial(disconnected_device.device_sn),
            disconnected_device.device_os_type,
            disconnected_device.host, disconnected_device.port))
