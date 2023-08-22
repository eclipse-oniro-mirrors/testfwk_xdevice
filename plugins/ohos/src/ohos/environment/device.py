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
import time
import os
import threading
import platform
import subprocess
import sys
from xdevice import DeviceOsType, FilePermission
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
from xdevice import get_cst_time

from ohos.environment.dmlib import HdcHelper
from ohos.environment.dmlib import CollectingOutputReceiver

__all__ = ["Device"]
TIMEOUT = 300 * 1000
RETRY_ATTEMPTS = 2
DEFAULT_UNAVAILABLE_TIMEOUT = 20 * 1000
BACKGROUND_TIME = 2 * 60 * 1000
LOG = platform_logger("Device")
DEVICETEST_HAP_PACKAGE_NAME = "com.ohos.devicetest"
UITEST_NAME = "uitest"
UITEST_SINGLENESS = "singleness"
UITEST_PATH = "/system/bin/uitest"
UITEST_SHMF = "/data/app/el2/100/base/{}/cache/shmf".format(DEVICETEST_HAP_PACKAGE_NAME)
UITEST_COMMAND = "{} start-daemon 0123456789 &".format(UITEST_PATH)
NATIVE_CRASH_PATH = "/data/log/faultlog/temp"
JS_CRASH_PATH = "/data/log/faultlog/faultlogger"
ROOT_PATH = "/data/log/faultlog"


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
    label = None
    log = platform_logger("Device")
    device_state_monitor = None
    reboot_timeout = 2 * 60 * 1000
    _device_log_collector = None

    _proxy = None
    _abc_proxy = None
    _is_abc = False
    initdevice = True
    d_port = 8011
    abc_d_port = 8012
    _uitestdeamon = None
    rpc_timeout = 300
    device_id = None
    reconnecttimes = 0
    _h_port = None
    oh_module_package = None
    module_ablity_name = None
    _device_report_path = None
    _webview = None

    model_dict = {
        'default': ProductForm.phone,
        'car': ProductForm.car,
        'tv': ProductForm.television,
        'watch': ProductForm.watch,
        'tablet': ProductForm.tablet,
        'nosdcard': ProductForm.phone
    }

    def __init__(self):
        self.extend_value = {}
        self.device_lock = threading.RLock()
        self.forward_ports = []
        self.forward_ports_abc = []
        self.proxy_listener = None

    def __eq__(self, other):
        return self.device_sn == other.__get_serial__() and \
               self.device_os_type == other.device_os_type

    def __set_serial__(self, device_sn=""):
        self.device_sn = device_sn
        return self.device_sn

    def __get_serial__(self):
        return self.device_sn

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

        result = self.device_state_monitor.wait_for_device_available()
        if result:
            self.device_log_collector.restart_catch_device_log()
        return result

    def get_device_type(self):
        self.label = self.model_dict.get("default", None)

    def get_property(self, prop_name, retry=RETRY_ATTEMPTS,
                     abort_on_exception=False):
        """
        Hdc command, ddmlib function.
        """
        command = "param get %s" % prop_name
        stdout = self.execute_shell_command(command, timeout=5 * 1000,
                                            output_flag=False,
                                            retry=retry,
                                            abort_on_exception=abort_on_exception).strip()
        if stdout:
            LOG.debug(stdout)
        return stdout

    @perform_device_action
    def connector_command(self, command, **kwargs):
        timeout = int(kwargs.get("timeout", TIMEOUT)) / 1000
        error_print = bool(kwargs.get("error_print", True))
        join_result = bool(kwargs.get("join_result", False))
        timeout_msg = '' if timeout == 300.0 else \
            " with timeout %ss" % timeout
        if self.host != "127.0.0.1":
            cmd = [HdcHelper.CONNECTOR_NAME, "-s", "{}:{}".format(self.host, self.port),
                   "-t", self.device_sn]
        else:
            cmd = [HdcHelper.CONNECTOR_NAME, "-t", self.device_sn]
        LOG.debug("{} execute command {} {}{}".format(convert_serial(self.device_sn),
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
        self.wait_for_boot_completion()

    def _reboot_until_online(self):
        self._do_reboot()

    def reboot(self):
        self._reboot_until_online()
        self.enable_hdc_root()
        self.device_log_collector.restart_catch_device_log()

    @perform_device_action
    def install_package(self, package_path, command=""):
        if package_path is None:
            raise HdcError(
                "install package: package path cannot be None!")
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
            raise HdcError("XDevice Local path cannot be None!")

        remote_is_dir = kwargs.get("remote_is_dir", False)
        if remote_is_dir:
            ret = self.execute_shell_command("test -d %s && echo 0" % remote)
            if not (ret != "" and len(str(ret).split()) != 0 and
                    str(ret).split()[0] == "0"):
                self.execute_shell_command("mkdir -p %s" % remote)

        if self.host != "127.0.0.1":
            self.connector_command("file send {} {}".format(local, remote))
        else:
            is_create = kwargs.get("is_create", False)
            timeout = kwargs.get("timeout", TIMEOUT)
            HdcHelper.push_file(self, local, remote, is_create=is_create,
                                timeout=timeout)
        if not self.is_file_exist(remote):
            LOG.error("Push %s to %s failed" % (local, remote))
            raise HdcError("push %s to %s failed" % (local, remote))

    @perform_device_action
    def pull_file(self, remote, local, **kwargs):
        """
        Pull a single file.
        The top directory won't be created if is_create is False (by default)
        and vice versa
        """
        local = "\"{}\"".format(local)
        remote = "\"{}\"".format(remote)
        if self.host != "127.0.0.1":
            self.connector_command("file recv {} {}".format(remote, local))
        else:
            is_create = kwargs.get("is_create", False)
            timeout = kwargs.get("timeout", TIMEOUT)
            HdcHelper.pull_file(self, remote, local, is_create=is_create,
                                timeout=timeout)

    def enable_hdc_root(self):
        return True

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
        if stdout:
            if "fail" in stdout:
                cmd = [HdcHelper.CONNECTOR_NAME, "list", "targets"]

                stdout = exec_cmd(cmd)
                LOG.debug("exec cmd list targets:{},current device_sn:{}".format(stdout, self.device_sn))
                if stdout and (self.device_sn in stdout):
                    stdout = "true"
            LOG.debug(stdout)
        return stdout

    def set_recover_state(self, state):
        with self.device_lock:
            setattr(self, ConfigConst.recover_state, state)
            if not state:
                self.test_device_state = TestDeviceState.NOT_AVAILABLE
                self.device_allocation_state = DeviceAllocationState.unavailable
                # do proxy clean
                if self.proxy_listener is not None:
                    if self._abc_proxy or (not self.is_abc and self.proxy):
                        self.proxy_listener(is_exception=True)

    def get_recover_state(self, default_state=True):
        with self.device_lock:
            state = getattr(self, ConfigConst.recover_state, default_state)
            return state

    def close(self):
        self.reconnecttimes = 0

    def reset(self):
        self.log.debug("start reset device...")
        if self._proxy is not None:
            self._proxy.close()
        self._proxy = None
        if self._uitestdeamon is not None:
            self._uitestdeamon = None
        if self.is_abc:
            self.stop_harmony_rpc(kill_all=False)
        else:
            self.remove_ports()
            self.stop_harmony_rpc(kill_all=True)
            # do proxy clean
            if self.proxy_listener is not None:
                self.proxy_listener(is_exception=False)
        self.device_log_collector.stop_restart_catch_device_log()

    @property
    def is_abc(self):
        # _is_abc init in device test driver
        return self._is_abc

    @property
    def proxy(self):
        """The first rpc session initiated on this device. None if there isn't
        one.
        """
        try:
            if self._proxy is None:
                # check uitest
                self.check_uitest_status()
                self._proxy = self.get_harmony()
        except Exception as error:
            self._proxy = None
            self.log.error("DeviceTest-10012 proxy:%s" % str(error))
        return self._proxy

    @property
    def abc_proxy(self):
        """The first rpc session initiated on this device. None if there isn't
        one.
        """
        try:
            if self._abc_proxy is None:
                # check uitest
                self.check_uitest_status()
                self._abc_proxy = self.get_harmony(start_abc=True)
        except Exception as error:
            self._abc_proxy = None
            self.log.error("DeviceTest-10012 abc_proxy:%s" % str(error))
        return self._abc_proxy

    @property
    def uitestdeamon(self):
        from devicetest.controllers.uitestdeamon import \
            UiTestDeamon
        if self._uitestdeamon is None:
            self._uitestdeamon = UiTestDeamon(self)
        return self._uitestdeamon

    @classmethod
    def set_module_package(cls, module_packag):
        cls.oh_module_package = module_packag

    @classmethod
    def set_moudle_ablity_name(cls, module_ablity_name):
        cls.module_ablity_name = module_ablity_name

    @property
    def is_oh(self):
        return True

    def get_harmony(self, start_abc=False):
        if self.initdevice:
            if start_abc:
                self.start_abc_rpc(re_install_rpc=True)
            else:
                self.start_harmony_rpc(re_install_rpc=True)
        self._h_port = self.get_local_port(start_abc)
        port = self.d_port if not start_abc else self.abc_d_port
        # clear old port,because abc and fast mode will not remove port
        cmd = "fport tcp:{} tcp:{}".format(
            self._h_port, port)
        self.connector_command(cmd)
        self.log.info(
            "get_proxy d_port:{} {}".format(self._h_port, port))
        rpc_proxy = None
        try:
            from devicetest.controllers.openharmony import OpenHarmony
            rpc_proxy = OpenHarmony(port=self._h_port, addr=self.host, device=self)
        except Exception as error:
            self.log.error(' proxy init error: {}.'.format(str(error)))
        return rpc_proxy

    def start_uitest(self):
        result = ""
        if self.is_abc:
            result = self.execute_shell_command("{} start-daemon singleness &".format(UITEST_PATH))
        else:
            share_mem_mode = False
            # uitest基础版本号，比该版本号大的用共享内存的方式进行启动
            base_version = [3, 2, 2, 2]
            uitest_version = self.execute_shell_command("{} --version".format(UITEST_PATH))
            if uitest_version and re.match(r'^\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}', uitest_version):
                uitest_version = uitest_version.split(".")
                for index, _ in enumerate(uitest_version):
                    if int(uitest_version[index]) > base_version[index]:
                        share_mem_mode = True
                        break
            if share_mem_mode:
                if not self.is_file_exist(UITEST_SHMF):
                    self.log.debug('Path {} not exist, create it.'.format(UITEST_SHMF))
                    self.execute_shell_command("echo abc > {}".format(UITEST_SHMF))
                    self.execute_shell_command("chmod -R 666 {}".format(UITEST_SHMF))
                result = self.execute_shell_command("{} start-daemon {} &".format(UITEST_PATH, UITEST_SHMF))
            else:
                result = self.execute_shell_command(UITEST_COMMAND)
        self.log.debug('start uitest, {}'.format(result))

    def start_harmony_rpc(self, re_install_rpc=False):
        if self.check_rpc_status(check_abc=False):
            if (hasattr(sys, ConfigConst.env_pool_cache) and
                getattr(sys, ConfigConst.env_pool_cache, False)) \
                    or not re_install_rpc:
                self.log.debug('Harmony rpc already start!!!!')
                return
        from devicetest.core.error_message import ErrorMessage
        if re_install_rpc:
            try:
                from devicetest.controllers.openharmony import OpenHarmony
                OpenHarmony.install_harmony_rpc(self)
            except ImportError as error:  # pylint:disable=undefined-variable
                self.log.debug(str(error))
                self.log.error('please check devicetest extension module is exist.')
                raise Exception(ErrorMessage.Error_01437.Topic)
            except Exception as error:
                self.log.debug(str(error))
                self.log.error('root device init RPC error.')
                raise Exception(ErrorMessage.Error_01437.Topic)
        if not self.is_abc:
            self.stop_harmony_rpc()
        else:
            self.log.debug('Abc mode, kill hap if hap is running.')
            self.stop_harmony_rpc(kill_all=False)
        cmd = "aa start -a {}.ServiceAbility -b {}".format(DEVICETEST_HAP_PACKAGE_NAME, DEVICETEST_HAP_PACKAGE_NAME)
        result = self.execute_shell_command(cmd)
        self.log.debug('start devicetest ability, {}'.format(result))
        if not self.is_abc:
            self.start_uitest()
        time.sleep(1)
        if not self.check_rpc_status(check_abc=False):
            raise Exception("harmony rpc not running")

    def start_abc_rpc(self, re_install_rpc=False):
        if re_install_rpc:
            try:
                from devicetest.controllers.openharmony import OpenHarmony
                OpenHarmony.init_abc_resource(self)
            except ImportError as error:  # pylint:disable=undefined-variable
                self.log.debug(str(error))
                self.log.error('please check devicetest extension module is exist.')
                raise error
            except Exception as error:
                self.log.debug(str(error))
                self.log.error('root device init abc RPC error.')
                raise error
        if self.is_abc and self.check_rpc_status(check_abc=True):
            self.log.debug('Harmony abc rpc already start!!!!')
            return
        self.start_uitest()
        time.sleep(1)
        if not self.check_rpc_status(check_abc=True):
            raise Exception("harmony abc rpc not running")

    def stop_harmony_rpc(self, kill_all=True):
        # abc妯″紡涓嬩粎鏉€鎺塪evicetest锛屽惁鍒欓兘鏉€鎺?
        proc_pids = self.get_devicetest_proc_pid()
        if not kill_all:
            proc_pids.pop()
        for pid in proc_pids:
            if pid != "":
                cmd = 'kill {}'.format(pid)
                self.execute_shell_command(cmd)

    # check uitest if running well, otherwise kill it first
    def check_uitest_status(self):
        self.log.debug('Check uitest running status.')
        proc_pids = self.get_devicetest_proc_pid(print_info=False)
        if self.is_abc and proc_pids[1] != "":
            if proc_pids[0] != "":
                self.execute_shell_command('kill {}'.format(proc_pids[0]))
            self.execute_shell_command('kill {}'.format(proc_pids[1]))
            self.log.debug('Uitest is running in normal mode, current mode is abc, wait it exit.')
        if not self.is_abc and proc_pids[2] != "":
            if proc_pids[0] != "":
                self.execute_shell_command('kill {}'.format(proc_pids[0]))
            self.execute_shell_command('kill {}'.format(proc_pids[2]))
            self.log.debug('Uitest is running in abc mode, current mode is normal, wait it exit.')
        self.log.debug('Finish check uitest running status.')

    def get_devicetest_proc_pid(self, print_info=True):
        uitest = "{} start-daemon".format(UITEST_NAME)
        cmd = 'ps -ef | grep -E \'{}|{}|{}\''.format(DEVICETEST_HAP_PACKAGE_NAME, UITEST_NAME, UITEST_SINGLENESS)
        proc_running = self.execute_shell_command(cmd).strip()
        proc_running = proc_running.split("\n")
        proc_pids = [""] * 3
        result = []
        for data in proc_running:
            if DEVICETEST_HAP_PACKAGE_NAME in data and "grep" not in data and UITEST_NAME not in data:
                result.append("{} running status: {}".format(DEVICETEST_HAP_PACKAGE_NAME, data))
                data = data.split()
                proc_pids[0] = data[1]
            if uitest in data and "grep" not in data:
                if UITEST_SINGLENESS in data:
                    result.append("{} running status: {}".format(UITEST_SINGLENESS, data))
                    data = data.split()
                    proc_pids[2] = data[1]
                else:
                    result.append("{} running status: {}".format(UITEST_NAME, data))
                    data = data.split()
                    proc_pids[1] = data[1]
        if print_info:
            self.log.debug("\n".join(result))
        return proc_pids

    def is_harmony_rpc_running(self, check_abc=False):
        proc_pids = self.get_devicetest_proc_pid(print_info=False)
        if not self.is_abc:
            self.log.debug('is_proc_running: agent pid: {}, uitest pid: {}'.format(proc_pids[0], proc_pids[1]))
            if proc_pids[0] != "" and proc_pids[1] != "":
                return True
        else:
            if check_abc:
                self.log.debug('is_proc_running: uitest pid: {}'.format(proc_pids[2]))
                if proc_pids[2] != "":
                    return True
            else:
                self.log.debug('is_proc_running: agent pid: {}'.format(proc_pids[0]))
                if proc_pids[0] != "":
                    return True
        return False

    def is_harmony_rpc_socket_running(self, port, check_server=True):
        out = self.execute_shell_command("netstat -anp | grep {}".format(port))
        self.log.debug(out)
        if out:
            out = out.split("\n")
            for data in out:
                if check_server:
                    if "LISTEN" in data and str(port) in data:
                        return True
                else:
                    if "hdcd" in data and str(port) in data:
                        return True
        return False

    def check_rpc_status(self, check_abc=False, check_server=True):
        port = self.d_port if not check_abc else self.abc_d_port
        if self.is_harmony_rpc_running(check_abc) and \
                self.is_harmony_rpc_socket_running(port, check_server=check_server):
            self.log.debug('Harmony rpc is running!!!! If is check abc: {}'.format(check_abc))
            return True
        self.log.debug('Harmony rpc is not running!!!! If is check abc: {}'.format(check_abc))
        return False

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

    def reconnect(self, waittime=60):
        '''
        @summary: Reconnect the device.
        '''
        if not self.wait_for_boot_completion():
            raise Exception("Reconnect timed out.")
        if self._proxy:
            self.start_harmony_rpc(re_install_rpc=True)
            self._h_port = self.get_local_port(start_abc=False)
            cmd = "fport tcp:{} tcp:{}".format(
                self._h_port, self.d_port)
            self.connector_command(cmd)
            try:
                self._proxy.init(port=self._h_port, addr=self.host, device=self)
            except Exception as _:
                time.sleep(3)
                self._proxy.init(port=self._h_port, addr=self.host, device=self)
            # do proxy clean
            if not self.is_abc and self.proxy_listener is not None:
                self.proxy_listener(is_exception=True)
        if self.is_abc and self._abc_proxy:
            self.start_abc_rpc(re_install_rpc=True)
            self._h_port = self.get_local_port(start_abc=True)
            cmd = "fport tcp:{} tcp:{}".format(
                self._h_port, self.abc_d_port)
            self.connector_command(cmd)
            try:
                self._abc_proxy.init(port=self._h_port, addr=self.host, device=self)
            except Exception as _:
                time.sleep(3)
                self._abc_proxy.init(port=self._h_port, addr=self.host, device=self)
            # do proxt clean
            if self.proxy_listener is not None:
                self.proxy_listener(is_exception=True)

        if self._uitestdeamon is not None:
            self._uitestdeamon.init(self)

        if self._proxy:
            return self._proxy
        return None

    def wait_for_boot_completion(self):
        """Waits for the device to boot up.

        Returns:
            True if the device successfully finished booting, False otherwise.
        """
        return self.device_state_monitor.wait_for_device_available(self.reboot_timeout)

    def get_local_port(self, start_abc):
        from devicetest.utils.util import get_forward_port
        host = self.host
        port = None
        h_port = get_forward_port(self, host, port)
        if start_abc:
            self.forward_ports_abc.append(h_port)
        else:
            self.forward_ports.append(h_port)
        self.log.info("tcp forward port: {} for {}".format(
            h_port, convert_serial(self.device_sn)))
        return h_port

    def remove_ports(self):
        for port in self.forward_ports:
            cmd = "fport rm tcp:{} tcp:{}".format(
                port, self.d_port)
            self.connector_command(cmd)
        for port in self.forward_ports_abc:
            cmd = "fport rm tcp:{} tcp:{}".format(
                port, self.abc_d_port)
            self.connector_command(cmd)
        self.forward_ports.clear()
        self.forward_ports_abc.clear()

    def remove_history_ports(self, port):
        cmd = "fport ls"
        res = self.connector_command(cmd, is_print=False)
        res = res.split("\n")
        for data in res:
            if str(port) in data:
                data = data.split('\t')
                cmd = "fport rm {}".format(data[0][1:-1])
                self.connector_command(cmd, is_print=False)

    @classmethod
    def check_recover_result(cls, recover_result):
        return "true" in recover_result

    def take_picture(self, name):
        '''
        @summary: 截取手机屏幕图片并保存
        @param  name: 保存的图片名称,通过getTakePicturePath方法获取保存全路径
        '''
        path = ""
        try:
            if self._device_report_path is None:
                from xdevice import EnvPool
                self._device_report_path = EnvPool.report_path
            temp_path = os.path.join(self._device_report_path, "temp")
            if not os.path.exists(temp_path):
                os.makedirs(temp_path)
            path = os.path.join(temp_path, name)
            picture_name = os.path.basename(name)
            out = self.execute_shell_command("snapshot_display -f /data/local/tmp/{}".format(picture_name))
            self.log.debug("result: {}".format(out))
            if "error" in out and "success" not in out:
                return False
            else:
                self.pull_file("/data/local/tmp/{}".format(picture_name), path)
        except Exception as error:
            self.log.error("devicetest take_picture: {}".format(str(error)))
        return path

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
        sys_type = platform.system()
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   shell=False,
                                   preexec_fn=None if sys_type == "Windows"
                                   else os.setsid,
                                   close_fds=True)
        return process

    @property
    def webview(self):
        from devicetest.controllers.web.webview import WebView
        if self._webview is None:
            self._webview = WebView(self)
        return self._webview

    @property
    def device_log_collector(self):
        if self._device_log_collector is None:
            self._device_log_collector = DeviceLogCollector(self)
        return self._device_log_collector

    def set_device_report_path(self, path):
        self._device_log_path = path

    def get_device_report_path(self):
        return self._device_log_path


class DeviceLogCollector:
    hilog_file_address = []
    log_file_address = []
    device = None
    restart_proc = []

    def __init__(self, device):
        self.device = device

    def restart_catch_device_log(self):
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

    def start_catch_device_log(self, log_file_pipe=None,
                               hilog_file_pipe=None):
        """
        Starts hdc log for each device in separate subprocesses and save
        the logs in files.
        """
        self._sync_device_time()
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
        return None, device_hilog_proc

    def stop_catch_device_log(self, proc):
        """
        Stops all hdc log subprocesses.
        """
        if proc:
            stop_standing_subprocess(proc)
            self.device.log.debug("Stop catch device hilog.")

    def start_hilog_task(self, log_size="10M"):
        log_size = log_size.upper()
        if re.search("^\d+[K?]$", log_size) is None \
                and re.search("^\d+[M?]$", log_size) is None:
            self.device.log.debug("hilog task Invalid size string {}. Use default 10M".format(log_size))
            log_size = "10M"
        matcher = re.match("^\d+", log_size)
        if log_size.endswith("K") and int(matcher.group(0)) < 64:
            self.device.log.debug("hilog task file size should be "
                                  "in range [64.0K, 512.0M], use min value 64K, now is {}".format(log_size))
            log_size = "64K"
        if log_size.endswith("M") and int(matcher.group(0)) > 512:
            self.device.log.debug("hilog task file size should be "
                                  "in range [64.0K, 512.0M], use min value 512M, now is {}".format(log_size))
            log_size = "512M"

        self._sync_device_time()
        self.clear_crash_log()
        # 先停止一下
        cmd = "hilog -w stop"
        self.device.execute_shell_command(cmd)
        # 清空日志
        cmd = "hilog -r"
        self.device.execute_shell_command(cmd)
        cmd = "rm -rf /data/log/hilog/*.gz"
        self.device.execute_shell_command(cmd)
        # 开始日志任务 设置落盘文件个数最大值1000, 单个文件20M，链接https://gitee.com/openharmony/hiviewdfx_hilog
        cmd = "hilog -w start -l {} -n 1000".format(log_size)
        out = self.device.execute_shell_command(cmd)
        LOG.info("Execute command: {}, result is {}".format(cmd, out))

    def stop_hilog_task(self, log_name, **kwargs):
        cmd = "hilog -w stop"
        out = self.device.execute_shell_command(cmd)
        module_name = kwargs.get("module_name", None)
        if module_name:
            path = "{}/log/{}".format(self.device.get_device_report_path(), module_name)
        else:
            path = "{}/log/".format(self.device.get_device_report_path())
        self.device.pull_file("/data/log/hilog/", path)
        # HDC不支持创建绝对路径，拉取文件夹出来后重命名文件夹
        try:
            new_hilog_dir = "{}/log/{}/hilog_{}".format(self.device.get_device_report_path(), module_name, log_name)
            os.rename("{}/log/{}/hilog".format(self.device.get_device_report_path(), module_name), new_hilog_dir)
            # 拉出来的文件夹权限可能是650，更改为755，解决在线日志浏览报403问题
            os.chmod(new_hilog_dir, FilePermission.mode_755)
        except Exception as e:
            self.device.log.warning("Rename hilog folder {}_hilog failed. error: {}".format(log_name, e))
            # 把hilog文件夹下所有文件拉出来 由于hdc不支持整个文件夹拉出只能采用先压缩再拉取文件
            cmd = "cd /data/log/hilog && tar -zcvf /data/log/{}_hilog.tar.gz *".format(log_name)
            out = self.device.execute_shell_command(cmd)
            LOG.info("Execute command: {}, result is {}".format(cmd, out))
            if out is not None and "No space left on device" not in out:
                self.device.pull_file("/data/log/{}_hilog.tar.gz".format(log_name), path)
                cmd = "rm -rf /data/log/{}_hilog.tar.gz".format(log_name)
                self.device.execute_shell_command(cmd)
        # 获取crash日志
        self.start_get_crash_log(log_name, module_name)
        # 获取额外路径的日志
        self.pull_extra_log_files(log_name, module_name, kwargs.get("extras_dirs", None))

    def _get_log(self, log_cmd, *params):
        def filter_by_name(log_name, args):
            for starts_name in args:
                if log_name.startswith(starts_name):
                    return True
            return False

        data_list = list()
        log_name_array = list()
        log_result = self.device.execute_shell_command(log_cmd)
        if log_result is not None and len(log_result) != 0:
            log_name_array = log_result.strip().replace("\r", "").split("\n")
        for log_name in log_name_array:
            log_name = log_name.strip()
            if len(params) == 0 or \
                    filter_by_name(log_name, params):
                data_list.append(log_name)
        return data_list

    def get_cur_crash_log(self, crash_path, log_name):
        log_name_map = {'cppcrash': NATIVE_CRASH_PATH,
                        "jscrash": JS_CRASH_PATH,
                        "SERVICE_BLOCK": ROOT_PATH,
                        "appfreeze": ROOT_PATH}
        if not os.path.exists(crash_path):
            os.makedirs(crash_path)
        if "Not support std mode" in log_name:
            return

        def get_log_path(logname):
            name_array = logname.split("-")
            if len(name_array) <= 1:
                return ROOT_PATH
            return log_name_map.get(name_array[0])

        log_path = get_log_path(log_name)
        temp_path = "%s/%s" % (log_path, log_name)
        self.device.pull_file(temp_path, crash_path)
        LOG.debug("Finish pull file: %s" % log_name)

    def start_get_crash_log(self, task_name, **kwargs):
        module_name = kwargs.get("module_name", None)
        log_array = list()
        native_crash_cmd = "ls {}".format(NATIVE_CRASH_PATH)
        js_crash_cmd = '"ls {} | grep jscrash"'.format(JS_CRASH_PATH)
        block_crash_cmd = '"ls {}"'.format(ROOT_PATH)
        # 获取crash日志文件
        log_array.extend(self._get_log(native_crash_cmd, "cppcrash"))
        log_array.extend(self._get_log(js_crash_cmd, "jscrash"))
        log_array.extend(self._get_log(block_crash_cmd, "SERVICE_BLOCK", "appfreeze"))
        LOG.debug("crash log file {}, length is {}".format(str(log_array), str(len(log_array))))
        if module_name:
            crash_path = "{}/log/{}/{}_crash_log/".format(self.device.get_device_report_path(), module_name, task_name)
        else:
            crash_path = "{}/log/crash_log_{}/".format(self.device.get_device_report_path(), task_name)
        for log_name in log_array:
            log_name = log_name.strip()
            self.get_cur_crash_log(crash_path, log_name)

    def clear_crash_log(self):
        clear_block_crash_cmd = "rm -f {}/*".format(ROOT_PATH)
        clear_native_crash_cmd = "rm -f {}/*".format(NATIVE_CRASH_PATH)
        clear_debug_crash_cmd = "rm -f {}/debug/*".format(ROOT_PATH)
        clear_js_crash_cmd = "rm -f {}/*".format(JS_CRASH_PATH)
        self.device.execute_shell_command(clear_block_crash_cmd)
        self.device.execute_shell_command(clear_native_crash_cmd)
        self.device.execute_shell_command(clear_debug_crash_cmd)
        self.device.execute_shell_command(clear_js_crash_cmd)

    def _sync_device_time(self):
        # 先同步PC和设备的时间
        iso_time_format = '%Y-%m-%d %H:%M:%S'
        cur_time = get_cst_time().strftime(iso_time_format)
        self.device.execute_shell_command("date '{}'".format(cur_time))
        self.device.execute_shell_command("hwclock --systohc")

    def add_log_address(self, log_file_address, hilog_file_address):
        # record to restart catch log when reboot device
        if log_file_address:
            self.log_file_address.append(log_file_address)
        if hilog_file_address:
            self.hilog_file_address.append(hilog_file_address)

    def remove_log_address(self, log_file_address, hilog_file_address):
        if log_file_address and log_file_address in self.log_file_address:
            self.log_file_address.remove(log_file_address)
        if hilog_file_address and hilog_file_address in self.hilog_file_address:
            self.hilog_file_address.remove(hilog_file_address)

    def pull_extra_log_files(self, task_name, module_name, dirs: str):
        if dirs is None:
            return
        dir_list = dirs.split(";")
        if len(dir_list) > 0:
            extra_log_path = "{}/log/{}/extra_log_{}/".format(self.device.get_device_report_path(),
                                                              module_name, task_name)
            if not os.path.exists(extra_log_path):
                os.makedirs(extra_log_path)
            for dir_path in dir_list:
                self.device.pull_file(dir_path, extra_log_path)
