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

import re
import shlex
import shutil
import time
import os
import threading
import copy
import platform
import subprocess
import tempfile
from typing import Tuple

from xdevice import DeviceOsType
from xdevice import FilePermission
from xdevice import ParamError
from xdevice import ProductForm
from xdevice import ReportException
from xdevice import IDevice
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import exec_cmd
from xdevice import ConfigConst
from xdevice import HdcError
from xdevice import DeviceAllocationState
from xdevice import DeviceConnectorType
from xdevice import TestDeviceState
from xdevice import AdvanceDeviceOption
from xdevice import convert_serial
from xdevice import check_path_legal
from xdevice import start_standing_subprocess
from xdevice import stop_standing_subprocess
from xdevice import DeviceProperties
from xdevice import get_cst_time
from xdevice import get_file_absolute_path
from xdevice import Platform
from xdevice import AgentMode
from xdevice import ShellCommandUnresponsiveException
from xdevice import Variables
from ohos.environment.dmlib import HdcHelper
from ohos.environment.dmlib import CollectingOutputReceiver
from ohos.utils import parse_strings_key_value
from ohos.error import ErrorMessage
from ohos.constants import ConnectType

__all__ = ["Device"]
TIMEOUT = 300 * 1000
RETRY_ATTEMPTS = 2
DEFAULT_UNAVAILABLE_TIMEOUT = 20 * 1000
BACKGROUND_TIME = 2 * 60 * 1000
LOG = platform_logger("Device")
DEVICE_TEMP_PATH = "/data/local/tmp"
QUERY_DEVICE_PROP_BIN = "testcases/queryStandard"
NATIVE_CRASH_PATH = "/data/log/faultlog/temp"
JS_CRASH_PATH = "/data/log/faultlog/faultlogger"
ROOT_PATH = "/data/log/faultlog"
KINGKONG_PATH = "/data/local/tmp/kingkongDir"
LOGLEVEL = ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
HILOG_PATH = "/data/log/hilog"


class CaptureMode:
    DEFAULT = "default"  # snapshot_display
    HAP = "hap"          # hap


def perform_device_action(func):
    def callback_to_outer(device, msg):
        # callback to decc ui
        if getattr(device, "callback_method", None):
            device.callback_method(msg)

    def device_action(self, *args, **kwargs):
        if not self.get_recover_state():
            LOG.debug("Device {} {} is false".format(self.device_sn,
                                                     ConfigConst.recover_state))
            return None
        # avoid infinite recursion, such as device reboot
        abort_on_exception = bool(kwargs.get("abort_on_exception", False))
        if abort_on_exception:
            result = func(self, *args, **kwargs)
            return result

        tmp = int(kwargs.get("retry", RETRY_ATTEMPTS))
        retry = tmp + 1 if tmp > 0 else 1
        exception = None
        for _ in range(retry):
            try:
                result = func(self, *args, **kwargs)
                return result
            except ReportException as error:
                self.log.exception("Generate report error!", exc_info=False)
                exception = error
            except (ConnectionResetError,  # pylint:disable=undefined-variable
                    ConnectionRefusedError,  # pylint:disable=undefined-variable
                    ConnectionAbortedError) as error:  # pylint:disable=undefined-variable
                self.log.error("error type: {}, error: {}".format
                               (error.__class__.__name__, error))
                # check hdc if is running
                if not HdcHelper.check_if_hdc_running():
                    LOG.debug("{} not running, set device {} {} false".format(
                        HdcHelper.CONNECTOR_NAME, self.device_sn, ConfigConst.recover_state))
                    self.set_recover_state(False)
                    callback_to_outer(self, "recover failed")
                    raise error
                callback_to_outer(self, "error:{}, prepare to recover".format(error))
                if not self.recover_device():
                    LOG.debug("Set device {} {} false".format(
                        self.device_sn, ConfigConst.recover_state))
                    self.set_recover_state(False)
                    callback_to_outer(self, "recover failed")
                    raise error
                exception = error
                callback_to_outer(self, "recover success")
            except HdcError as error:
                self.log.error("error type: {}, error: {}".format(error.__class__.__name__, error))
                callback_to_outer(self, "error:{}, prepare to recover".format(error))
                if not self.recover_device():
                    LOG.debug("Set device {} {} false".format(
                        self.device_sn, ConfigConst.recover_state))
                    self.set_recover_state(False)
                    callback_to_outer(self, "recover failed")
                    raise error
                exception = error
                callback_to_outer(self, "recover success")
            except Exception as error:
                self.log.exception("error type: {}, error: {}".format(
                    error.__class__.__name__, error), exc_info=False)
                exception = error
        raise exception

    return device_action


@Plugin(type=Plugin.DEVICE, id=DeviceOsType.default)
class Device(IDevice):
    """
    Class representing a device.

    Each object of this class represents one device in xDevice,
    including handles to hdc, fastboot, and test agent (DeviceTest.apk).

    Attributes:
        device_sn: A string that's the serial number of the device.
    """

    device_sn = None
    host = None
    port = None
    usb_type = DeviceConnectorType.hdc
    is_timeout = False
    device_hilog_proc = None
    device_os_type = DeviceOsType.default
    test_device_state = None
    device_allocation_state = DeviceAllocationState.available
    label = ProductForm.phone
    log = platform_logger("Device")
    device_state_monitor = None
    reboot_timeout = 2 * 60 * 1000
    _device_log_collector = None

    _agent_mode = AgentMode.bin
    is_oh = True
    _arch = None
    rpc_timeout = 300
    device_id = None
    reconnecttimes = 0
    _h_port = None
    oh_module_package = None
    module_ablity_name = None
    _device_report_path = None
    test_platform = Platform.ohos
    _webview = None
    _is_root = None
    tmp_path = DEVICE_TEMP_PATH
    _uitest_version = None
    _use_unix_socket = None

    model_dict = {
        'default': ProductForm.phone,
        'phone': ProductForm.phone,
        'car': ProductForm.car,
        'tv': ProductForm.television,
        'watch': ProductForm.watch,
        'tablet': ProductForm.tablet,
        '2in1': ProductForm._2in1,
        'wearable': ProductForm.wearable,
        'nosdcard': ProductForm.phone
    }

    device_params = {
        DeviceProperties.system_sdk: "",
        DeviceProperties.system_version: "",
        DeviceProperties.build_number: "",
        DeviceProperties.cpu_abi: "",
        DeviceProperties.device_form: "PHYSICAL",
        DeviceProperties.software_version: "",
        DeviceProperties.fault_code: "",
        DeviceProperties.fold_screen: "",
        DeviceProperties.hardware: "",
        DeviceProperties.is_ark: "",
        DeviceProperties.mac: "",
        DeviceProperties.mobile_service: "",
        DeviceProperties.model: "",
        DeviceProperties.rom: "",
        DeviceProperties.rooted: "",
        DeviceProperties.sn: "",
        DeviceProperties.xres: "",
        DeviceProperties.yres: "",
        DeviceProperties.manufacturer: "",
        DeviceProperties.kind: 2
    }

    device_params_command = {
        DeviceProperties.system_sdk: "const.ohos.apiversion",
        DeviceProperties.system_version: "",
        DeviceProperties.build_number: "",
        DeviceProperties.cpu_abi: "const.product.cpu.abilist",
        DeviceProperties.device_form: "",
        DeviceProperties.software_version: "const.product.software.version",
        DeviceProperties.fault_code: "",
        DeviceProperties.fold_screen: "",
        DeviceProperties.hardware: "ohos.boot.hardware",
        DeviceProperties.is_ark: "",
        DeviceProperties.mac: "",
        DeviceProperties.mobile_service: "ro.odm.config.modem_number",
        DeviceProperties.model: "const.product.model",
        DeviceProperties.rom: "",
        DeviceProperties.rooted: "",
        DeviceProperties.xres: "",
        DeviceProperties.yres: "",
        DeviceProperties.manufacturer: "const.product.manufacturer",
        DeviceProperties.kind: ""
    }

    def __init__(self):
        self.extend_value = {}
        self.device_lock = threading.RLock()
        self.forward_ports = []
        self.forward_ports_abc = []
        self.proxy_listener = None
        self.win_proxy_listener = None
        self.device_props = {}
        self.device_description = {}
        self.clean_proxy_function = []
        self.reconnect_proxy_function = []

    def __eq__(self, other):
        return self.device_sn == other.__get_serial__() and \
            self.device_os_type == other.device_os_type and \
            self.host == other.host

    @property
    def connect_type(self):
        if self.host == "127.0.0.1":
            return ConnectType.local
        else:
            return ConnectType.remote

    def init_description(self):
        if self.device_description:
            return
        desc = {
            DeviceProperties.sn: convert_serial(self.device_sn),
            DeviceProperties.model: self.get_property_value("const.product.model"),
            DeviceProperties.type_: self.get_device_type(),
            DeviceProperties.platform: self._get_device_platform(),
            DeviceProperties.version: self.get_property_value(
                self.device_params_command.get(DeviceProperties.software_version)),
            DeviceProperties.others: self.device_props
        }
        self.device_description.update(desc)

    def __set_serial__(self, device_sn=""):
        self.device_sn = device_sn
        return self.device_sn

    def __get_serial__(self):
        return self.device_sn

    @property
    def arch(self):
        if self._arch is None:
            text = self.execute_shell_command("file /system/bin/uitest")
            if "x86_64" in text or "x86-64" in text:
                self._arch = "x86_64"
            elif "64" in text:
                self._arch = "64"
            elif "32" in text:
                self._arch = "32"
            else:
                self._arch = "64"
        return self._arch

    @property
    def uitest_version(self):
        if self._uitest_version is None:
            self._uitest_version = self.execute_shell_command("/system/bin/uitest --version")
            self._uitest_version = self._uitest_version.strip()
            self.log.info(f"Uitest version is {self._uitest_version}")
        return self._uitest_version

    @property
    def ui_socket_mode(self):
        if self._use_unix_socket is None:
            self._use_unix_socket = False
        return self._use_unix_socket

    def extend_device_props(self):
        if self.device_props:
            return
        try:
            query_bin_path = get_file_absolute_path(QUERY_DEVICE_PROP_BIN)
        except ParamError:
            query_bin_path = ""
        if query_bin_path == "":
            return
        self.push_file(query_bin_path, DEVICE_TEMP_PATH)
        file_name = os.path.basename(query_bin_path)
        cmd = f"cd {DEVICE_TEMP_PATH} && chmod +x {file_name} && ./{file_name}"
        out = self.execute_shell_command(
            cmd, timeout=5 * 1000, output_flag=False, retry=RETRY_ATTEMPTS, abort_on_exception=False).strip()
        if not out:
            return
        LOG.info(out)
        params = parse_strings_key_value(out)
        self.device_props.update(params)

    def get(self, key=None, default=None):
        if not key:
            return default
        value = getattr(self, key, None)
        if value:
            return value
        else:
            return self.extend_value.get(key, default)

    def recover_device(self):
        if not self.get_recover_state():
            LOG.debug("Device %s %s is false, cannot recover device" % (
                self.device_sn, ConfigConst.recover_state))
            return False

        LOG.debug("Wait device %s to recover" % self.device_sn)
        # tcpip类型的设备，需要connect成功后，才能被hdc list targets命令查询到
        self.reconnect_tcpip_device()

        result = self.device_state_monitor.wait_for_device_available(self.reboot_timeout)
        if result:
            self.device_log_collector.restart_catch_device_log()
        return result

    def reconnect_tcpip_device(self):
        """运行tconn命令，连接tcpip类型的设备"""
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):\d+'
        if not re.match(pattern, self.device_sn):
            return

        if self.host != "127.0.0.1":
            cmd = [HdcHelper.CONNECTOR_NAME, "-s", "{}:{}".format(self.host, self.port), "tconn", self.device_sn]
        else:
            cmd = [HdcHelper.CONNECTOR_NAME, "tconn", self.device_sn]

        timeout = self.reboot_timeout
        LOG.debug(f"reconnect to device {self.device_sn}, timeout: {timeout}ms")

        count, reconnect_result = 1, False
        start_time = int(time.time() * 1000)
        while int(time.time() * 1000) - start_time < timeout:
            try:
                LOG.debug(f"the {count} times to reconnect to device")
                LOG.debug(" ".join(cmd))
                out = exec_cmd(cmd, timeout=2)
                LOG.debug(out)
                # when device connected, output as: connected to ip:port
                if "Connect OK" in out or "Target is connected" in out:
                    reconnect_result = True
                    break
                time.sleep(5)
                count += 1
            except Exception as e:
                LOG.error(f"reconnect to device error, {e}")
        if not reconnect_result:
            LOG.warning("reconnect to device failed")

    def _get_device_platform(self):
        self.test_platform = "OpenHarmony"
        return self.test_platform

    def get_device_type(self):
        try:
            model = self.get_property("const.product.devicetype",
                                      abort_on_exception=True)
        except ShellCommandUnresponsiveException:
            model = "default"
        model = "default" if model == "" else model
        self.label = self.model_dict.get(model, ProductForm.phone)
        return self.label

    def get_property(self, prop_name, retry=RETRY_ATTEMPTS,
                     abort_on_exception=False):
        """
        Hdc command, dmlib function.
        """
        if not self.get_recover_state():
            return ""
        command = "param get %s" % prop_name
        stdout = self.execute_shell_command(command, timeout=5 * 1000,
                                            output_flag=False,
                                            retry=retry,
                                            abort_on_exception=abort_on_exception).strip()
        if stdout:
            LOG.debug(stdout)
        return stdout

    def get_property_value(self, prop_name, retry=RETRY_ATTEMPTS,
                           abort_on_exception=False):
        """
        Hdc command, ddmlib function.
        """
        if not self.get_recover_state():
            return ""
        command = "param get %s" % prop_name
        stdout = self.execute_shell_command(command, timeout=5 * 1000,
                                            output_flag=False,
                                            retry=retry,
                                            abort_on_exception=abort_on_exception).strip()
        if "fail" in stdout:
            return ""
        return stdout

    @perform_device_action
    def connector_command(self, command, **kwargs):
        timeout = int(kwargs.get("timeout", TIMEOUT)) / 1000
        error_print = bool(kwargs.get("error_print", True))
        join_result = bool(kwargs.get("join_result", False))
        timeout_msg = '' if timeout == 300.0 else \
            " with timeout %ss" % timeout
        if self.host != "127.0.0.1":
            cmd = [HdcHelper.CONNECTOR_NAME, "-s", "{}:{}".format(self.host, self.port), "-t", self.device_sn]
        else:
            cmd = [HdcHelper.CONNECTOR_NAME, "-t", self.device_sn]
        LOG.debug("{} execute command {} {} {}".format(convert_serial(self.device_sn),
                                                       HdcHelper.CONNECTOR_NAME,
                                                       command, timeout_msg))
        if isinstance(command, list):
            cmd.extend(command)
        else:
            command = command.strip()
            cmd.extend(command.split(" "))
        result = exec_cmd(cmd, timeout, error_print, join_result)
        if not result:
            return result
        is_print = bool(kwargs.get("is_print", True))
        if is_print:
            for line in str(result).split("\n"):
                if line.strip():
                    LOG.debug(line.strip())
        return result

    @perform_device_action
    def execute_shell_command(self, command, timeout=TIMEOUT,
                              receiver=None, **kwargs):
        if not receiver:
            collect_receiver = CollectingOutputReceiver()
            HdcHelper.execute_shell_command(
                self, command, timeout=timeout,
                receiver=collect_receiver, **kwargs)
            if "Device not founded or connected" in collect_receiver.output:
                LOG.info("Device is Disconnected")
                raise ConnectionAbortedError
            return collect_receiver.output
        else:
            return HdcHelper.execute_shell_command(
                self, command, timeout=timeout,
                receiver=receiver, **kwargs)

    def execute_shell_cmd_background(self, command, timeout=TIMEOUT,
                                     receiver=None):
        status = HdcHelper.execute_shell_command(self, command,
                                                 timeout=timeout,
                                                 receiver=receiver)

        self.wait_for_device_not_available(DEFAULT_UNAVAILABLE_TIMEOUT)
        self.device_state_monitor.wait_for_device_available(BACKGROUND_TIME)
        cmd = "target mount"
        self.connector_command(cmd)
        self.device_log_collector.restart_catch_device_log()
        return status

    def wait_for_device_not_available(self, wait_time):
        return self.device_state_monitor.wait_for_device_not_available(
            wait_time)

    def _wait_for_device_online(self, wait_time=None):
        return self.device_state_monitor.wait_for_device_online(wait_time)

    def _do_reboot(self):
        HdcHelper.reboot(self)
        self.recover_device()

    def _reboot_until_online(self):
        self._do_reboot()

    def reboot(self):
        self._reboot_until_online()

    @perform_device_action
    def install_package(self, package_path, command=""):
        if package_path is None:
            raise HdcError(ErrorMessage.Device.Code_0303005)
        return HdcHelper.install_package(self, package_path, command)

    @perform_device_action
    def uninstall_package(self, package_name):
        return HdcHelper.uninstall_package(self, package_name)

    @perform_device_action
    def push_file(self, local, remote, **kwargs):
        """
        Push a single file.
        The top directory won't be created if is_create is False (by default)
        and vice versa
        """
        local = "\"{}\"".format(local)
        remote = "\"{}\"".format(remote)
        if local is None:
            raise HdcError(ErrorMessage.Device.Code_0303001)

        remote_is_dir = kwargs.get("remote_is_dir", False)
        if remote_is_dir:
            ret = self.execute_shell_command("test -d %s && echo 0" % remote, retry=0)
            if not (ret != "" and len(str(ret).split()) != 0 and
                    str(ret).split()[0] == "0"):
                self.execute_shell_command("mkdir -p %s" % remote, retry=0)

        self.connector_command("file send {} {}".format(local, remote), retry=0)

        if not self.is_file_exist(remote):
            err_msg = ErrorMessage.Device.Code_0303004.format(local, remote)
            LOG.error(err_msg)
            raise HdcError(err_msg)

    @perform_device_action
    def pull_file(self, remote, local, **kwargs):
        """
        Pull a single file.
        The top directory won't be created if is_create is False (by default)
        and vice versa
        """
        local = "\"{}\"".format(local)
        remote = "\"{}\"".format(remote)
        # 改成走socket方式拉文件，hdc回应拉取成功，实际文件没有被拉下来，而使用命令方式，没有问题
        self.connector_command("file recv {} {}".format(remote, local), retry=0)

    @property
    def is_root(self):
        if self._is_root is None:
            ret = self.execute_shell_command("whoami")
            LOG.debug(ret)
            self._is_root = True if ret and "root" in ret else False
        return self._is_root

    def is_directory(self, path):
        path = check_path_legal(path)
        output = self.execute_shell_command("ls -ld {}".format(path))
        if output and output.startswith('d'):
            return True
        return False

    def is_file_exist(self, file_path):
        file_path = check_path_legal(file_path)
        output = self.execute_shell_command("ls {}".format(file_path))
        if output and "No such file or directory" not in output:
            return True
        return False

    def get_recover_result(self, retry=RETRY_ATTEMPTS):
        command = "param get bootevent.boot.completed"
        stdout = self.execute_shell_command(command, timeout=5 * 1000,
                                            output_flag=False, retry=retry,
                                            abort_on_exception=True).strip()
        LOG.debug("device recover status: {}".format(stdout))
        return stdout

    def set_recover_state(self, state):
        with self.device_lock:
            setattr(self, ConfigConst.recover_state, state)
            if not state:
                self.test_device_state = TestDeviceState.NOT_AVAILABLE
                self.call_proxy_listener()

    def get_recover_state(self, default_state=True):
        with self.device_lock:
            state = getattr(self, ConfigConst.recover_state, default_state)
            return state

    def wait_for_boot_completion(self):
        """Waits for the device to boot up.

        Returns:
            True if the device successfully finished booting, False otherwise.
        """
        return self.device_state_monitor.wait_for_boot_complete(self.reboot_timeout)

    @classmethod
    def check_recover_result(cls, recover_result):
        return "true" in recover_result

    @property
    def device_log_collector(self):
        if self._device_log_collector is None:
            self._device_log_collector = DeviceLogCollector(self)
        return self._device_log_collector

    def close(self):
        self.reconnecttimes = 0

    def reset(self):
        self.log.debug("start reset device...")
        self.call_proxy_listener()
        for function in self.clean_proxy_function:
            function()
        self.clean_proxy_function.clear()
        self.reconnect_proxy_function.clear()
        self.device_log_collector.stop_restart_catch_device_log()

    @property
    def is_bin(self):
        # _agent_mode init in device test driver
        # 0 is hap, 1 is abc, 2 is bin
        return False if self._agent_mode == AgentMode.hap else True

    def set_agent_mode(self, mode: AgentMode = AgentMode.bin):
        if self.arch == "32":
            self._agent_mode = AgentMode.hap
            LOG.debug("Current mode is normal mode.")
        else:
            self._agent_mode = mode
            LOG.debug("Current mode is {} mode.".format(mode))


    @property
    def abc_proxy(self):
        # ui operation agent
        return self.ui_proxy

    @property
    def ui_proxy(self):
        # ui operation agent
        ui_proxy = getattr(self, "_ui_proxy", None)
        if ui_proxy is None:
            from ohos.proxy.ui_proxy import UIProxy
            self._ui_proxy = UIProxy()
            self._ui_proxy.__set_device__(self)
            self._ui_proxy.__init_proxy__()
            self.clean_proxy_function.append(self._ui_proxy.__clean_proxy__)
        return self._ui_proxy.rpc_proxy

    @classmethod
    def set_module_package(cls, module_packag):
        cls.oh_module_package = module_packag

    @classmethod
    def set_moudle_ablity_name(cls, module_ablity_name):
        cls.module_ablity_name = module_ablity_name

    def call_proxy_listener(self):
        if ((self.is_bin and getattr(self, "_ui_proxy", None)) or
                (not self.is_bin and getattr(self, "_hap_proxy", None))):
            if self.proxy_listener is not None:
                self.proxy_listener(is_exception=True)
        if getattr(self, "_hap_proxy", None):
            if self.win_proxy_listener is not None:
                self.win_proxy_listener(is_exception=True)

    def install_app(self, remote_path, command):
        try:
            ret = self.execute_shell_command(
                "pm install %s %s" % (command, remote_path))
            if ret is not None and str(
                    ret) != "" and "Unknown option: -g" in str(ret):
                return self.execute_shell_command(
                    "pm install -r %s" % remote_path)
            return ret
        except Exception as error:
            self.log.error("%s, maybe there has a warning box appears "
                           "when installing RPC." % error)
            return False

    def uninstall_app(self, package_name):
        try:
            ret = self.execute_shell_command("pm uninstall %s" % package_name)
            self.log.debug(ret)
            return ret
        except Exception as err:
            self.log.error('DeviceTest-20013 uninstall: %s' % str(err))
            return False

    def reconnect(self, waittime=60, proxy=None):
        """
        @summary: Reconnect the device.
        """
        self.call_proxy_listener()

        if not self.recover_device():
            for function in self.clean_proxy_function:
                function()
            raise Exception("Reconnect timed out.")


        ui_proxy = getattr(self, "_ui_proxy", None)
        if ui_proxy and (proxy is None or proxy == AgentMode.bin):
            ui_proxy.__reconnect_proxy__()

        for function in self.reconnect_proxy_function:
            function()

    def take_picture(self, name: str, display_id: int = 0):
        """
        @summary: 截取手机屏幕图片并保存
        @param  name: 保存的图片名称,通过getTakePicturePath方法获取保存全路径
        """
        path = ""
        try:
            if self._device_report_path is None:
                from xdevice import EnvPool
                self._device_report_path = EnvPool.report_path if EnvPool.generate_report else None
            if self._device_report_path is None:
                return False
            temp_path = os.path.join(self._device_report_path, "temp")
            if not os.path.exists(temp_path):
                os.makedirs(temp_path)
            path = os.path.join(temp_path, name)
            picture_name = os.path.basename(name)
            out = self.execute_shell_command(
                "snapshot_display -f {}/{} -i {}".format(self.tmp_path, picture_name, display_id))
            self.log.debug("result: {}".format(out))
            if "error" in out and "success" not in out:
                return False
            else:
                self.pull_file("{}/{}".format(self.tmp_path, picture_name), path)
        except Exception as error:
            self.log.error("devicetest take_picture: {}".format(str(error)))
        return path

    def capture(self, link: str, path: str, ext: str = ".png", display_id: int = 0) -> Tuple[str, str]:
        """
        截图步骤实现，未使用参数是保持一致
        :param link: 链接
        :param path: 保存路径
        :param ext: 后缀
        :return: link path 链接
        """

        new_ext = ".jpeg"
        link = link[:link.rfind(ext)] + new_ext
        path = path[:path.rfind(ext)] + new_ext


        remote = "{}/xdevice_screenshot{}".format(self.tmp_path, ext)
        remote = remote[:remote.rfind(ext)] + new_ext
        result = self.execute_shell_command("snapshot_display -f {} -i {}".format(remote, display_id), timeout=60000)
        LOG.debug("{}".format(result))
        # 适配非root
        if not self.is_root:
            time.sleep(1)
        self.pull_file(remote, path)
        self.execute_shell_command("rm -f {}".format(remote))
        return link, path

    def set_device_report_path(self, path):
        self._device_report_path = path

    def get_device_report_path(self):
        return self._device_report_path

    def get_device_params(self, refresh=True):
        """
        获取设备属性信息
        @return:
        """
        if refresh:
            for key, value in self.device_params_command.items():
                if value and isinstance(value, str):
                    self.device_params[key] = self.get_property_value(value)
            self.device_params[DeviceProperties.sn] = self.device_sn
            try:
                result = self.execute_shell_command(
                    "snapshot_display -f {}/screen.png".format(self.tmp_path))
                if "success" not in result or "successfully" not in result:
                    result = self.execute_shell_command(
                        "snapshot_display -f {}/screen.jpeg".format(self.tmp_path))
                pattern = re.search(r"width \d+. height \d+", result)
                resolution = re.findall(r"\d+", pattern.group())
                self.device_params[DeviceProperties.xres] = resolution[0]
                self.device_params[DeviceProperties.yres] = resolution[1]
            except Exception:
                pass
        return copy.deepcopy(self.device_params)

    def execute_shell_in_daemon(self, command):
        if self.host != "127.0.0.1":
            cmd = [HdcHelper.CONNECTOR_NAME, "-s", "{}:{}".format(
                self.host, self.port), "-t", self.device_sn, "shell"]
        else:
            cmd = [HdcHelper.CONNECTOR_NAME, "-t", self.device_sn, "shell"]
        LOG.debug("{} execute command {} {} in daemon".format(
            convert_serial(self.device_sn), HdcHelper.CONNECTOR_NAME, command))
        if isinstance(command, list):
            cmd.extend(command)
        else:
            command = command.strip()
            cmd.extend(command.split(" "))
        if platform.system() == "Darwin":
            # 执行spawn模式
            if isinstance(cmd, list):
                cmd = " ".join(cmd)
            unix_shell = '/bin/sh'
            cmd = [unix_shell, "-c"] + [cmd]
            close_fds = False
            preexec_fn = None
        elif platform.system() == "Windows":
            close_fds = True
            preexec_fn = None
        else:
            close_fds = True
            preexec_fn = os.setsid

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=False, close_fds=close_fds, preexec_fn=preexec_fn)
        return process

    def check_advance_option(self, extend_value, **kwargs):
        if not isinstance(extend_value, dict):
            return True

        advance_dict = extend_value.get(AdvanceDeviceOption.advance, None)
        if not isinstance(advance_dict, dict):
            return True
        # 匹配设备别名
        adv_alias = advance_dict.get(DeviceProperties.alias, "")
        adv_label = advance_dict.get(AdvanceDeviceOption.label, "")
        alias = (adv_alias or adv_label).strip().upper()
        if alias:
            is_matched = False
            selection = "selection:{alias:%s}" % alias
            # 兼容-di参数
            device_info = kwargs.get("device_info", None)
            if device_info and isinstance(device_info, list):
                di_alias = ""
                for info in device_info:
                    if not isinstance(info, dict) or info.get("sn", "") != self.device_sn:
                        continue
                    di_alias = info.get("type", "")
                    is_matched = di_alias == alias
                    break
                if not is_matched:
                    LOG.error("device:{sn:%s, alias:%s} mismatch %s, please check "
                              "the [-di] running params!" % (self.device_sn, di_alias, selection))
                    LOG.info("current [-di] running params is: %s" % device_info)
                    return False
                self.device_id = di_alias
            elif self.device_id == alias:
                is_matched = True
            if not is_matched:
                LOG.error("device:{sn:%s, alias:%s} mismatch %s" % (
                    self.device_sn, self.device_id, selection))
                return False

        # 匹配设备额外的信息
        advance_type = advance_dict.get(AdvanceDeviceOption.type, None)
        advance_product = advance_dict.get(AdvanceDeviceOption.product, None)
        advance_version = advance_dict.get(AdvanceDeviceOption.version, None)
        advance_product_cmd = advance_dict.get(AdvanceDeviceOption.product_cmd, None)
        advance_version_cmd = advance_dict.get(AdvanceDeviceOption.version_cmd, None)
        if advance_type and advance_type == AdvanceDeviceOption.command \
                and advance_product_cmd \
                and advance_version_cmd:
            if advance_product is not None:
                self.device_params[DeviceProperties.model] = \
                    self.execute_shell_command(advance_product_cmd).strip()
            if advance_version is not None:
                self.device_params[DeviceProperties.system_version] = \
                    self.execute_shell_command(advance_version_cmd).strip()
        else:
            if advance_product is not None:
                self.device_params[DeviceProperties.model] = \
                    self.get_property(self.device_params_command.get(DeviceProperties.model, ""))
            if advance_version is not None:
                self.device_params[DeviceProperties.system_version] = \
                    self.get_property(self.device_params_command.get(DeviceProperties.system_version, ""))

        if advance_product and advance_version:
            return True if advance_product == self.device_params.get(DeviceProperties.model, "") \
                           and advance_version == self.device_params.get(DeviceProperties.system_version, "") else False
        elif advance_product and advance_version is None:
            return True if advance_product == self.device_params.get(DeviceProperties.model, "") else False
        elif advance_product is None and advance_version:
            return True if advance_version == self.device_params.get(DeviceProperties.system_version, "") else False
        else:
            return True

    @property
    def webview(self):
        from devicetest.controllers.web.webview import WebView
        if self._webview is None:
            self._webview = WebView(self)
        return self._webview


class DeviceLogCollector:
    hilog_file_address = []
    log_file_address = []
    hdc_module_name = ""
    device = None
    restart_proc = []
    device_log_level = None
    is_clear = True
    device_hilog_proc = None
    need_pull_hdc_log = False  # 是否需要拉取hdc日志

    # log
    hilog_file_pipes = []
    device_log = dict()
    hilog = dict()
    log_proc = dict()
    hilog_proc = dict()

    _cur_thread_ident = None
    _cur_thread_name = None
    _hilog_begin_time = None
    _latest_pull_abnormal_log_time = time.time()

    def __init__(self, device):
        self.device = device

    def restart_catch_device_log(self):
        self._sync_device_time()
        for _, path in enumerate(self.hilog_file_address):
            hilog_open = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 FilePermission.mode_755)
            with os.fdopen(hilog_open, "a") as hilog_file_pipe:
                _, proc = self.start_catch_device_log(hilog_file_pipe=hilog_file_pipe)
                self.restart_proc.append(proc)

    def stop_restart_catch_device_log(self):
        # when device free stop restart log proc
        for _, proc in enumerate(self.restart_proc):
            self.stop_catch_device_log(proc)
        self.restart_proc.clear()
        self.hilog_file_address.clear()
        self.log_file_address.clear()

    def _set_device_log_level(self, **kwargs):
        # 设备日志级别
        if not self.device_log_level:
            log_level = kwargs.get("log_level", "INFO")
            if log_level not in LOGLEVEL:
                self.device_log_level = "INFO"
            else:
                self.device_log_level = log_level
        cmd = "hilog -b {}".format(self.device_log_level)
        self.device.execute_shell_command(cmd)

    def _set_hilog_begin_time(self):
        """设置日志抓取任务的开始时间"""
        cur_thread = threading.current_thread()
        cur_thread_id, cur_thread_name = cur_thread.ident, cur_thread.name
        if self._cur_thread_ident != cur_thread_id or self._cur_thread_name != cur_thread_name:
            # 用例连续运行，执行线程会变换，这时更新线程id和开始时间
            self._cur_thread_ident, self._cur_thread_name = cur_thread_id, cur_thread_name
            self._hilog_begin_time = time.time()

    def start_catch_device_log(self, log_file_pipe=None, hilog_file_pipe=None, **kwargs):
        """
        Starts hdc log for each device in separate subprocesses and save
        the logs in files.
        """
        self._sync_device_time()
        self._set_device_log_level(**kwargs)
        self._set_hilog_begin_time()

        device_hilog_proc = None
        if hilog_file_pipe:
            command = "hilog"
            if self.device.host != "127.0.0.1":
                cmd = [HdcHelper.CONNECTOR_NAME, "-s", "{}:{}".format(self.device.host, self.device.port),
                       "-t", self.device.device_sn, "shell", command]
            else:
                cmd = [HdcHelper.CONNECTOR_NAME, "-t", self.device.device_sn, "shell", command]
            LOG.info("execute command: %s" % " ".join(cmd).replace(
                self.device.device_sn, convert_serial(self.device.device_sn)))
            device_hilog_proc = start_standing_subprocess(
                cmd, hilog_file_pipe)
        self.device_hilog_proc = device_hilog_proc
        return None, device_hilog_proc

    def stop_catch_device_log(self, proc):
        """
        Stops all hdc log subprocesses.
        """
        if proc:
            self.device.log.debug("Stop catch device hilog.")
            stop_standing_subprocess(proc)
        if self.hdc_module_name:
            self.pull_hdc_log(self.hdc_module_name)
            self.hdc_module_name = None

    def start_hilog_task(self, **kwargs):
        """启动日志抓取任务。若设备没有在抓取日志，则设置启动抓取（不删除历史日志，以免影响其他组件运行）"""
        log_size = (kwargs.get("log_size") or "4M").upper()
        r = re.match(r'(\d+)([KM])$', log_size)
        if r:
            size, unit = int(r.group(1)), r.group(2)
            if size == 0:
                log_size = "4M"
            elif unit == "K" and size < 64:
                self.device.log.warning("invalid log size {}, it should be in range [64K, 512M], "
                                        "use the min value 64K".format(log_size))
                log_size = "64K"
            elif unit == "M" and size > 512:
                self.device.log.warning("invalid log size {}, it should be in range [64K, 512M], "
                                        "use the max value 512M".format(log_size))
                log_size = "512M"
        else:
            self.device.log.warning("invalid log size {}, it should be in range [64K, 512M], "
                                    "use the default value 4M".format(log_size))
            log_size = "4M"

        if re.search("^[0-9]+[K?]$", log_size) is None \
                and re.search("^[0-9]+[M?]$", log_size) is None:
            self.device.log.debug("hilog task Invalid size string {}. Use default 10M".format(log_size))
            log_size = "10M"
        matcher = re.match("^[0-9]+", log_size)
        if log_size.endswith("K") and int(matcher.group(0)) < 64:
            self.device.log.debug("hilog task file size should be "
                                  "in range [64.0K, 512.0M], use min value 64K, now is {}".format(log_size))
            log_size = "64K"
        if log_size.endswith("M") and int(matcher.group(0)) > 512:
            self.device.log.debug("hilog task file size should be "
                                  "in range [64.0K, 512.0M], use min value 512M, now is {}".format(log_size))
            log_size = "512M"

        self._sync_device_time()
        self._set_device_log_level(**kwargs)
        self._set_hilog_begin_time()

        # 启动日志任务
        out = self.device.execute_shell_command('hilog -w query')
        LOG.debug(out)
        cur_size = ''
        ret = re.search(r'/data/log/hilog/\S+ (\d+\.\d+)([KM]) 1000', out)
        if ret:
            cur_size = f'{int(float(ret.group(1)))}{ret.group(2)}'
        if 'No running persistent task' in out:
            # 启动hilog日志任务
            r = self.device.execute_shell_command('hilog -w start -l {} -n 1000'.format(log_size))
            LOG.debug(r)
            # 启动kmsg日志任务
            r = self.device.execute_shell_command('hilog -w start -t kmsg -l {} -n 100'.format(log_size))
            LOG.debug(r)
        elif cur_size != log_size:
            # 日志文件大小不一致，先停止日志任务，再重启hilog日志任务
            r = self.device.execute_shell_command('hilog -w stop')
            LOG.debug(r)
            time.sleep(2)
            r = self.device.execute_shell_command('hilog -w start -l {} -n 1000'.format(log_size))
            LOG.debug(r)
            # 启动kmsg日志任务
            r = self.device.execute_shell_command('hilog -w start -t kmsg -l {} -n 100'.format(log_size))
            LOG.debug(r)

    def stop_hilog_task(self, log_name, repeat=1, repeat_round=1, **kwargs):
        module_name = kwargs.get("module_name", "")
        round_folder = f"round{repeat_round}" if repeat > 1 else ""
        base_dir = os.path.join(self.device.get_device_report_path(), "log", round_folder)
        if module_name:
            path = os.path.join(base_dir, module_name)
        else:
            path = base_dir
        os.makedirs(path, exist_ok=True)

        # 获取hilog日志
        hilog_local = os.path.join(path, "hilog_{}".format(log_name))
        self.get_period_log({HILOG_PATH: ""}, hilog_local)
        # 拉取最新的字典文件。若hilog都没拉出来，字典文件也不用拉取了
        if os.path.exists(hilog_local):
            out = self.device.execute_shell_command('ls -t {} | grep hilog_dict'.format(HILOG_PATH))
            LOG.debug(out)
            log_dicts = out.strip().replace('\r', '').split('\n') if out else []
            if log_dicts:
                dict_file_name = log_dicts[0]
                self.device.pull_file(HILOG_PATH + '/' + dict_file_name, hilog_local, retry=0)
                self._parse_hilog(hilog_local, dict_file_name, **kwargs)
            else:
                LOG.warning("hilog_dict does not exist, and it won't be pulled")

        # 获取crash日志
        self.start_get_crash_log(log_name, repeat=repeat, repeat_round=repeat_round, module_name=module_name)
        # 获取额外路径的日志
        extras_dirs = kwargs.get("extras_dirs", "")
        self.pull_extra_log_files(log_name, module_name, extras_dirs, round_folder=round_folder)
        # 获取hdc日志
        self.pull_hdc_log(module_name, round_folder=round_folder)

    def pull_hdc_log(self, module_name, round_folder=""):
        if not self.need_pull_hdc_log:
            return
        report_path = self.device.get_device_report_path()
        if not report_path:
            return
        hdc_log_save_path = os.path.join(
            report_path, "log", round_folder, module_name, "hdc_log")
        if not os.path.exists(hdc_log_save_path):
            os.makedirs(hdc_log_save_path)
        temp_dir = tempfile.gettempdir()
        files = os.listdir(temp_dir)
        for file in files:
            if "hdc.log" in file or "hdclast.log" in file:
                hdc_log = os.path.join(temp_dir, file)
                shutil.copy(hdc_log, hdc_log_save_path)

    def start_get_crash_log(self, task_name, repeat=1, repeat_round=1, **kwargs):
        self._set_hilog_begin_time()
        module_name = kwargs.get("module_name", "")
        round_folder = f"round{repeat_round}" if repeat > 1 else ""
        base_dir = os.path.join(self.device.get_device_report_path(), "log", round_folder)
        crash_folder = f"crash_log_{task_name}"
        if module_name:
            crash_path = os.path.join(base_dir, module_name, crash_folder)
        else:
            crash_path = os.path.join(base_dir, crash_folder)

        crash_logs = {
            NATIVE_CRASH_PATH: ["cppcrash"],
            # JS_CRASH_PATH设为空，表示拉取这个路径下用例运行期间生成的文件
            JS_CRASH_PATH: [],
            ROOT_PATH: ["SERVICE_BLOCK", "appfreeze"]
        }
        remotes = {}
        for base_path, folders in crash_logs.items():
            for folder in folders:
                remote_dir = base_path + '/' + folder if folder else base_path
                remotes.update({remote_dir: ""})
            else:
                remotes.update({base_path: ""})
        self.get_period_log(remotes, crash_path)

    @staticmethod
    def _parse_hilog(log_path, dict_file_name, **kwargs):
        dict_file = os.path.join(log_path, dict_file_name)
        enable1 = kwargs.get('parse_hilog', 'false').lower() == 'true'
        enable2 = Variables.config.devicelog.get('parse_hilog', 'false').lower() == 'true'
        # 解析hilog
        if not os.path.exists(dict_file) or not (enable1 or enable2):
            return
        if not shutil.which('hilogtool'):
            LOG.warning("because the hilogtool command is unavailable, the log cannot be parsed")
            return
        cmd = f'hilogtool parse -d {dict_file_name}'
        LOG.debug(f'parse hilog files. command: {cmd}')
        if platform.system() != "Windows":
            cmd = shlex.split(cmd)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=log_path)
        out, _ = proc.communicate()
        out = out.decode()
        LOG.debug(out)
        ret = re.search(r'Result: successNum: \d+, failNum: (\d+)', out)
        fail_num = int(ret.group(1))
        if fail_num > 0:
            return
        LOG.debug('remove the local original hilog, dicts files')
        try:
            for file_name in os.listdir(log_path):
                if file_name.startswith('hilog.') and file_name.endswith('.gz'):
                    os.remove(os.path.join(log_path, file_name))
            os.remove(dict_file)
            dict_folder_path = os.path.join(log_path, 'dict')
            if os.path.exists(dict_folder_path):
                shutil.rmtree(dict_folder_path)
        except Exception as e:
            LOG.warning(f'remove the local original hilog, dicts files failed. {e}')

    def _sync_device_time(self):
        # 先同步PC和设备的时间
        iso_time_format = '%Y-%m-%d %H:%M:%S'
        cur_time = get_cst_time().strftime(iso_time_format)
        self.device.execute_shell_command("date '{}'".format(cur_time))

    def add_log_address(self, log_file_address, hilog_file_address):
        # record to restart catch log when reboot device
        if log_file_address:
            self.log_file_address.append(log_file_address)
        if hilog_file_address:
            self.hilog_file_address.append(hilog_file_address)
            self.hdc_module_name = os.path.basename(os.path.dirname(hilog_file_address))

    def remove_log_address(self, log_file_address, hilog_file_address):
        if log_file_address and log_file_address in self.log_file_address:
            self.log_file_address.remove(log_file_address)
        if hilog_file_address and hilog_file_address in self.hilog_file_address:
            self.hilog_file_address.remove(hilog_file_address)

    def pull_extra_log_files(self, task_name: str, module_name: str, dirs: str, round_folder: str = ""):
        if not dirs or dirs == 'None':
            return
        extra_log_path = os.path.join(
            self.device.get_device_report_path(), "log", round_folder,
            module_name, "extra_log_{}".format(task_name))
        remotes = {}
        for item in dirs.split(';'):
            item = item.strip().rstrip('/')
            if not item:
                continue
            # 若是文件夹，则保存在本地的同名文件夹内
            on_folder = os.path.basename(item) if self.device.is_directory(item) else ""
            remotes.update({item: on_folder})
        self.get_period_log(remotes, extra_log_path)

    def clear_kingking_dir_log(self):
        def execute_clear_cmd(path: str, prefix: list):
            for pre in prefix:
                clear_cmd = "rm -f {}/{}/*".format(path, pre)
                self.device.execute_shell_command(clear_cmd)

        execute_clear_cmd(KINGKONG_PATH, ["data", "fault_route", "screenshots"])

    def get_period_log(self, remotes: dict, local_path: str, begin_time: float = None, find_cmd: str = None):
        """在目录下查找一段时间内有更改的文件，并将文件拉到本地
        remotes: dict, {查找目录: 使用子文件夹存放文件（通常不用子文件夹）}
        local_path: str, pull to local path
        begin_time: float, the beginning time
        """
        begin = begin_time if begin_time else self._hilog_begin_time
        if not begin:
            LOG.warning('hilog task begin time is not set')
            return
        minutes, seconds = divmod(int(time.time() - begin), 60)
        if minutes < 0:
            LOG.warning('get logs in a period failed!')
            LOG.warning('当前日志打印的时间先与开始抓取日志的时间')
            return
        if minutes > 0:
            units = '%dm' % (minutes + 1)
        else:
            units = '%ds' % seconds

        for remote_dir, on_folder in remotes.items():
            find = find_cmd if find_cmd else 'find {}'.format(remote_dir)
            cmd = '{} -type f -mtime -{}'.format(find, units)
            out = self.device.execute_shell_command(cmd)
            if 'No such file or directory' in out:
                continue
            LOG.debug(out)
            log_files = [f for f in out.strip().replace('\r', '').split('\n') if f and f.startswith(remote_dir)]
            if not log_files:
                continue
            local_dir = os.path.join(local_path, on_folder) if on_folder else local_path
            os.makedirs(local_dir, exist_ok=True)
            os.chmod(local_dir, FilePermission.mode_755)
            for log_file in log_files:
                # 避免将整个文件夹拉下来和重复拉取文件
                if '.persisterInfo' in log_file \
                        or 'hilog_diag.log' in log_file \
                        or log_file == remote_dir and self.device.is_directory(log_file) \
                        or os.path.exists(log_file) and os.path.isfile(log_file):
                    continue
                self.device.pull_file(log_file, local_dir, retry=0)

    def start_catch_log(self, request, **kwargs):
        hilog_size = kwargs.get("hilog_size", "10M")
        log_level = request.config.device_log.get(ConfigConst.tag_loglevel, "INFO")
        pull_hdc_log_status = request.config.device_log.get(ConfigConst.tag_hdc, None)
        self.need_pull_hdc_log = False if pull_hdc_log_status and pull_hdc_log_status.lower() == "false" else True
        self.device.set_device_report_path(request.config.report_path)
        self.start_hilog_task(log_size=hilog_size, log_level=log_level)

    def stop_catch_log(self, request, **kwargs):
        self.remove_log_address(self.device_log.get(self.device.device_sn, None),
                                self.hilog.get(self.device.device_sn, None))
        serial = "{}_{}".format(str(self.device.__get_serial__()), time.time_ns())
        log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
        self.stop_hilog_task(
            log_tar_file_name,
            module_name=request.get_module_name(),
            extras_dirs=request.config.device_log.get(ConfigConst.tag_dir),
            repeat=request.config.repeat,
            repeat_round=request.get_repeat_round())
