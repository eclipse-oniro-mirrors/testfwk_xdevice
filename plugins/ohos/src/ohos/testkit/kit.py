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

import json
import os
import re
import stat
import subprocess
import time
import zipfile
from dataclasses import dataclass
from multiprocessing import Process
from multiprocessing import Queue
from tempfile import TemporaryDirectory
from tempfile import NamedTemporaryFile

from xdevice import DeviceLabelType
from xdevice import FilePermission
from xdevice import ITestKit
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import ParamError
from xdevice import get_file_absolute_path
from xdevice import get_config_value
from xdevice import exec_cmd
from xdevice import ConfigConst
from xdevice import AppInstallError
from xdevice import convert_serial
from xdevice import check_path_legal
from xdevice import modify_props
from xdevice import get_app_name_by_tool
from xdevice import remount
from xdevice import get_cst_time
from xdevice import check_device_ohca
from xdevice import Variables

from ohos.constants import CKit
from ohos.environment.dmlib import HdcHelper
from ohos.environment.dmlib import CollectingOutputReceiver
from ohos.error import ErrorMessage

__all__ = ["STSKit", "CommandKit", "PushKit", "PropertyCheckKit", "ShellKit",
           "ConfigKit", "AppInstallKit", "ComponentKit",
           "PermissionKit", "SmartPerfKit", "CommonPushKit"]

MAX_WAIT_COUNT = 4
TARGET_SDK_VERSION = 22

LOG = platform_logger("Kit")


@Plugin(type=Plugin.TEST_KIT, id=CKit.command)
class CommandKit(ITestKit):

    def __init__(self):
        self.run_command = []
        self.teardown_command = []
        self.paths = ""

    def __check_config__(self, config):
        self.paths = get_config_value('paths', config)
        self.teardown_command = get_config_value('teardown', config)
        self.run_command = get_config_value('shell', config)

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("CommandKit setup, device:{}, params:{}".
                  format(device, self.get_plugin_config().__dict__))
        if len(self.run_command) == 0:
            LOG.info("No setup_command to run, skipping!")
            return
        for command in self.run_command:
            self._run_command(command, device)

    def __teardown__(self, device):
        LOG.debug("CommandKit teardown: device:{}, params:{}".format
                  (device, self.get_plugin_config().__dict__))
        if len(self.teardown_command) == 0:
            LOG.info("No teardown_command to run, skipping!")
            return
        for command in self.teardown_command:
            self._run_command(command, device)

    def _run_command(self, command, device):

        command_type = command.get("name").strip()
        command_value = command.get("value")

        if command_type == "reboot":
            device.reboot()
        elif command_type == "install":
            LOG.debug("Trying to install package {}".format(command_value))
            package = get_file_absolute_path(command_value, self.paths)
            if not package or not os.path.exists(package):
                LOG.error(
                    "The package {} to be installed does not exist".format(
                        package))

            result = device.install_package(package)
            if not result.startswith("Success") and "successfully" not in result:
                raise AppInstallError(ErrorMessage.Device.Code_0303007.format(
                    package, device.__get_serial__(), result))
            LOG.debug("Installed package finished {}".format(package))
        elif command_type == "uninstall":
            LOG.debug("Trying to uninstall package {}".format(command_value))
            package = get_file_absolute_path(command_value, self.paths)
            app_name = get_app_name_by_tool(package, self.paths)
            if app_name:
                result = device.uninstall_package(app_name)
                if not result.startswith("Success"):
                    LOG.error("error uninstalling package %s %s" %
                              (device.__get_serial__(), result))
            LOG.debug("uninstall package finished {}".format(app_name))
        elif command_type == "pull":
            files = command_value.split("->")
            remote = files[0].strip()
            local = files[1].strip()
            device.pull_file(remote, local)
        elif command_type == "push":
            files = command_value.split("->")
            if len(files) != 2:
                LOG.error("The push spec is invalid: {}".format(command_value))
                return
            src, dst = files[0].strip(), files[1].strip()
            if not dst.startswith("/"):
                dst = Props.dest_root + dst
            LOG.debug("Trying to push the file local {} to remote{}".format(src, dst))
            real_src_path = get_file_absolute_path(src, self.paths)
            if not real_src_path or not os.path.exists(real_src_path):
                LOG.error(
                    "The src file {} to be pushed does not exist".format(src))
            device.push_file(real_src_path, dst)
            LOG.debug("Push file finished from {} to {}".format(src, dst))
        elif command_type == "shell":
            device.execute_shell_command(command_value)


@Plugin(type=Plugin.TEST_KIT, id=CKit.sts)
class STSKit(ITestKit):
    def __init__(self):
        self.sts_version = ""
        self.throw_error = ""

    def __check_config__(self, config):
        self.sts_version = get_config_value('sts-version', config)
        self.throw_error = get_config_value('throw-error', config)
        if len(self.sts_version) < 1:
            raise TypeError(ErrorMessage.Config.Code_0302013.format(self.sts_version))

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("STSKit setup, device:{}, params:{}".
                  format(device, self.get_plugin_config().__dict__))
        device_spl = device.get_property(Props.security_patch)
        if device_spl is None or device_spl == "":
            err_msg = ErrorMessage.Config.Code_0302015.format(device_spl)
            LOG.error(err_msg)
            raise ParamError(err_msg)
        rex = '^[a-zA-Z\\d\\.]+_([\\d]+-[\\d]+)$'
        match = re.match(rex, self.sts_version)
        if match is None:
            err_msg = ErrorMessage.Config.Code_0302014.format(self.sts_version)
            LOG.error(err_msg)
            raise ParamError(err_msg)
        sts_version_date_user = match.group(1).join("-01")
        sts_version_date_kernel = match.group(1).join("-05")
        if device_spl in [sts_version_date_user, sts_version_date_kernel]:
            LOG.info(
                "The device SPL version {} match the sts version {}".format(
                    device_spl, self.sts_version))
        else:
            err_msg = ErrorMessage.Config.Code_0302016.format(device_spl, self.sts_version)
            LOG.error(err_msg)
            raise ParamError(err_msg)

    def __teardown__(self, device):
        LOG.debug("STSKit teardown: device:{}, params:{}".format
                  (device, self.get_plugin_config().__dict__))


class PushBase(ITestKit):
    def __init__(self):
        self.pre_push = ""
        self.push_list = []
        self.post_push = ""
        self.is_uninstall = ""
        self.paths = ""
        self.pushed_file = []
        self.abort_on_push_failure = True
        self.teardown_push = ""
        self.request = None

    def __check_config__(self, config):
        self.pre_push = get_config_value('pre-push', config)
        self.push_list = get_config_value('push', config)
        self.post_push = get_config_value('post-push', config)
        self.teardown_push = get_config_value('teardown-push', config)
        self.is_uninstall = get_config_value('uninstall', config,
                                             is_list=False, default=True)
        self.abort_on_push_failure = get_config_value(
            'abort-on-push-failure', config, is_list=False, default=True)
        if isinstance(self.abort_on_push_failure, str):
            self.abort_on_push_failure = False if \
                self.abort_on_push_failure.lower() == "false" else True

        self.paths = get_config_value('paths', config)
        self.pushed_file = []

    def __setup__(self, device, **kwargs):
        pass

    def _get_push_list(self, device):
        new_push_list = []
        if getattr(device, 'common_kits', None):
            LOG.info(list(filter(lambda x: isinstance(x, CommonPushKit), device.common_kits)))
            common_push_list = list(filter(lambda x: isinstance(x, CommonPushKit), device.common_kits))[0].push_list
            for push_info in self.push_list:
                if push_info in common_push_list:
                    continue
                else:
                    new_push_list.append(push_info)
        else:
            new_push_list = self.push_list
        return new_push_list

    def _push_file(self, device, push_list: list) -> list:
        dsts = []
        for push_info in push_list:
            files = re.split('->|=>', push_info)
            if len(files) != 2:
                LOG.error("The push spec is invalid: {}".format(push_info))
                continue
            src, dst = files[0].strip(), files[1].strip()
            if not dst.startswith("/"):
                dst = Props.dest_root + dst
            LOG.debug("Trying to push the file local {} to remote {}".format(src, dst))

            try:
                real_src_path = get_file_absolute_path(src, self.paths)
            except ParamError as error:
                real_src_path = self.__download_web_resource(device, src)
                if real_src_path is None:
                    if self.abort_on_push_failure:
                        raise error
                    LOG.warning(error, error_no=error.error_no)
                    continue
            if check_device_ohca(device) and dst.startswith("/data/"):
                regex = re.compile('^/data/*')
                dst = regex.sub("/data/ohos_data/", dst)
            # hdc don't support push directory now
            if os.path.isdir(real_src_path):
                command = "shell mkdir {}".format(dst)
                device.connector_command(command)
                for root, _, files in os.walk(real_src_path):
                    for file in files:
                        device.push_file("{}".format(os.path.join(root, file)),
                                         "{}".format(dst))
                        LOG.debug(
                            "Push file finished from {} to {}".format(
                                os.path.join(root, file), dst))
                        self.pushed_file.append(os.path.join(dst, file))
            else:
                if device.is_directory(dst):
                    dst = os.path.join(dst, os.path.basename(real_src_path))
                    if dst.find("\\") > -1:
                        dst_paths = dst.split("\\")
                        dst = "/".join(dst_paths)
                device.push_file("{}".format(real_src_path),
                                 "{}".format(dst))
                LOG.debug("Push file finished from {} to {}".format(src, dst))
                self.pushed_file.append(dst)
            dsts.append(dst)
        return dsts

    def __download_web_resource(self, device, file_path):
        """下载OpenHarmony兼容性测试资源文件"""
        # 在命令行配置
        config = Variables.config
        request_config = self.request.config
        enable_web_resource1 = config.taskargs.get(ConfigConst.enable_web_resource, "false").lower()
        # 在xml配置
        web_resource = config.resource.get(ConfigConst.web_resource, {})
        web_resource_url = web_resource.get(ConfigConst.tag_url, "").strip()
        enable_web_resource2 = web_resource.get(ConfigConst.tag_enable, "false").lower()
        if enable_web_resource1 == "false" and enable_web_resource2 == "false":
            return None
        file_path = file_path.replace("\\", "/")
        # 必须是resource或./resource开头的资源文件
        pattern = re.compile(r'^(\./)?resource/')
        if re.match(pattern, file_path) is None:
            return None
        file_path = re.sub(pattern, "", file_path)
        save_file = os.path.join(
            request_config.get(ConfigConst.resource_path), file_path)
        if os.path.exists(save_file):
            return save_file
        url = self.__query_resource_url(device, web_resource_url, "resource/" + file_path)
        if not url:
            return None
        save_path = os.path.dirname(save_file)
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        cli = None
        try:
            import requests
            cli = requests.get(url, timeout=5, verify=False)
            if cli.status_code == 200:
                file_fd = os.open(save_file, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
                with os.fdopen(file_fd, mode="wb+") as s_file:
                    for chunk in cli.iter_content(chunk_size=1024 * 4):
                        s_file.write(chunk)
                    s_file.flush()
        except Exception as e:
            LOG.error(f"download the resource of '{file_path}' failed. {e}")
        finally:
            if cli is not None:
                cli.close()
        return save_file if os.path.exists(save_file) else None

    def __query_resource_url(self, device, query_url, file_path):
        """获取资源下载链接"""
        url = ""
        os_type = ""
        device_class = device.__class__.__name__
        if device_class == "Device":
            os_type = "standard system"
        if device_class == "DeviceLite" and device.label == DeviceLabelType.ipcamera:
            os_type = "small system"
        os_version = getattr(device, "device_props", {}).get("OsFullName", "")
        test_type = self.request.config.get(ConfigConst.task, "").upper()
        if not os_type or not os_version or re.search(r'(AC|DC|HA|HI|SS)TS', test_type) is None:
            LOG.warning("query resource params is none")
            return url
        cli = None
        params = {
            "filePath": file_path,
            "testType": test_type,
            "osType": os_type,
            "osVersion": os_version
        }
        LOG.debug(f"query resource's params {params}")
        try:
            import requests
            cli = requests.post(query_url, json=params, timeout=5, verify=False)
            rsp_code = cli.status_code
            rsp_body = cli.content.decode()
            LOG.debug(f"query resource's response code {rsp_code}")
            LOG.debug(f"query resource's response body {rsp_body}")
            if rsp_code == 200:
                try:
                    data = json.loads(rsp_body)
                    if data.get("code") == 200:
                        url = data.get("body")
                    else:
                        msg = data.get("msg")
                        LOG.error(f"query the resource of '{file_path}' downloading url failed. {msg}")
                except ValueError:
                    LOG.error("query resource's response body is not json data")
        except Exception as e:
            LOG.error(f"query the resource of '{file_path}' downloading url failed. {e}")
        finally:
            if cli is not None:
                cli.close()
        return url

    def add_pushed_dir(self, src, dst):
        for root, _, files in os.walk(src):
            for file_path in files:
                self.pushed_file.append(
                    os.path.join(root, file_path).replace(src, dst))

    def __teardown__(self, device):
        LOG.debug("PushKit teardown: device: {}".format(device.device_sn))
        for command in self.teardown_push:
            run_command(device, command)
        if self.is_uninstall:
            remount(device)
            for file_name in self.pushed_file:
                LOG.debug("Trying to remove file {}".format(file_name))
                file_name = file_name.replace("\\", "/")

                for _ in range(
                        Props.trying_remove_maximum_times):
                    collect_receiver = CollectingOutputReceiver()
                    file_name = check_path_legal(file_name)
                    device.execute_shell_command("rm -rf {}".format(
                        file_name), receiver=collect_receiver,
                        output_flag=False)
                    if not collect_receiver.output:
                        LOG.debug(
                            "Removed file {} successfully".format(file_name))
                        break
                    else:
                        LOG.error("Removed file {} successfully".
                                  format(collect_receiver.output))
                else:
                    LOG.error("Failed to remove file {}".format(file_name))

    def __add_pushed_file__(self, device, src, dst):
        if device.is_directory(dst):
            dst = dst + os.path.basename(src) if dst.endswith(
                "/") else dst + "/" + os.path.basename(src)
        self.pushed_file.append(dst)

    def __add_dir_pushed_files__(self, device, src, dst):
        if device.file_exist(device, dst):
            for _, dirs, files in os.walk(src):
                for file_path in files:
                    if dst.endswith("/"):
                        dst = "%s%s" % (dst, os.path.basename(file_path))
                    else:
                        dst = "%s/%s" % (dst, os.path.basename(file_path))
                    self.pushed_file.append(dst)
                for dir_name in dirs:
                    self.__add_dir_pushed_files__(device, dir_name, dst)
        else:
            self.pushed_file.append(dst)


@Plugin(type=Plugin.TEST_KIT, id=CKit.propertycheck)
class PropertyCheckKit(ITestKit):
    def __init__(self):
        self.prop_name = ""
        self.expected_value = ""
        self.throw_error = ""

    def __check_config__(self, config):
        self.prop_name = get_config_value('property-name', config,
                                          is_list=False)
        self.expected_value = get_config_value('expected-value', config,
                                               is_list=False)
        self.throw_error = get_config_value('throw-error', config,
                                            is_list=False)

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("PropertyCheckKit setup, device:{}".format(device.device_sn))
        if not self.prop_name:
            LOG.warning("The option of property-name not setting")
            return
        prop_value = device.get_property(self.prop_name)
        if not prop_value:
            LOG.warning(
                "The property {} not found on device, cannot check the value".
                format(self.prop_name))
            return

        if prop_value != self.expected_value:
            err_msg = ErrorMessage.Config.Code_0302024.format(self.prop_name, prop_value, self.expected_value)
            LOG.warning(err_msg)
            if self.throw_error and self.throw_error.lower() == 'true':
                raise Exception(err_msg)

    @classmethod
    def __teardown__(cls, device):
        LOG.debug("PropertyCheckKit teardown: device:{}".format(
            device.device_sn))


@Plugin(type=Plugin.TEST_KIT, id=CKit.shell)
class ShellKit(ITestKit):
    def __init__(self):
        self.command_list = []
        self.tear_down_command = []
        self.paths = None

    def __check_config__(self, config):
        self.command_list = get_config_value('run-command', config)
        self.tear_down_command = get_config_value('teardown-command', config)
        self.tear_down_local_command = get_config_value('teardown-localcommand', config)
        self.paths = get_config_value('paths', config)

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("ShellKit setup, device:{}".format(device.device_sn))
        if len(self.command_list) == 0:
            LOG.info("No setup_command to run, skipping!")
            return
        for command in self.command_list:
            run_command(device, command)

    def __teardown__(self, device):
        LOG.debug("ShellKit teardown: device:{}".format(device.device_sn))
        if len(self.tear_down_command) == 0:
            LOG.info("No teardown_command to run, skipping!")
        else:
            for command in self.tear_down_command:
                run_command(device, command)
        if len(self.tear_down_local_command) == 0:
            LOG.info("No teardown-localcommand to run, skipping!")
        else:
            for command in self.tear_down_local_command:
                subprocess.run(command)
                ret = subprocess.run(command, capture_output=True, text=True)
                LOG.info("Teardown-localcommand run: {}".format(ret))


@dataclass
class Props:
    @dataclass
    class Paths:
        system_build_prop_path = "/system/build.prop"
        service_wifi_app_path = "tools/wifi/xDeviceService-wifi.apk"

    dest_root = "/data/data/"
    mnt_external_storage = "EXTERNAL_STORAGE"
    trying_remove_maximum_times = 3
    maximum_connect_wifi_times = 3
    connect_wifi_cmd = "am instrument -e request \"{{module:Wifi, " \
                       "method:connectWifiByCertificate, params:{{'certPath':" \
                       "'{}}}'," \
                       "'certPassword':'{}'," \
                       "'wifiName':'{}'}}}}\"  " \
                       "-w com.xdeviceservice.service.plrdtest/com.xdeviceservice.service.MainInstrumentation"
    security_patch = "ro.build.version.security_patch"


@Plugin(type=Plugin.TEST_KIT, id=CKit.config)
class ConfigKit(ITestKit):
    def __init__(self):
        self.is_connect_wifi = ""
        self.is_disconnect_wifi = ""
        self.min_external_store_space = ""
        self.is_disable_dialing = ""
        self.is_test_harness = ""
        self.is_audio_silent = ""
        self.is_disable_dalvik_verifier = ""
        self.build_prop_list = ""
        self.is_enable_hook = ""
        self.cust_prop_file = ""
        self.is_prop_changed = False
        self.local_system_prop_file = ""
        self.cust_props = ""
        self.is_reboot_delay = ""
        self.is_remount = ""
        self.local_cust_prop_file = {}

    def __check_config__(self, config):
        self.is_connect_wifi = get_config_value('connect-wifi', config,
                                                is_list=False, default=False)
        self.is_disconnect_wifi = get_config_value(
            'disconnect-wifi-after-test', config, is_list=False, default=True)
        self.min_external_store_space = get_config_value(
            'min-external-store-space', config)
        self.is_disable_dialing = get_config_value('disable-dialing', config)
        self.is_test_harness = get_config_value('set-test-harness', config)
        self.is_audio_silent = get_config_value('audio-silent', config)
        self.is_disable_dalvik_verifier = get_config_value(
            'disable-dalvik-verifier', config)
        self.build_prop_list = get_config_value('build-prop', config)
        self.cust_prop_file = get_config_value('cust-prop-file', config)
        self.cust_props = get_config_value('cust-prop', config)
        self.is_enable_hook = get_config_value('enable-hook', config)
        self.is_reboot_delay = get_config_value('reboot-delay', config)
        self.is_remount = get_config_value('remount', config, default=True)
        self.local_system_prop_file = NamedTemporaryFile(prefix='build',
                                                         suffix='.prop',
                                                         delete=False).name

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("ConfigKit setup, device:{}".format(device.device_sn))
        if self.is_remount:
            remount(device)
        self.is_prop_changed = self.modify_system_prop(device)
        self.is_prop_changed = self.modify_cust_prop(
            device) or self.is_prop_changed

        keep_screen_on(device)
        if self.is_enable_hook:
            pass
        if self.is_prop_changed:
            device.reboot()

    def __teardown__(self, device):
        LOG.debug("ConfigKit teardown: device:{}".format(device.device_sn))
        if self.is_remount:
            remount(device)
        if self.is_prop_changed:
            device.push_file(self.local_system_prop_file,
                             Props.Paths.system_build_prop_path)
            device.execute_shell_command(
                " ".join(["chmod 644", Props.Paths.system_build_prop_path]))
            os.remove(self.local_system_prop_file)

            for target_file, temp_file in self.local_cust_prop_file.items():
                device.push_file(temp_file, target_file)
                device.execute_shell_command(
                    " ".join(["chmod 644", target_file]))
                os.remove(temp_file)

    def modify_system_prop(self, device):
        prop_changed = False
        new_props = {}
        if self.is_disable_dialing:
            new_props['ro.telephony.disable-call'] = 'true'
        if self.is_test_harness:
            new_props['ro.monkey'] = '1'
            new_props['ro.test_harness'] = '1'
        if self.is_audio_silent:
            new_props['ro.audio.silent'] = '1'
        if self.is_disable_dalvik_verifier:
            new_props['dalvik.vm.dexopt-flags'] = 'v=n'
        for prop in self.build_prop_list:
            if prop is None or prop.find("=") < 0 or len(prop.split("=")) != 2:
                LOG.warning("The build prop:{} not match the format "
                            "'key=value'".format(prop))
                continue
            new_props[prop.split("=")[0]] = prop.split("=")[1]
        if new_props:
            prop_changed = modify_props(device, self.local_system_prop_file,
                                        Props.Paths.system_build_prop_path,
                                        new_props)
        return prop_changed

    def modify_cust_prop(self, device):
        prop_changed = False
        cust_files = {}
        new_props = {}
        for cust_prop_file in self.cust_prop_file:
            # the correct format should be "CustName:/cust/prop/absolutepath"
            if len(cust_prop_file.split(":")) != 2:
                LOG.error(
                    "The value %s of option cust-prop-file is incorrect" %
                    cust_prop_file)
                continue
            cust_files[cust_prop_file.split(":")[0]] = \
                cust_prop_file.split(":")[1]
        for prop in self.cust_props:
            # the correct format should be "CustName:key=value"
            prop_infos = re.split(r'[:|=]', prop)
            if len(prop_infos) != 3:
                LOG.error(
                    "The value {} of option cust-prop is incorrect".format(
                        prop))
                continue
            file_name, key, value = prop_infos
            if file_name not in cust_files:
                LOG.error(
                    "The custName {} must be in cust-prop-file option".format(
                        file_name))
                continue
            props = new_props.setdefault(file_name, {})
            props[key] = value

        for name in new_props.keys():
            cust_file = cust_files.get(name)
            temp_cust_file = NamedTemporaryFile(prefix='cust', suffix='.prop',
                                                delete=False).name
            self.local_cust_prop_file[cust_file] = temp_cust_file
            try:
                prop_changed = modify_props(device, temp_cust_file, cust_file,
                                            new_props[name]) or prop_changed
            except KeyError:
                LOG.error("Get props error.")
                continue

        return prop_changed


@Plugin(type=Plugin.TEST_KIT, id=CKit.app_install)
class AppInstallKit(ITestKit):
    def __init__(self):
        self.app_list = ""
        self.app_list_name = ""
        self.is_clean = ""
        self.alt_dir = ""
        self.ex_args = ""
        self.installed_app = set()
        self.paths = ""
        self.is_pri_app = ""
        self.pushed_hap_file = set()
        self.env_index_list = None

    def __check_config__(self, options):
        self.app_list = get_config_value('test-file-name', options)
        self.app_list_name = get_config_value('test-file-packName', options)
        self.is_clean = get_config_value('cleanup-apps', options, False)
        self.alt_dir = get_config_value('alt-dir', options, False)
        if self.alt_dir and self.alt_dir.startswith("resource/"):
            self.alt_dir = self.alt_dir[len("resource/"):]
        self.ex_args = get_config_value('install-arg', options, False)
        self.installed_app = set()
        self.paths = get_config_value('paths', options)
        self.is_pri_app = get_config_value('install-as-privapp', options,
                                           False, default=False)
        self.env_index_list = get_config_value('env-index', options)

    def __setup__(self, device, **kwargs):
        del kwargs
        LOG.debug("AppInstallKit setup, device:{}".format(device.device_sn))
        if len(self.app_list) == 0:
            LOG.info("No app to install, skipping!")
            return
        # to disable app install alert
        for app in self.app_list:
            if self.alt_dir:
                app_file = get_file_absolute_path(app, self.paths,
                                                  self.alt_dir)
            else:
                app_file = get_file_absolute_path(app, self.paths)
            if app_file is None:
                LOG.error("The app file {} does not exist".format(app))
                continue
            self.install_hap(device, app_file)
            self.installed_app.add(app_file)

    def __teardown__(self, device):
        LOG.debug("AppInstallKit teardown: device:{}".format(device.device_sn))
        if self.is_clean and str(self.is_clean).lower() == "true":
            if self.app_list_name and len(self.app_list_name) > 0:
                for app_name in self.app_list_name:
                    result = device.uninstall_package(app_name)
                    if result and (result.startswith("Success") or "successfully" in result):
                        LOG.debug("uninstalling package Success. result is %s" %
                                  result)
                    else:
                        LOG.warning("Error uninstalling package %s %s" %
                                    (device.__get_serial__(), result))
            else:
                for app in self.installed_app:
                    app_name = get_app_name(app)
                    if app_name:
                        result = device.uninstall_package(app_name)
                        if result and (result.startswith("Success") or "successfully" in result):
                            LOG.debug("uninstalling package Success. result is %s" %
                                      result)
                        else:
                            LOG.warning("Error uninstalling package %s %s" %
                                        (device.__get_serial__(), result))
                    else:
                        LOG.warning("Can't find app name for %s" % app)
        if self.is_pri_app:
            remount(device)
        for pushed_file in self.pushed_hap_file:
            device.execute_shell_command("rm -r %s" % pushed_file)

    def install_hap(self, device, hap_file):
        if self.is_pri_app:
            LOG.info("Install hap as privileged app {}".format(hap_file))
            hap_name = os.path.basename(hap_file).replace(".hap", "")
            try:
                with TemporaryDirectory(prefix=hap_name) as temp_dir:
                    zif_file = zipfile.ZipFile(hap_file)
                    zif_file.extractall(path=temp_dir)
                    entry_app = os.path.join(temp_dir, "Entry.app")
                    push_dest_dir = os.path.join("/system/priv-app/", hap_name)
                    device.execute_shell_command("rm -rf " + push_dest_dir,
                                                 output_flag=False)
                    device.push_file(entry_app, os.path.join(
                        push_dest_dir + os.path.basename(entry_app)))
                    device.push_file(hap_file, os.path.join(
                        push_dest_dir + os.path.basename(hap_file)))
                    self.pushed_hap_file.add(os.path.join(
                        push_dest_dir + os.path.basename(hap_file)))
                    device.reboot()
            except Exception as exception:
                err_msg = ErrorMessage.Device.Code_0303006.format(exception)
                LOG.error(err_msg)
                raise Exception(err_msg) from exception
            finally:
                zif_file.close()
        else:
            if hasattr(device, "is_oh"):
                push_dest = "/data/local/tmp"
            else:
                push_dest = "/sdcard"
            push_dest = "{}/{}".format(push_dest, os.path.basename(hap_file))
            device.push_file(hap_file, push_dest)
            self.pushed_hap_file.add(push_dest)
            output = device.execute_shell_command("bm install -p {} {}".format(push_dest, self.ex_args))
            if not output.startswith("Success") and "successfully" not in output:
                output = output.strip()
                if "[ERROR_GET_BUNDLE_INSTALLER_FAILED]" not in output.upper():
                    raise AppInstallError(ErrorMessage.Device.Code_0303007.format(
                        push_dest, device.__get_serial__(), output))
                else:
                    LOG.info("'[ERROR_GET_BUNDLE_INSTALLER_FAILED]' occurs, "
                             "retry install hap")
                    exec_out = self.retry_install_hap(
                        device, "bm install -p {} {}".format(push_dest, self.ex_args))
                    if not exec_out.startswith("Success") and "successfully" not in output:
                        raise AppInstallError(ErrorMessage.Device.Code_0303007.format(
                            push_dest, device.__get_serial__(), exec_out))
            else:
                LOG.debug("Install %s success" % push_dest)

    @classmethod
    def retry_install_hap(cls, device, command):
        real_command = [HdcHelper.CONNECTOR_NAME, "-t", str(device.device_sn), "-s",
                        "tcp:%s:%s" % (str(device.host), str(device.port)),
                        "shell", command]
        message = "%s execute command: %s" % \
                  (convert_serial(device.device_sn), " ".join(real_command))
        LOG.info(message)
        exec_out = ""
        for wait_count in range(1, MAX_WAIT_COUNT):
            LOG.debug("Retry times:%s, wait %ss" %
                      (wait_count, (wait_count * 10)))
            time.sleep(wait_count * 10)
            exec_out = exec_cmd(real_command)
            if exec_out and exec_out.startswith("Success"):
                break
        if not exec_out:
            exec_out = "System is not in %s" % ["Windows", "Linux", "Darwin"]
        LOG.info("Retry install hap result is: [%s]" % exec_out.strip())
        return exec_out


@Plugin(type=Plugin.TEST_KIT, id=CKit.component)
class ComponentKit(ITestKit):

    def __init__(self):
        self._white_list_file = ""
        self._white_list = ""
        self._cap_file = ""
        self.paths = ""
        self.cache_subsystem = set()
        self.cache_part = set()

    def __check_config__(self, config):
        self._white_list_file = \
            get_config_value('white-list', config, is_list=False)
        self._cap_file = get_config_value('cap-file', config, is_list=False)
        self.paths = get_config_value('paths', config)

    def __setup__(self, device, **kwargs):
        if hasattr(device, ConfigConst.support_component):
            return
        if device.label in ["phone", "watch", "car", "tv", "tablet", "ivi"]:
            command = "cat %s" % self._cap_file
            result = device.execute_shell_command(command)
            part_set = set()
            subsystem_set = set()
            if "{" in result:
                for item in json.loads(result).get("components", []):
                    part_set.add(item.get("component", ""))
            subsystems, parts = self.get_white_list()
            part_set.update(parts)
            subsystem_set.update(subsystems)
            setattr(device, ConfigConst.support_component,
                    (subsystem_set, part_set))
            self.cache_subsystem.update(subsystem_set)
            self.cache_part.update(part_set)

    def get_cache(self):
        return self.cache_subsystem, self.cache_part

    def get_white_list(self):
        if not self._white_list and self._white_list_file:
            self._white_list = self._parse_white_list()
        return self._white_list

    def _parse_white_list(self):
        subsystem = set()
        part = set()
        white_json_file = os.path.normpath(self._white_list_file)
        if not os.path.isabs(white_json_file):
            white_json_file = \
                get_file_absolute_path(white_json_file, self.paths)
        if os.path.isfile(white_json_file):
            subsystem_list = list()
            flags = os.O_RDONLY
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(os.open(white_json_file, flags, modes),
                           "r") as file_content:
                json_result = json.load(file_content)
                if "subsystems" in json_result.keys():
                    subsystem_list.extend(json_result["subsystems"])
                for subsystem_item_list in subsystem_list:
                    for key, value in subsystem_item_list.items():
                        if key == "subsystem":
                            subsystem.add(value)
                        elif key == "components":
                            for component_item in value:
                                if "component" in component_item.keys():
                                    part.add(
                                        component_item["component"])

        return subsystem, part

    def __teardown__(self, device):
        if hasattr(device, ConfigConst.support_component):
            setattr(device, ConfigConst.support_component, None)
        self._white_list_file = ""
        self._white_list = ""
        self._cap_file = ""
        self.cache_subsystem.clear()
        self.cache_part.clear()
        self.cache_device.clear()


@Plugin(type=Plugin.TEST_KIT, id=CKit.permission)
class PermissionKit(ITestKit):
    def __init__(self):
        self.package_name_list = None
        self.permission_list = None

    def __check_config__(self, config):
        self.package_name_list = \
            get_config_value('package-names', config, True, [])
        self.permission_list = \
            get_config_value('permissions', config, True, [])

    def __setup__(self, device, **kwargs):
        if not self.package_name_list or not self.permission_list:
            LOG.warning("Please check parameters of permission kit in json")
            return
        for index in range(len(self.package_name_list)):
            cur_name = self.package_name_list[index]
            token_id = self._get_token_id(device, cur_name)
            if not token_id:
                LOG.warning("Not found accessTokenId of '{}'".format(cur_name))
                continue
            for permission in self.permission_list[index]:
                command = "atm perm -g -i {} -p {}".format(token_id,
                                                           permission)
                out = device.execute_shell_command(command)
                LOG.debug("Set permission result: {}".format(out))

    def __teardown__(self, device):
        pass

    def _get_token_id(self, device, pkg_name):
        # shell bm dump -n
        dum_command = "bm dump -n {}".format(pkg_name)
        content = device.execute_shell_command(dum_command)
        if not content or not str(content).startswith(pkg_name):
            return ""
        content = content[len(pkg_name) + len(":\n"):]
        dump_dict = json.loads(content)
        if "userInfo" not in dump_dict.keys():
            return ""
        user_info_dict = dump_dict["userInfo"][0]
        if "accessTokenId" not in user_info_dict.keys():
            return ""
        else:
            return user_info_dict["accessTokenId"]


def keep_screen_on(device):
    device.execute_shell_command("svc power stayon true")


def run_command(device, command):
    LOG.debug("The command:{} is running".format(command))
    stdout = None
    if command.strip() == "remount":
        remount(device)
    elif command.strip() == "target mount":
        device.connector_command(command.split(" "))
    elif command.strip() == "reboot":
        device.reboot()
    elif command.strip() == "reboot-delay":
        pass
    elif command.strip().endswith("&"):
        device.execute_shell_in_daemon(command.strip())
    elif command.strip().startswith("push"):
        if check_device_ohca(device):
            command_list = command.split(" ")
            if command_list and \
                    len(command_list) > 0 and \
                    command_list[len(command_list) - 1].startswith("/data/"):
                regex = re.compile('^/data/*')
                command_list[len(command_list) - 1] = regex.sub("/data/ohos_data/",
                                                                command_list[len(command_list) - 1])
                command = " ".join(command_list)
        stdout = device.execute_shell_command(command)
    elif command.strip().startswith("cp"):
        if check_device_ohca(device):
            regex = re.compile('^/data/*')
            command_list = command.split(" ")
            if command_list[1].startswith("/data/"):
                command_list[1] = regex.sub("/data/ohos_data/", command_list[1])
            if command_list[2].startswith("/data"):
                command_list[2] = regex.sub("/data/ohos_data/", command_list[2])
            command = " ".join(command_list)
        stdout = device.execute_shell_command(command)
    else:
        stdout = device.execute_shell_command(command)
    LOG.debug("Run command result: %s" % (stdout if stdout else ""))
    return stdout


def get_app_name(hap_app):
    hap_name = os.path.basename(hap_app).replace(".hap", "")
    app_name = ""
    hap_file_info = None
    config_json_file = ""
    try:
        hap_file_info = zipfile.ZipFile(hap_app)
        name_list = ["module.json", "config.json"]
        for _, name in enumerate(hap_file_info.namelist()):
            if name in name_list:
                config_json_file = name
                break
        config_info = hap_file_info.read(config_json_file).decode('utf-8')
        attrs = json.loads(config_info)
        if "app" in attrs.keys() and \
                "bundleName" in attrs.get("app", dict()).keys():
            app_name = attrs["app"]["bundleName"]
            LOG.info("Obtain the app name {} from json "
                     "successfully".format(app_name))
        else:
            LOG.debug("Tip: 'app' or 'bundleName' not "
                      "in {}.hap/config.json".format(hap_name))
    except Exception as e:
        LOG.error("get app name from hap error: {}".format(e))
    finally:
        if hap_file_info:
            hap_file_info.close()
    return app_name


@Plugin(type=Plugin.TEST_KIT, id=CKit.smartperf)
class SmartPerfKit(ITestKit):
    def __init__(self):
        self._run_command = ["SP_daemon", "-PKG"]
        self._process = None
        self._pattern = "order:\\d+ (.+)=(.+)"
        self._param_key = ["cpu", "gpu", "ddr", "fps", "pnow", "ram", "temp"]
        self.target_name = ""
        self._msg_queue = None

    def __check_config__(self, config):
        self._run_command.append(self.target_name)
        if isinstance(config, str):
            key_value_pairs = str(config).split(";")
            for key_value_pair in key_value_pairs:
                key, value = key_value_pair.split(":", 1)
                if key == "num":
                    self._run_command.append("-N")
                    self._run_command.append(value)
                else:
                    if key in self._param_key and value == "true":
                        self._run_command.append("-" + key[:1])
        elif isinstance(config, dict):
            self._run_command[-1] = config.get('bundle_name', '')
            params = config.get('params', {})
            if 'num' not in params:
                self._run_command.append("-N")
                self._run_command.append("1")
                LOG.warning(f'Set num to default value (1) because it is not set. ')
            for key, value in params.items():
                if key == "num":
                    self._run_command.append("-N")
                    try:
                        value = int(value)
                    except ValueError as e:
                        value = 1
                        LOG.warning(f'Set num to default value ({value}) because: {e}')
                    if value <= 0:
                        value = 1
                        LOG.warning(f'Set num to default value ({value}) because it cannot be less than 1! ')
                    self._run_command.append(f"{value}")
                else:
                    if key in self._param_key and value:
                        self._run_command.append("-" + key[:1])

    def _execute(self, msg_queue, cmd_list, xls_file, proc_name):
        data = []
        while msg_queue.empty():
            process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       shell=False)
            rev = process.stdout.read()
            data.append((get_cst_time().strftime("%Y-%m-%d-%H-%M-%S"), rev))
        self.write_to_file(data, proc_name, xls_file)

    def write_to_file(self, data, proc_name, xls_file):
        from openpyxl import Workbook
        from openpyxl import styles
        book = Workbook()
        sheet = book.active
        sheet.row_dimensions[1].height = 30
        sheet.column_dimensions["A"].width = 30
        sheet.sheet_properties.tabColor = "1072BA"
        alignment = styles.Alignment(horizontal='center',
                                     vertical='center')
        font = styles.Font(size=15, color="000000",
                           bold=True, italic=False, strike=None,
                           underline=None)
        names = ["time", "PKG"]
        start = True
        for _time, content in data:
            cur = [_time, proc_name]
            rev_list = str(content, "utf-8").split("\n")
            if start:
                start = False
                for rev in rev_list:
                    result = re.match(self._pattern, rev)
                    if result and result.group(1):
                        names.append(result.group(1))
                        cur.append(result.group(2))
                sheet.append(names)
                sheet.append(cur)
                for pos in range(1, len(names) + 1):
                    cur_cell = sheet.cell(1, pos)
                    sheet.column_dimensions[cur_cell.column_letter].width = 20
                    cur_cell.alignment = alignment
                    cur_cell.font = font
            else:
                for rev in rev_list:
                    result = re.match(self._pattern, rev)
                    if result and result.group(1):
                        cur.append(result.group(2))
                sheet.append(cur)
        book.save(xls_file)

    def __setup__(self, device, **kwargs):
        request = kwargs.get("request")
        folder = os.path.join(request.get_config().report_path, "smart_perf")
        if not os.path.exists(folder):
            os.mkdir(folder)
        file = os.path.join(folder, "{}.xlsx".format(request.get_module_name()))
        if device.host != "127.0.0.1":
            cmd_list = [HdcHelper.CONNECTOR_NAME, "-s",
                        "{}:{}".format(device.host, device.port), "-t",
                        device.device_sn, "shell"]
        else:
            cmd_list = [HdcHelper.CONNECTOR_NAME, "-t", device.device_sn,
                        "shell"]

        cmd_list.extend(self._run_command)
        LOG.debug("Smart perf command:{}".format(" ".join(cmd_list)))
        self._msg_queue = Queue()
        self._process = Process(target=self._execute, args=(
            self._msg_queue, cmd_list, file, self.target_name))
        self._process.start()

    def __teardown__(self, device):
        if self._process:
            if self._msg_queue:
                self._msg_queue.put("")
                self._msg_queue = None
            else:
                self._process.terminate()
            self._process = None


@Plugin(type=Plugin.TEST_KIT, id=CKit.push)
class PushKit(PushBase):

    def __setup__(self, device, **kwargs):
        self.request = kwargs.get("request")
        LOG.debug("PushKit setup, device: {}".format(device.device_sn))
        for command in self.pre_push:
            run_command(device, command)
        remount(device)
        push_list = self._get_push_list(device)
        dsts = self._push_file(device, push_list)
        for command in self.post_push:
            run_command(device, command)
        return self.pushed_file, dsts


@Plugin(type=Plugin.TEST_KIT, id=CKit.common_push)
class CommonPushKit(PushBase):

    def __setup__(self, device, **kwargs):
        self.request = kwargs.get("request")
        LOG.debug("Common PushKit setup, device: {}".format(device.device_sn))
        for command in self.pre_push:
            run_command(device, command)
        remount(device)
        dsts = self._push_file(device, self.push_list)
        for command in self.post_push:
            run_command(device, command)
        return self.pushed_file, dsts
