#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2026 Huawei Device Co., Ltd.
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

__all__ = ["JSunitLiteDriver"]

import os
import re
import time
import shutil
import threading

from ohos.drivers import (
    Binder, DeviceTestType, ExecuteTerminate, FilePermission,
    IDriver, JsonParser, Plugin, check_result_report,
    get_config_value, get_device_log_file, get_kit_instances,
    platform_logger, ShellHandler, get_plugin,
)
from ohos.constants import DeviceLiteKernel, ParserType
from ohos.drivers.constants import init_remote_server, get_nfs_server
from ohos.error import ErrorMessage

LOG = platform_logger("JSunitLiteDriver")

ANSI_PATTERN = re.compile(r'\x1B(\[([0-9]{1,2}(;[0-9]{1,2})*)?m)*')


def _get_device_ip(nfs_server_ip):
    parts = nfs_server_ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".254"
    return ""


def _clean_serial_data(raw):
    data = raw.decode('gbk', errors='ignore')
    return ANSI_PATTERN.sub('', data).replace("\r", "")


def _drain_serial_buffer(com_obj, serial_buffer, stop_flag):
    try:
        com = _get_serial_port(com_obj)
        if not com:
            return
        _poll_serial_loop(com, serial_buffer, stop_flag)
    except Exception:
        pass


def _get_serial_port(com_obj):
    if not com_obj or not com_obj.com:
        return None
    return com_obj.com


def _poll_serial_loop(com, serial_buffer, stop_flag):
    while not stop_flag[0]:
        if com.in_waiting > 0:
            _read_one_batch(com, serial_buffer)
        else:
            time.sleep(0.01)


def _read_one_batch(com, serial_buffer):
    if com.in_waiting <= 0:
        return
    data = _clean_serial_data(com.read(com.in_waiting))
    if data:
        serial_buffer[0] = "{}{}".format(serial_buffer[0], data)
        for line in data.split("\n"):
            line = line.strip()
            if line and ("[pass]" in line or "[fail]" in line or "[ignore]" in line
                         or "[suite start]" in line or "[suite end]" in line
                         or "[end] run suites end" in line or "[start] start run suites" in line
                         or "[Console Error]" in line or "appspawn" in line
                         or "Ability" in line or "bm install" in line.lower()):
                LOG.info("[serial] %s" % line)


def _read_remaining_serial(com_obj):
    try:
        if com_obj and com_obj.com and com_obj.com.in_waiting > 0:
            return _clean_serial_data(com_obj.com.read(com_obj.com.in_waiting))
        return ""
    except Exception:
        return ""


def _drain_serial_before_command(device):
    try:
        com_obj = device.device.com_dict.get("cmd")
        if not com_obj or not com_obj.com:
            return
        drain_count = 0
        while com_obj.com.in_waiting > 0 and drain_count < 10:
            com_obj.com.read(com_obj.com.in_waiting)
            time.sleep(0.3)
            drain_count += 1
    except Exception:
        pass


def _collect_serial_after_command(device, delay=2):
    try:
        com_obj = device.device.com_dict.get("cmd")
        if not com_obj or not com_obj.com:
            return ""
        time.sleep(delay)
        extra = ""
        read_count = 0
        while read_count < 5:
            if com_obj.com.in_waiting > 0:
                extra += _clean_serial_data(com_obj.com.read(com_obj.com.in_waiting))
                time.sleep(0.5)
                read_count += 1
            else:
                break
        return extra
    except Exception:
        return ""


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.jsunit_test_lite)
class JSunitLiteDriver(IDriver):
    config = None
    result = ""
    error_message = ""

    def __init__(self):
        self.file_name = ""
        self.kernel = None

    def __check_environment__(self, device_options):
        return len(device_options) == 1

    def __check_config__(self, config=None):
        pass

    def __execute__(self, request):
        device_log_file = get_device_log_file(
            request.config.report_path,
            request.get_devices()[0].__get_serial__(),
            repeat=request.config.repeat,
            repeat_round=request.get_repeat_round())
        try:
            self.config = request.config
            self.config.device = request.config.environment.devices[0]
            init_remote_server(self, request=request)
            config_file = request.root.source.config_file
            json_config = JsonParser(config_file)
            self._get_driver_config(json_config)

            kits = get_kit_instances(json_config,
                                     request.config.resource_path,
                                     request.config.testcases_path)

            self._setup_network(request)

            for kit in kits:
                if not Binder.is_executing():
                    raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
                if hasattr(kit, 'type_kernel') and not kit.type_kernel:
                    kit.type_kernel = self._detect_kernel(self.config.device)
                kit.__setup__(self.config.device, request=request)

            self._setup_device(request)
            self._run_jsunit_lite_test(request)

        except Exception as exception:
            LOG.exception(exception, exc_info=False)
            self.error_message = exception
        finally:
            self._write_device_log(device_log_file)
            for kit in kits:
                try:
                    kit.__teardown__(self.config.device)
                except Exception:
                    pass
            self.config.device.close()

        self.result = check_result_report(
            request.config.report_path, self.result,
            self.error_message, request=request)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""

    @staticmethod
    def _copy_aa_local(aa_local, aa_dst):
        if os.path.exists(aa_dst):
            os.chmod(aa_dst, 0o755)
            os.remove(aa_dst)
        shutil.copy2(aa_local, aa_dst)
        os.chmod(aa_dst, 0o755)

    @staticmethod
    def _copy_aa_remote(nfs_info, aa_local, aa_dst):
        import paramiko
        client = paramiko.Transport((nfs_info.get("ip", ""),
                                     int(nfs_info.get("port", "22"))))
        client.connect(username=nfs_info.get("username"),
                       password=nfs_info.get("password"))
        sftp = paramiko.SFTPClient.from_transport(client)
        sftp.put(localpath=aa_local, remotepath=aa_dst)
        client.close()

    @staticmethod
    def _find_local_aa(request):
        candidates = [
            os.path.join(request.config.testcases_path, "tools", "aa"),
            os.path.join(request.config.testcases_path, "aa"),
            os.path.join(request.config.testcases_path, "..", "..", "dev_tools", "bin", "aa"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    @staticmethod
    def _get_reboot_cmd(kernel):
        if kernel == DeviceLiteKernel.linux_kernel:
            return "reboot"
        return "reset"

    @staticmethod
    def _get_storage_prefix(kernel):
        return "/storage" if kernel == DeviceLiteKernel.linux_kernel else ""

    @staticmethod
    def _is_file_present(ls_result, ls_status):
        return (ls_status and "No such file" not in ls_result
                and "Error" not in ls_result
                and ls_result.strip()
                and "ls or" not in ls_result)

    def _detect_kernel(self, device):
        kernel = device.__get_device_kernel__()
        if kernel:
            LOG.info("Device kernel type: %s" % kernel)
            return kernel
        env_result, status, _ = device.execute_command_with_timeout(
            command="uname", timeout=3)
        if not status:
            LOG.info("Device kernel type: linux (default, uname failed)")
            return DeviceLiteKernel.linux_kernel
        if "linux" in env_result.lower():
            device.__set_device_kernel__(DeviceLiteKernel.linux_kernel)
            LOG.info("Device kernel type: linux (detected via uname)")
            return DeviceLiteKernel.linux_kernel
        device.__set_device_kernel__(DeviceLiteKernel.lite_kernel)
        LOG.info("Device kernel type: lite (detected via uname)")
        return DeviceLiteKernel.lite_kernel

    def _get_driver_config(self, json_config):
        setattr(self.config, "command_result", "")
        self.bundle_name = get_config_value(
            'bundle-name', json_config.get_driver(), False)
        timeout_config = get_config_value(
            'timeout', json_config.get_driver(), False)
        self.timeout = int(timeout_config) // 1000 if timeout_config else 600
        ability_name_cfg = get_config_value(
            'ability-name', json_config.get_driver(), False)
        self.ability_name = ability_name_cfg or "MainAbility"
        self.hap_file = get_config_value(
            'hap-file-name', json_config.get_driver(), False)
        self.preset_dir = "/system/internal"
        self.reboot_timeout = 120
        cleanup_config = get_config_value(
            'cleanup', json_config.get_driver(), False)
        self.cleanup_after = cleanup_config.lower() != 'false' if cleanup_config else True
        reboot_config = get_config_value(
            'reboot-after-cleanup', json_config.get_driver(), False)
        self.reboot_after = reboot_config.lower() != 'false' if reboot_config else True

    def _install_hap(self, device, kernel, storage_prefix, request):
        if not self.hap_file:
            return True
        hap_dir = "%s/test_root" % storage_prefix
        local_hap_path = os.path.join(request.config.testcases_path,
                                      "jsunit_lite_test", self.hap_file)
        expected_size = os.path.getsize(local_hap_path) if os.path.exists(local_hap_path) else 0
        LOG.info("Expected HAP size: %d bytes" % expected_size)

        bm_path = "/storage/bm"
        use_bm = (kernel == DeviceLiteKernel.linux_kernel)
        if use_bm:
            bm_check, _, _ = device.execute_command_with_timeout(
                command="ls %s" % bm_path, timeout=3)
            use_bm = (bm_check and "No such file" not in bm_check
                     and bm_check.strip())
        if use_bm:
            LOG.info("Using bm install to install HAP")
            hap_remote = "%s/test_root/%s" % (storage_prefix, self.hap_file)
            _drain_serial_before_command(device)
            install_result, install_status, _ = device.execute_command_with_timeout(
                command="/storage/bm install -p %s" % hap_remote, timeout=60)
            extra = _collect_serial_after_command(device, delay=2)
            if extra:
                install_result = str(install_result) + extra
            LOG.info("bm install result: %s" % str(install_result)[:200])
            if install_status and "success" in str(install_result).lower() and "install" in str(install_result).lower():
                LOG.info("HAP installed via bm, skip reboot")
                self.reboot_after = False
                return True
            LOG.warning("bm install failed, falling back to cp method")

        if not self._cp_install_hap(device, hap_dir):
            return False

        LOG.info("Cleaning old install data: rm -r /storage/app/etc/bundles")
        device.execute_command_with_timeout(
            command="rm -r /storage/app/etc/bundles", timeout=10)
        return True

    def _cp_install_hap(self, device, hap_dir):
        LOG.info("Copying HAP from %s/%s to %s/%s" % (hap_dir, self.hap_file, self.preset_dir, self.hap_file))
        for retry in range(3):
            LOG.info("HAP copy attempt %d" % (retry + 1))
            device.execute_command_with_timeout(
                command="cp %s/%s %s/" % (hap_dir, self.hap_file, self.preset_dir),
                timeout=60)
            time.sleep(5)
            ls_result, ls_status, _ = device.execute_command_with_timeout(
                command="ls %s/%s" % (self.preset_dir, self.hap_file), timeout=5)
            LOG.info("HAP ls result: %s" % str(ls_result)[:200])
            if ls_status and self.hap_file in ls_result and "No such file" not in ls_result:
                LOG.info("HAP copy verified")
                return True
            LOG.warning("HAP copy attempt %d not verified, retrying..." % (retry + 1))
            time.sleep(2)
        LOG.error("HAP copy failed after 3 retries, aborting install")
        return False

    def _launch_app(self, device, handler=None):
        aa_path = "/storage/aa"
        aa_check, aa_status, _ = device.execute_command_with_timeout(
            command="ls %s" % aa_path, timeout=3)
        has_aa = (aa_check and "No such file" not in aa_check
                  and "ls or" not in aa_check and aa_check.strip())
        if not has_aa:
            LOG.warning("ability assistant not found on device, skipping launch")
            return ""

        device.execute_command_with_timeout(command="cd /storage", timeout=1)
        command = "./aa start -p %s -n %s" % (self.bundle_name, self.ability_name)
        LOG.info("Launch jsunit_lite test: %s" % command)

        if handler:
            result, _, _ = device.execute_command_with_timeout(
                command=command,
                case_type=DeviceTestType.jsunit_test_lite,
                receiver=handler,
                timeout=self.timeout)
            return result or ""

        result = ""
        for retry in range(3):
            try:
                result, _, _ = device.execute_command_with_timeout(
                    command=command,
                    case_type=DeviceTestType.jsunit_test_lite,
                    timeout=3)
                if result:
                    LOG.info("ability assistant start result: %s" % str(result)[:200])
                    break
                LOG.warning("ability assistant start attempt %d returned empty result, retrying..." % (retry + 1))
            except Exception:
                LOG.warning("ability assistant start attempt %d failed, retrying..." % (retry + 1))
                result = ""
            if retry < 2:
                time.sleep(5)
        return result

    def _collect_serial_output(self, initial_result, timeout):
        serial_buffer = [initial_result]
        stop_reading = [False]

        com_obj = self.config.device.device.com_dict.get("cmd")
        reader = threading.Thread(
            target=_drain_serial_buffer,
            args=(com_obj, serial_buffer, stop_reading),
            daemon=True)
        reader.start()

        end_marker = "[end] run suites end"
        elapsed = 0
        interval = 1
        while elapsed < timeout:
            if end_marker in serial_buffer[0]:
                LOG.info("Test completed, end marker found")
                break
            time.sleep(interval)
            elapsed += interval

        stop_reading[0] = True
        reader.join(timeout=3)

        time.sleep(1)
        remaining = _read_remaining_serial(com_obj)
        if remaining:
            serial_buffer[0] = "{}{}".format(serial_buffer[0], remaining)

        return serial_buffer[0]

    def _copy_aa_to_device(self, device, storage_prefix):
        aa_src = "%s/test_root/aa" % storage_prefix
        aa_dst = "/storage/aa"
        LOG.info("Copying ability assistant from %s to %s" % (aa_src, aa_dst))
        device.execute_command_with_timeout(
            command="mkdir -p /storage", timeout=3)
        for retry in range(3):
            device.execute_command_with_timeout(
                command="cp %s %s" % (aa_src, aa_dst), timeout=5)
            ls_result, ls_status, _ = device.execute_command_with_timeout(
                command="ls %s" % aa_dst, timeout=3)
            if self._is_file_present(ls_result, ls_status):
                LOG.info("ability assistant copied OK: %s" % ls_result.strip())
                device.execute_command_with_timeout(
                    command="chmod +x %s" % aa_dst, timeout=3)
                break
            LOG.warning("ability assistant copy attempt %d failed, retrying..." % (retry + 1))
            time.sleep(2)
        else:
            LOG.warning("ability assistant not found at %s after 3 retries." % aa_dst)

        bm_src = "%s/test_root/bm" % storage_prefix
        bm_dst = "/storage/bm"
        LOG.info("Copying bm from %s to %s" % (bm_src, bm_dst))
        for retry in range(3):
            device.execute_command_with_timeout(
                command="cp %s %s" % (bm_src, bm_dst), timeout=5)
            ls_result, ls_status, _ = device.execute_command_with_timeout(
                command="ls %s" % bm_dst, timeout=3)
            if self._is_file_present(ls_result, ls_status):
                LOG.info("bm copied OK: %s" % ls_result.strip())
                device.execute_command_with_timeout(
                    command="chmod +x %s" % bm_dst, timeout=3)
                return
            LOG.warning("bm copy attempt %d failed, retrying..." % (retry + 1))
            time.sleep(2)
        LOG.warning("bm not found at %s after 3 retries." % bm_src)

    def _copy_aa_to_nfs(self, request):
        nfs_info = get_nfs_server(request)
        if not nfs_info:
            return
        nfs_dir = nfs_info.get("dir", "")
        if not nfs_dir:
            return

        aa_local = self._find_local_aa(request)
        if not aa_local:
            LOG.warning("ability assistant not found in testcases/tools/ or dev_tools/bin/")
        else:
            aa_dst = os.path.join(nfs_dir, "aa")
            is_remote = nfs_info.get("remote", "false")
            try:
                if is_remote.lower() == "true":
                    self._copy_aa_remote(nfs_info, aa_local, aa_dst)
                else:
                    self._copy_aa_local(aa_local, aa_dst)
                LOG.info("ability assistant copied to NFS: %s -> %s" % (aa_local, aa_dst))
            except Exception as e:
                LOG.error("Failed to copy ability assistant to NFS: %s" % str(e))

        tools_dir = os.path.join(request.config.testcases_path, "tools")
        bm_local = os.path.join(tools_dir, "bm")
        if not os.path.isfile(bm_local):
            bm_local = os.path.join(request.config.testcases_path,
                                    "jsunit_lite_test", "tools", "bm")
        if os.path.isfile(bm_local):
            bm_dst = os.path.join(nfs_dir, "bm")
            is_remote = nfs_info.get("remote", "false")
            try:
                if is_remote.lower() == "true":
                    self._copy_aa_remote(nfs_info, bm_local, bm_dst)
                else:
                    self._copy_aa_local(bm_local, bm_dst)
                LOG.info("bm copied to NFS: %s -> %s" % (bm_local, bm_dst))
            except Exception as e:
                LOG.error("Failed to copy bm to NFS: %s" % str(e))
        else:
            LOG.warning("bm not found in testcases/tools/")

    def _reboot_and_reconnect(self, device, kernel, request):
        LOG.info("Rebooting device...")
        device.execute_command_with_timeout(self._get_reboot_cmd(kernel), timeout=5)
        reconnected = False
        for i in range(self.reboot_timeout // 5):
            time.sleep(5)
            try:
                device.close()
                device.connect()
                result, status, _ = device.execute_command_with_timeout(
                    command="ls", timeout=3)
                if status and result:
                    LOG.info("Device reconnected after %ds" % ((i + 1) * 5))
                    time.sleep(5)
                    reconnected = True
                    break
            except Exception:
                continue
        if not reconnected:
            LOG.error("Device did not come back within %ds" % self.reboot_timeout)
            return

        self._reconfigure_network(device, kernel, request)
        storage_prefix = self._get_storage_prefix(kernel)
        self._copy_aa_to_device(device, storage_prefix)
        LOG.info("Waiting for device to fully boot...")
        time.sleep(15)

    def _reconfigure_network(self, device, kernel, request):
        nfs_info = get_nfs_server(request)
        if not nfs_info:
            return
        nfs_server_ip = nfs_info.get("ip", "")
        device_ip = _get_device_ip(nfs_server_ip) if nfs_server_ip else ""
        if not device_ip:
            return
        LOG.info("Re-configuring device network after reboot: ifconfig eth0 %s" % device_ip)
        device.execute_command_with_timeout(
            command="ifconfig eth0 %s" % device_ip, timeout=5)
        if kernel == DeviceLiteKernel.linux_kernel:
            device.execute_command_with_timeout(
                command="echo 0 100 > /proc/sys/net/ipv4/ping_group_range",
                timeout=1)

    def _suppress_kernel_log(self, device):
        try:
            device.execute_command_with_timeout(
                command="echo 1 > /proc/sys/kernel/printk", timeout=3)
            LOG.info("Kernel log level lowered")
        except Exception:
            pass

    def _run_jsunit_lite_test(self, request):
        self.file_name = request.root.source.test_name.split(".")[0]
        LOG.info("file_name: %s" % self.file_name)
        self.result = "%s.xml" % os.path.join(
            request.config.report_path, "result", self.file_name)

        device = self.config.device
        self.kernel = self._detect_kernel(device)

        self._suppress_kernel_log(device)

        parsers = get_plugin(Plugin.PARSER, ParserType.jsuit_test_lite)
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = self.file_name
            parser_instance.listeners = request.listeners
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)

        LOG.info("Running jsunit_lite test with parser, timeout=%ds" % self.timeout)

        # Write aa start command directly to serial, then collect output
        command = "./aa start -p %s -n %s" % (self.bundle_name, self.ability_name)
        LOG.info("Launch jsunit_lite test: %s" % command)

        com_obj = self.config.device.device.com_dict.get("cmd")
        if com_obj and com_obj.com:
            com_obj.com.write(b"cd /storage\r\n")
            time.sleep(0.5)
            _drain_serial_before_command(self.config.device)
            com_obj.com.write((command + "\r\n").encode("ascii"))
            time.sleep(1)
            initial = ""
            if com_obj.com.in_waiting > 0:
                initial = _clean_serial_data(com_obj.com.read(com_obj.com.in_waiting))
            result = self._collect_serial_output(initial, self.timeout)
            if handler:
                handler.__read__(result)
        else:
            LOG.warning("Serial port not available, falling back to execute_command")
            result = self._launch_app(device, handler=handler)

        self.config.command_result = result if result else ""
        LOG.info("Test execution completed")

        # Drain serial buffer and reset shell state before teardown
        try:
            com_obj = self.config.device.device.com_dict.get("cmd")
            if com_obj and com_obj.com:
                time.sleep(0.5)
                if com_obj.com.in_waiting > 0:
                    com_obj.com.read(com_obj.com.in_waiting)
                com_obj.com.write(b"cd /\r\n")
                time.sleep(0.5)
                if com_obj.com.in_waiting > 0:
                    com_obj.com.read(com_obj.com.in_waiting)
        except Exception:
            pass

        self._teardown_device(request)

    def _setup_device(self, request):
        device = self.config.device
        device.connect()
        self.kernel = self._detect_kernel(device)
        storage_prefix = self._get_storage_prefix(self.kernel)

        self._copy_aa_to_nfs(request)
        self._copy_aa_to_device(device, storage_prefix)
        hap_installed = self._install_hap(device, self.kernel, storage_prefix, request)

        if hap_installed and self.reboot_after:
            self._reboot_and_reconnect(device, self.kernel, request)

    def _setup_network(self, request):
        device = self.config.device
        device.connect()
        self.kernel = self._detect_kernel(device)

        nfs_info = get_nfs_server(request)
        if not nfs_info:
            return
        nfs_server_ip = nfs_info.get("ip", "")
        device_ip = _get_device_ip(nfs_server_ip) if nfs_server_ip else ""
        if not device_ip:
            return

        LOG.info("Setting up device network: ifconfig eth0 %s" % device_ip)
        device.execute_command_with_timeout(
            command="ifconfig eth0 %s" % device_ip, timeout=5)
        if self.kernel == DeviceLiteKernel.linux_kernel:
            device.execute_command_with_timeout(
                command="echo 0 100 > /proc/sys/net/ipv4/ping_group_range",
                timeout=1)
        self._device_ip = device_ip

    def _teardown_device(self, request):
        if not self.hap_file or not self.cleanup_after:
            return
        device = self.config.device

        try:
            device.connect()
            kernel = device.__get_device_kernel__() or DeviceLiteKernel.linux_kernel

            bm_path = "/storage/bm"
            use_bm = (kernel == DeviceLiteKernel.linux_kernel)
            if use_bm:
                bm_check, _, _ = device.execute_command_with_timeout(
                    command="ls %s" % bm_path, timeout=3)
                use_bm = (bm_check and "No such file" not in bm_check
                         and bm_check.strip())
            if use_bm:
                self._cleanup_with_bm(device, kernel)
                return

            LOG.info("Cleanup: rm %s/%s" % (self.preset_dir, self.hap_file))
            device.execute_command_with_timeout("cd /", timeout=1)
            device.execute_command_with_timeout(
                command="rm %s/%s" % (self.preset_dir, self.hap_file), timeout=5)
            LOG.info("Cleanup: rm -r /storage/app/etc/bundles")
            device.execute_command_with_timeout(
                command="rm -r /storage/app/etc/bundles", timeout=10)
            LOG.info("Cleanup: rebooting for uninstall to take effect")
            device.execute_command_with_timeout(self._get_reboot_cmd(kernel), timeout=5)
        except Exception as e:
            LOG.warning("Teardown error: %s" % str(e))

    def _reconnect_device(self, device):
        for i in range(self.reboot_timeout // 5):
            time.sleep(5)
            try:
                device.close()
                device.connect()
                result, status, _ = device.execute_command_with_timeout(
                    command="ls", timeout=3)
                if status and result:
                    LOG.info("Device reconnected after %ds" % ((i + 1) * 5))
                    time.sleep(5)
                    return
            except Exception:
                continue

    def _cleanup_with_bm(self, device, kernel):
        # Kill app process first - app.terminate() may not fully stop it
        LOG.info("Cleanup: killing app process")
        device.execute_command_with_timeout(
            command="killall %s" % self.bundle_name.replace(".", "_"), timeout=5)
        time.sleep(2)
        # Also try removing the run directory to force cleanup
        device.execute_command_with_timeout(
            command="rm -rf /storage/app/run/%s" % self.bundle_name, timeout=5)
        time.sleep(1)
        LOG.info("Cleanup: bm uninstall %s" % self.bundle_name)
        _drain_serial_before_command(device)
        uninstall_result, uninstall_status, _ = device.execute_command_with_timeout(
            command="/storage/bm uninstall -n %s" % self.bundle_name, timeout=30)
        extra = _collect_serial_after_command(device, delay=2)
        if extra:
            uninstall_result = str(uninstall_result) + extra
        LOG.info("Cleanup: bm uninstall result: %s" % str(uninstall_result)[:200])
        if uninstall_status and "success" in str(uninstall_result).lower():
            LOG.info("Cleanup: bm uninstall success")
        else:
            LOG.warning("Cleanup: bm uninstall failed, doing manual cleanup")
            device.execute_command_with_timeout(
                command="rm -f %s/%s" % (self.preset_dir, self.hap_file), timeout=5)
            device.execute_command_with_timeout(
                command="rm -rf /storage/app/etc/bundles", timeout=10)
            device.execute_command_with_timeout(
                command="rm -rf /storage/app/run/%s" % self.bundle_name, timeout=5)
            LOG.info("Cleanup: manual cleanup done, rebooting for uninstall to take effect")
            device.execute_command_with_timeout(
                self._get_reboot_cmd(kernel), timeout=5)
            self._reconnect_device(device)
            return
        if self.reboot_after:
            LOG.info("Cleanup: rebooting to clear screen")
        device.execute_command_with_timeout(
            self._get_reboot_cmd(kernel), timeout=5)
        self._reconnect_device(device)
        return

    def _write_device_log(self, device_log_file):
        device_log_file_open = os.open(
            device_log_file,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            FilePermission.mode_755)
        with os.fdopen(device_log_file_open, "a") as f:
            f.write(getattr(self.config, "command_result", "") or "")
            f.flush()
