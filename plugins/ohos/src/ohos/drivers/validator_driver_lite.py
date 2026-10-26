#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2024 Huawei Device Co., Ltd.
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

__all__ = ["ValidatorLiteDriver"]

import os
import re
import time
import shutil
import threading
import hashlib
from xml.etree import ElementTree as ET

from ohos.drivers import (
    Binder, DeviceTestType, ExecuteTerminate, FilePermission,
    IDriver, JsonParser, Plugin, check_result_report,
    get_config_value, get_device_log_file, get_kit_instances,
    platform_logger,
)
from ohos.constants import DeviceLiteKernel
from ohos.drivers.constants import init_remote_server, get_nfs_server
from ohos.error import ErrorMessage

LOG = platform_logger("ValidatorLiteDriver")

REPORT_PATTERN = re.compile(r"\[report\]\s+(\S+)\s+(\S+)(?:\s+(.+))?")
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


def _read_remaining_serial(com_obj):
    try:
        if com_obj and com_obj.com and com_obj.com.in_waiting > 0:
            return _clean_serial_data(com_obj.com.read(com_obj.com.in_waiting))
        return ""
    except Exception:
        return ""




def _drain_serial_before_command(device):
    try:
        com_obj = device.device.com_dict.get('cmd')
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
        com_obj = device.device.com_dict.get('cmd')
        if not com_obj or not com_obj.com:
            return ''
        time.sleep(delay)
        extra = ''
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
        return ''


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.validator_lite)
class ValidatorLiteDriver(IDriver):
    config = None
    result = ""
    error_message = ""

    def __init__(self):
        self.file_name = ""

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
        kits = []
        try:
            self.config = request.config
            self.config.device = request.config.environment.devices[0]
            self.transfer_mode = self._resolve_transfer_mode(request)
            LOG.info("Transfer mode: %s" % self.transfer_mode)
            if self.transfer_mode == "nfs":
                init_remote_server(self, request=request)
            config_file = request.root.source.config_file
            json_config = JsonParser(config_file)
            self._get_driver_config(json_config)

            kits = get_kit_instances(json_config,
                                     request.config.resource_path,
                                     request.config.testcases_path)

            is_update = self._check_update_testarg()

            if self.transfer_mode == "nfs":
                self._setup_network(request)

            for kit in kits:
                if not Binder.is_executing():
                    raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
                if self.transfer_mode == "serial" and hasattr(kit, 'mount_list'):
                    if hasattr(kit, 'type_kernel') and kit.type_kernel:
                        self.config.device.__set_device_kernel__(kit.type_kernel)
                        LOG.info("Kernel type from Test.json: %s" % kit.type_kernel)
                    continue
                if hasattr(kit, 'type_kernel') and not kit.type_kernel:
                    kit.type_kernel = self._detect_kernel(self.config.device)
                kit.__setup__(self.config.device, request=request)

            if is_update:
                if self.transfer_mode == "nfs":
                    self._setup_device(request)
                else:
                    self._serial_deploy(request)
            self._is_update = is_update
            self._run_validator_test(request)

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

    def _resolve_transfer_mode(self, request):
        try:
            nfs_info = get_nfs_server(request)
            if nfs_info and nfs_info.get("ip"):
                remote = str(nfs_info.get("remote", "")).lower()
                self._nfs_dir = None if remote == "true" else nfs_info.get("dir")
                return "nfs"
        except Exception:
            pass
        return "serial"

    def _serial_hap_name(self):
        stem = os.path.splitext(self.hap_file or "test.hap")[0]
        cleaned = re.sub(r'[^A-Za-z0-9]', '', stem).lower()[:8] or "test"
        return "%s.hap" % cleaned

    def _device_sha3(self, path):
        for _ in range(3):
            try:
                _drain_serial_before_command(self.config.device)
                out, _, _ = self.config.device.execute_command_with_timeout(
                    command="/bin/toybox sha3sum %s" % path, timeout=8)
                m = re.search(r'\b([0-9a-f]{56})\b', str(out))
                if m:
                    return m.group(1)
            except Exception:
                pass
        return None

    def _serial_deploy(self, request):
        from ohos.drivers.serial_deploy_lite import SerialDeployer
        device = self.config.device
        device.connect()

        aa_path = self._find_local_aa(request)
        bm_path = os.path.join(request.config.testcases_path, "tools", "bm")
        if not os.path.isfile(bm_path):
            bm_path = os.path.join(request.config.testcases_path,
                                   "acts_validator_lite", "tools", "bm")
        hap_path = os.path.join(request.config.testcases_path,
                                "acts_validator_lite", self.hap_file)
        sources = [("aa", aa_path), ("bm", bm_path),
                   (self._serial_hap_name(), hap_path)]
        files = []
        for name, path in sources:
            if not path or not os.path.isfile(path):
                raise RuntimeError("serial deploy: local file missing: %s" % path)
            with open(path, "rb") as handle:
                files.append((name, handle.read()))

        # Determine kernel BEFORE any serial commands (from json/cache)
        kernel = self._detect_kernel(device)
        kernel_str = "linux" if kernel == DeviceLiteKernel.linux_kernel else "liteos"

        if kernel_str == "linux":
            # Linux: skip pre-check (console noise makes sha3 unreliable)
            need = files
        else:
            need = []
            for name, data in files:
                want = hashlib.sha3_224(data).hexdigest()
                if self._device_sha3("/storage/%s" % name) != want:
                    need.append((name, data))
                else:
                    LOG.info("serial deploy: %s already up to date" % name)
            if not need:
                LOG.info("serial deploy: all files up to date, skip U-Boot phase")

        if need:
            com_obj = device.device.com_dict.get("cmd")
            if not com_obj or not com_obj.com:
                raise RuntimeError("serial deploy: cmd serial port unavailable")
            deployer = SerialDeployer(com_obj.com, logger=LOG.info)
            deployer.deploy(need, kernel=kernel_str)
            # close deployer port and reconnect device (deployer may have
            # closed/reopened the serial during U-Boot entry)
            try:
                if deployer.com and deployer.com.is_open:
                    deployer.com.close()
            except Exception:
                pass
            try:
                device.close()
                device.connect()
                LOG.info("serial deploy: device reconnected after deploy")
            except Exception:
                LOG.warning("serial deploy: device reconnect issue")

            # Reboot after deploy for clean shell (files already on /storage)
            if kernel_str == "linux":
                LOG.info("serial deploy: rebooting before install")
                try:
                    _drain_serial_before_command(device)
                    device.execute_command_with_timeout(
                        command="reboot", timeout=5)
                except Exception:
                    pass
                time.sleep(30)
                try:
                    device.close()
                    device.connect()
                except Exception:
                    pass
                for _ in range(18):
                    time.sleep(5)
                    try:
                        result, status, _ = device.execute_command_with_timeout(
                            command="echo ok", timeout=5)
                        if status and "ok" in str(result):
                            LOG.info("serial deploy: shell ready after reboot")
                            break
                    except Exception:
                        continue

        LOG.info("serial deploy: waiting for system to settle")
        time.sleep(10)
        try:
            com_obj = device.device.com_dict.get("cmd")
            if com_obj and com_obj.com and com_obj.com.in_waiting:
                com_obj.com.read(com_obj.com.in_waiting)
        except Exception:
            pass

        for name, data in need:
            want = hashlib.sha3_224(data).hexdigest()
            got = self._device_sha3("/storage/%s" % name)
            if got == want:
                LOG.info("serial deploy: %s OS sha3 match" % name)
            else:
                LOG.info("serial deploy: %s OS sha3 unreadable, flash crc32 "
                         "already verified in U-Boot" % name)
        LOG.info("serial deploy: %d file(s) deployed and verified" % len(need))

        kernel = self._detect_kernel(device)
        storage_prefix = self._get_storage_prefix(kernel)
        if not self._install_hap(device, kernel, storage_prefix, request):
            raise RuntimeError("serial deploy: hap install failed")
        if self.reboot_after:
            LOG.info("serial deploy: rebooting after install")
            device.execute_command_with_timeout(self._get_reboot_cmd(kernel), timeout=5)
            self._reconnect_device(device)

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
    def _copy_aa_local(aa_local, aa_dst):
        if os.path.exists(aa_dst):
            os.chmod(aa_dst, 0o755)
            os.remove(aa_dst)
        shutil.copy(aa_local, aa_dst)
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
    def _detect_kernel(device):
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

    @staticmethod
    def _print_manual_prompt():
        print("=" * 60)
        print("Please manually launch the Validator app on the device.")
        print("Tap the app icon to start testing.")
        print("After finishing all tests, tap 'Generate Report'.")
        print("=" * 60)

    @staticmethod
    def _wait_for_user_confirmation():
        LOG.info("Waiting for operator to finish manual testing on device...")
        while True:
            print("Is test finished? Y/N")
            usr_input = input(">>>> ")
            if usr_input in ("Y", "y"):
                LOG.debug("Finish current test")
                break
            print("continue")
            LOG.debug("Your input is:{}, continue".format(usr_input))

    def _append_testcase(self, suite, r):
        case = ET.SubElement(suite, "testcase")
        case.set("name", r["name"])
        case.set("classname", self.file_name)
        if r["status"] == "fail":
            case.set("status", "run")
            case.set("result", "false")
            failure = ET.SubElement(case, "failure")
            failure.set("message",
                        r.get("message") or "Visual inspection failed by operator")
        elif r["status"] == "untested":
            case.set("status", "notrun")
            case.set("result", "untested")
        else:
            case.set("status", "run")
            case.set("result", "true")

    def _check_update_testarg(self):
        if hasattr(self.config, 'testargs') and 'update' in self.config.testargs:
            return self.config.testargs.get('update')[0] == 'true'
        return False

    def _collect_serial_output(self, initial_result):
        serial_buffer = [initial_result]
        stop_reading = [False]

        com_obj = self.config.device.device.com_dict.get("cmd")
        reader = threading.Thread(
            target=_drain_serial_buffer,
            args=(com_obj, serial_buffer, stop_reading),
            daemon=True)
        reader.start()

        self._wait_for_user_confirmation()

        stop_reading[0] = True
        reader.join(timeout=3)

        time.sleep(1)
        remaining = _read_remaining_serial(com_obj)
        if remaining:
            serial_buffer[0] = "{}{}".format(serial_buffer[0], remaining)

        file_report = self._read_report_file()
        if file_report:
            LOG.info("Read report from device file: %d chars" % len(file_report))
            serial_buffer[0] = file_report
        else:
            LOG.warning("No report file on device, using serial output only")

        return serial_buffer[0]

    def _collect_report_via_nfs(self):
        """Unified report collection: the device copies report.txt to the NFS
        mount, the host reads the file locally. Same command on linux/liteos
        (only the mount point differs), immune to serial console noise."""
        nfs_dir = getattr(self, '_nfs_dir', None)
        if not nfs_dir or not os.path.isdir(nfs_dir):
            return ""
        device = self.config.device
        bundle_name = getattr(self, 'bundle_name', '')
        device_report = "/storage/app/data/%s/report.txt" % bundle_name
        local_report = os.path.join(nfs_dir, "report.txt")
        if os.path.exists(local_report):
            os.remove(local_report)
        kernel = device.__get_device_kernel__() or DeviceLiteKernel.linux_kernel
        mount_point = "%s/test_root" % self._get_storage_prefix(kernel)
        try:
            device.execute_command_with_timeout(
                command="cp %s %s/report.txt" % (device_report, mount_point),
                timeout=8)
        except Exception as e:
            LOG.warning("nfs report copy-back command failed: %s" % str(e))
        if not os.path.exists(local_report):
            return ""
        try:
            with open(local_report, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        finally:
            try:
                os.remove(local_report)
            except Exception:
                pass
        if content and "[report]" in content:
            return content
        return ""

    def _read_report_file(self):
        # 1) nfs copy-back: unified for linux/liteos, no serial dependency
        try:
            report = self._collect_report_via_nfs()
            if report:
                LOG.info("Read report from nfs copy-back: %d chars" % len(report))
                return report
            LOG.warning("nfs copy-back empty, falling back to serial cat")
        except Exception as e:
            LOG.warning("nfs copy-back failed: %s" % str(e))
        # 2) serial cat (legacy path; unreliable on noisy liteos consoles)
        device = self.config.device
        bundle_name = getattr(self, 'bundle_name', '')
        data_path = "/storage/app/data/%s" % bundle_name
        report_path = "%s/report.txt" % data_path
        try:
            result, status, _ = device.execute_command_with_timeout(
                command="cat %s" % report_path, timeout=5)
            if status and result and "[report]" in result:
                return result
            LOG.warning("Report file not found or empty: %s" % report_path)
        except Exception as e:
            LOG.warning("Failed to read report file: %s" % str(e))
        return ""

    def _cleanup_report_file(self, device):
        bundle_name = getattr(self, 'bundle_name', '')
        data_path = "/storage/app/data/%s" % bundle_name
        report_path = "%s/report.txt" % data_path
        try:
            device.execute_command_with_timeout(
                command="rm -f %s" % report_path, timeout=3)
        except Exception:
            pass

    def _ensure_data_dir_access(self, device):
        # /storage/app/data is owned by appspawn (uid 8, mode 750) while each
        # bundle's data dir is chowned to its own uid, so the app process cannot
        # traverse the parent dir and @system.file writeText fails with code 200.
        try:
            device.execute_command_with_timeout(
                command="chmod o+x /storage/app/data", timeout=3)
            LOG.info("App data dir access ensured (chmod o+x /storage/app/data)")
        except Exception:
            pass

    def _suppress_kernel_log(self, device):
        try:
            device.execute_command_with_timeout(
                command="echo 1 > /proc/sys/kernel/printk", timeout=3)
            LOG.info("Kernel log level lowered to KERN_ALERT only")
        except Exception:
            pass

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
            LOG.warning("ability assistant not found at %s after 3 retries. Will skip start."
                         "Serial output: %s" % (aa_dst, ls_result))

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
                                    "acts_validator_lite", "tools", "bm")
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

    def _generate_report(self, request, results):
        if not results:
            LOG.warning("No report entries parsed from serial output, "
                        "skip report generation (will be unavailable)")
            return

        result_dir = os.path.join(request.config.report_path, "result")
        os.makedirs(result_dir, exist_ok=True)

        total = len(results)
        passed = sum(1 for r in results if r["status"] == "pass")
        failed = sum(1 for r in results if r["status"] == "fail")
        ignored = sum(1 for r in results if r["status"] == "untested")

        suites = ET.Element("testsuites")
        suites.set("tests", str(total))
        suites.set("failures", str(failed))
        suites.set("ignored", str(ignored))
        suite = ET.SubElement(suites, "testsuite")
        suite.set("name", self.file_name)
        suite.set("tests", str(total))
        suite.set("failures", str(failed))
        suite.set("ignored", str(ignored))

        for r in results:
            self._append_testcase(suite, r)

        tree = ET.ElementTree(suites)
        tree.write(self.result, encoding="utf-8", xml_declaration=True)
        LOG.info("Report generated: %s (total=%d, pass=%d, fail=%d)" %
                 (self.result, total, passed, failed))

    def _get_driver_config(self, json_config):
        setattr(self.config, "command_result", "")
        self.bundle_name = get_config_value(
            'bundle-name', json_config.get_driver(), False)
        timeout_config = get_config_value(
            'timeout', json_config.get_driver(), False)
        self.timeout = int(timeout_config) // 1000 if timeout_config else 600
        ability_name_cfg = get_config_value(
            'ability-name', json_config.get_driver(), False)
        self.ability_name = ability_name_cfg or "AceAbility"
        self.hap_file = get_config_value(
            'hap-file-name', json_config.get_driver(), False)
        self.preset_dir = "/system/internal"
        self.reboot_after = True
        self.reboot_timeout = 120
        self.cleanup_after = True

    def _install_hap(self, device, kernel, storage_prefix, request):
        if not self.hap_file:
            return True
        if getattr(self, 'transfer_mode', 'nfs') == "serial":
            hap_dir = "/storage"
            hap_name = self._serial_hap_name()
        else:
            hap_dir = "%s/test_root" % storage_prefix
            hap_name = self.hap_file
        local_hap_path = os.path.join(request.config.testcases_path,
                                       "acts_validator_lite", self.hap_file)
        expected_size = os.path.getsize(local_hap_path) if os.path.exists(local_hap_path) else 0
        LOG.info("Expected HAP size: %d bytes" % expected_size)

        bm_path = "/storage/bm"
        use_bm = False
        for _ in range(3):
            _drain_serial_before_command(device)
            bm_check, _, _ = device.execute_command_with_timeout(
                command="ls %s" % bm_path, timeout=3)
            if bm_check and "No such file" not in bm_check and bm_check.strip():
                use_bm = True
                break
            LOG.warning("bm presence check returned no useful output, retrying...")
        if use_bm:
            LOG.info("Using bm install to install HAP")
            if getattr(self, 'transfer_mode', 'nfs') == "serial":
                hap_remote = "/storage/%s" % self._serial_hap_name()
            else:
                hap_remote = "%s/test_root/%s" % (storage_prefix, self.hap_file)
            if kernel == DeviceLiteKernel.linux_kernel:
                install_cmd = "/storage/bm install -p %s" % hap_remote
            else:
                device.execute_command_with_timeout(
                    command="cd /storage", timeout=1)
                install_cmd = "./bm install -p %s" % hap_remote

            if getattr(self, 'transfer_mode', 'nfs') == "serial" and \
                    kernel == DeviceLiteKernel.linux_kernel:
                # Linux serial: console noise makes output unreadable.
                # Send install, wait, then verify via install record file.
                device.execute_command_with_timeout(
                    command=install_cmd, timeout=30)
                time.sleep(5)
                record_check, _, _ = device.execute_command_with_timeout(
                    command="ls /storage/app/etc/bundles/%s.json" % self.bundle_name,
                    timeout=10)
                if ".json" in str(record_check):
                    LOG.info("HAP installed (install record verified)")
                    self.reboot_after = False
                    return True
                LOG.warning("install record not found, install may have failed")
                return False

            install_result, install_status, _ = device.execute_command_with_timeout(
                command=install_cmd, timeout=60)
            LOG.info("bm install result: %s" % str(install_result)[:200])
            install_result_low = str(install_result).lower()
            if kernel == DeviceLiteKernel.linux_kernel:
                install_ok = (install_status and "success" in install_result_low) or \
                             "already exist" in install_result_low
            else:
                install_ok = ("resultmessage is install success"
                              in install_result_low
                              or "already exist" in install_result_low)
            if install_ok:
                LOG.info("HAP installed via bm, skip reboot")
                self.reboot_after = False
                return True
            LOG.warning("bm install failed, falling back to cp method")

        LOG.info("Copying HAP from %s/%s to %s/%s" % (hap_dir, hap_name, self.preset_dir, hap_name))
        device.execute_command_with_timeout(command="cd %s" % hap_dir, timeout=3)
        for retry in range(3):
            LOG.info("HAP copy attempt %d" % (retry + 1))
            device.execute_command_with_timeout(
                command="cp %s %s/" % (hap_name, self.preset_dir),
                timeout=60)
            time.sleep(5)
            ls_result, ls_status, _ = device.execute_command_with_timeout(
                command="ls %s/%s" % (self.preset_dir, hap_name), timeout=5)
            LOG.info("HAP ls result: %s" % str(ls_result)[:200])
            if ls_status and hap_name in ls_result and "No such file" not in ls_result:
                LOG.info("HAP copy verified")
                break
            LOG.warning("HAP copy attempt %d not verified, retrying..." % (retry + 1))
            time.sleep(2)
        else:
            LOG.error("HAP copy failed after 3 retries, aborting install")
            return False

        LOG.info("Cleaning old install data: rm -r /storage/app/etc/bundles")
        device.execute_command_with_timeout(
            command="rm -r /storage/app/etc/bundles", timeout=10)
        return True

    def _launch_app(self, device):
        aa_path = "/storage/aa"
        aa_check, aa_status, _ = device.execute_command_with_timeout(
            command="ls %s" % aa_path, timeout=3)
        has_aa = (aa_check and "No such file" not in aa_check
                  and "ls or" not in aa_check and aa_check.strip())
        if not has_aa:
            LOG.warning("ability assistant not found on device, please manually launch the app")
            return ""

        device.execute_command_with_timeout(command="cd /storage", timeout=1)
        command = "./aa start -p %s -n %s" % (self.bundle_name, self.ability_name)
        LOG.info("Launch Validator test: %s" % command)
        result = ""
        for retry in range(3):
            try:
                result, _, _ = device.execute_command_with_timeout(
                    command=command,
                    case_type=DeviceTestType.validator_lite,
                    timeout=3)
                if result and "aa" in result:
                    break
                LOG.warning("ability assistant start attempt %d returned no valid result, retrying..." % (retry + 1))
            except Exception:
                LOG.warning("ability assistant start attempt %d failed, retrying..." % (retry + 1))
                result = ""
            if retry < 2:
                time.sleep(5)
        return result

    def _parse_report(self, output):
        results = []
        seen = set()
        for line in output.split("\n"):
            match = REPORT_PATTERN.search(line)
            if match:
                name = match.group(1)
                if name in seen:
                    continue
                seen.add(name)
                results.append({
                    "name": name,
                    "status": match.group(2),
                    "message": match.group(3) or "",
                })
        LOG.info("Parsed %d report entries from serial output" % len(results))
        return results

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

    def _run_validator_test(self, request):
        self.file_name = request.root.source.test_name.split(".")[0]
        self.result = "%s.xml" % os.path.join(
            request.config.report_path, "result", self.file_name)

        device = self.config.device
        kernel = self._detect_kernel(device)

        self._cleanup_report_file(device)
        self._ensure_data_dir_access(device)
        self._suppress_kernel_log(device)

        result = self._launch_app(device)
        self.config.command_result = result

        if not result or "aa" not in result:
            self._print_manual_prompt()

        result = self._collect_serial_output(result)

        self.config.command_result = result
        LOG.info("Total serial output length: %d" % len(result))

        report_data = self._parse_report(result)
        self._generate_report(request, report_data)
        if getattr(self, '_is_update', False):
            self._teardown_device(request)

    def _setup_device(self, request):
        device = self.config.device
        device.connect()
        kernel = self._detect_kernel(device)
        storage_prefix = self._get_storage_prefix(kernel)

        self._copy_aa_to_nfs(request)
        self._copy_aa_to_device(device, storage_prefix)
        hap_installed = self._install_hap(device, kernel, storage_prefix, request)

        if hap_installed and self.reboot_after:
            self._reboot_and_reconnect(device, kernel, request)

    def _setup_network(self, request):
        device = self.config.device
        device.connect()
        kernel = self._detect_kernel(device)

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
        if kernel == DeviceLiteKernel.linux_kernel:
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
            use_bm = True
            if use_bm:
                bm_check, _, _ = device.execute_command_with_timeout(
                    command="ls %s" % bm_path, timeout=3)
                use_bm = (bm_check and "No such file" not in bm_check
                         and bm_check.strip())
            if use_bm:
                LOG.info("Cleanup: bm uninstall %s" % self.bundle_name)
                uninstall_cmd = "/storage/bm uninstall -n %s" % self.bundle_name
                if kernel != DeviceLiteKernel.linux_kernel:
                    # LiteOS cannot execute absolute paths directly but `exec`
                    # can; the "exec" prefix also bypasses the dmlib "./"
                    # command branch which has no uninstall end marker and
                    # would wait for timeout.
                    uninstall_cmd = "exec /storage/bm uninstall -n %s" % self.bundle_name
                device.execute_command_with_timeout(
                    command=uninstall_cmd, timeout=30)
                LOG.info("Cleanup: bm uninstall done, skip reboot")
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

    def _write_device_log(self, device_log_file):
        device_log_file_open = os.open(
            device_log_file,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            FilePermission.mode_755)
        with os.fdopen(device_log_file_open, "a") as f:
            f.write(getattr(self.config, "command_result", "") or "")
            f.flush()
