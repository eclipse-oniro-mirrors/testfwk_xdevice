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

import copy
import os
import re
import stat
import json
import time
import platform
import subprocess
import signal
from threading import Timer

from _core.constants import ConfigConst
from _core.constants import DeviceConnectorType
from _core.constants import DeviceTestType
from _core.constants import FilePermission
from _core.context.center import Context
from _core.error import ErrorMessage
from _core.exception import ExecuteTerminate
from _core.exception import ParamError
from _core.logger import platform_logger
from _core.plugin import get_plugin
from _core.plugin import Plugin
from _core.testkit.json_parser import JsonParser
from _core.utils import get_file_absolute_path

LOG = platform_logger("Kit")

TARGET_SDK_VERSION = 22

__all__ = [
    "get_app_name_by_tool", "junit_para_parse", "gtest_para_parse",
    "get_install_args", "reset_junit_para", "remount", "disable_keyguard",
    "timeout_callback", "unlock_screen", "unlock_device", "get_class",
    "check_device_ohca", "check_device_name", "check_device_env_index",
    "do_module_kit_setup", "do_module_kit_teardown",
    "do_common_module_kit_setup", "do_common_module_kit_teardown",
    "get_kit_instances"
]


def remount(device):
    cmd = "target mount" \
        if device.usb_type == DeviceConnectorType.hdc else "remount"
    device.connector_command(cmd)
    device.execute_shell_command("remount")
    device.execute_shell_command("mount -o rw,remount /")
    device.execute_shell_command("mount -o rw,remount /sys_prod")
    device.execute_shell_command("mount -o rw,remount /chip_prod")
    device.execute_shell_command("mount -o rw,remount /preload")
    device.execute_shell_command("mount -o rw,remount /patch_hw")
    device.execute_shell_command("mount -o rw,remount /vendor")
    device.execute_shell_command("mount -o rw,remount /cust")
    device.execute_shell_command("mount -o rw,remount /product")
    device.execute_shell_command("mount -o rw,remount /hw_product")
    device.execute_shell_command("mount -o rw,remount /version")
    device.execute_shell_command("mount -o rw,remount /system")
    device.connector_command("target mount")


def get_class(junit_paras, prefix_char, para_name):
    if not junit_paras.get(para_name):
        return ""

    result = ""
    if prefix_char == "-e":
        result = " {} class ".format(prefix_char)
    elif prefix_char == "--":
        result = " {} class ".format(prefix_char)
    elif prefix_char == "-s":
        result = " {} class ".format(prefix_char)
    test_items = []
    for test in junit_paras.get(para_name):
        test_item = test.split("#")
        if len(test_item) == 1 or len(test_item) == 2:
            test_item = "{}".format(test)
            test_items.append(test_item)
        elif len(test_item) == 3:
            test_item = "{}#{}".format(test_item[1], test_item[2])
            test_items.append(test_item)
        else:
            raise ParamError(ErrorMessage.Common.Code_0101031.format(prefix_char, para_name))
    if not result:
        LOG.debug("There is unsolved prefix char: {} .".format(prefix_char))
    return result + ",".join(test_items)


def junit_para_parse(device, junit_paras, prefix_char="-e"):
    """To parse the para of junit
    Args:
        device: the device running
        junit_paras: the para dict of junit
        prefix_char: the prefix char of parsed cmd
    Returns:
        the new para using in a command like -e testFile xxx
        -e coverage true...
    """
    ret_str = []
    path = "/{}/{}/{}".format("data", "local", "ajur")
    include_file = "{}/{}".format(path, "includes.txt")
    exclude_file = "{}/{}".format(path, "excludes.txt")

    if not isinstance(junit_paras, dict):
        LOG.warning("The para of junit is not the dict format as required")
        return ""
    # Disable screen keyguard
    disable_key_guard = junit_paras.get('disable-keyguard')
    if not disable_key_guard or disable_key_guard[0].lower() != 'false':
        disable_keyguard(device)

    for key, value in junit_paras.items():
        # value is a list object
        para_name = key.strip()
        path = "/{}/{}/{}/".format("data", "local", "ajur")
        if para_name == "test-file-include-filter":
            for file_name in value:
                device.push_file(file_name, include_file)
                device.execute_shell_command(
                    'chown -R shell:shell {}'.format(path))
            ret_str.append(" ".join([prefix_char, "testFile", include_file]))
        elif para_name == "test-file-exclude-filter":
            for file_name in value:
                device.push_file(file_name, exclude_file)
                device.execute_shell_command(
                    'chown -R shell:shell {}'.format(path))
            ret_str.append(" ".join([prefix_char, "notTestFile", exclude_file]))
        elif para_name == "test" or para_name == "class":
            result = get_class(junit_paras, prefix_char, para_name)
            ret_str.append(result)
        elif para_name == "include-annotation":
            ret_str.append(" ".join([prefix_char, "annotation", ",".join(value)]))
        elif para_name == "exclude-annotation":
            ret_str.append(" ".join([prefix_char, "notAnnotation", ",".join(value)]))

    return " ".join(ret_str)


def get_include_tests(para_datas, test_types, runner):
    case_list = []
    if test_types == "class":
        case_list = para_datas
    else:
        for case_file in para_datas:
            flags = os.O_RDONLY
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(os.open(case_file, flags, modes), "r") as file_desc:
                case_list.extend(file_desc.read().splitlines())
    runner.add_instrumentation_arg("gtest_filter", ":".join(case_list).replace("#", "."))


def get_all_test_include(para_datas, test_types, runner, request):
    case_list = []
    if test_types == "notClass":
        case_list = para_datas
    else:
        if para_datas:
            flags = os.O_RDONLY
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(os.open(para_datas[0], flags, modes), "r") as file_handler:
                json_data = json.load(file_handler)
            exclude_list = json_data.get(DeviceTestType.cpp_test, [])
            for exclude in exclude_list:
                if request.get_module_name() in exclude:
                    temp = exclude.get(request.get_module_name())
                    case_list.extend(temp)
    runner.add_instrumentation_arg("gtest_filter", "{}{}".format("-", ":".join(case_list)).replace("#", "."))


def gtest_para_parse(gtest_paras, runner, request):
    """To parse the para of gtest
    Args:
        gtest_paras: the para dict of gtest
    Returns:
        the new para using in gtest
    """
    if not isinstance(gtest_paras, dict):
        LOG.warning("The para of gtest is not the dict format as required")
        return ""
    for para in gtest_paras.keys():
        test_types = para.strip()
        para_datas = gtest_paras.get(para)
        if test_types in ["test-file-include-filter", "class"]:
            get_include_tests(para_datas, test_types, runner)
        elif test_types in ["all-test-file-exclude-filter", "notClass"]:
            get_all_test_include(para_datas, test_types, runner, request)
    return ""


def reset_junit_para(junit_para_str, prefix_char="-e", ignore_keys=None):
    if not ignore_keys and not isinstance(ignore_keys, list):
        ignore_keys = ["class", "test"]
    lines = junit_para_str.split("{} ".format(prefix_char))
    normal_lines = []
    for line in lines:
        line = line.strip()
        if line:
            items = line.split()
            if items[0].strip() in ignore_keys:
                continue
            normal_lines.append("{} {}".format(prefix_char, line))
    return " ".join(normal_lines)


def get_install_args(device, app_name, original_args=None):
    """To obtain all the args of app install
    Args:
        original_args: the argus configure in .config file
        device : the device will be installed app
        app_name : the name of the app which will be installed
    Returns:
        All the args
    """
    if original_args is None:
        original_args = []
    new_args = original_args[:]
    try:
        sdk_version = device.get_property("ro.build.version.sdk")
        if int(sdk_version) > TARGET_SDK_VERSION:
            new_args.append("-g")
    except TypeError as type_error:
        LOG.error("Obtain the sdk version failed with exception {}".format(
            type_error))
    except ValueError as value_error:
        LOG.error("Obtain the sdk version failed with exception {}".format(
            value_error))
    if app_name.endswith(".apex"):
        new_args.append("--apex")
    return " ".join(new_args)


def get_app_name_by_tool(app_path, paths):
    """To obtain the app name by using tool
    Args:
        app_path: the path of app
        paths:
    Returns:
        The Pkg Name if found else None
    """
    rex = "^package:\\s+name='(.*?)'.*$"
    if platform.system() == "Windows":
        aapt_tool_name = "aapt.exe"
    elif platform.system() == "Linux":
        aapt_tool_name = "aapt"
    else:
        aapt_tool_name = "aapt_mac"
    if app_path:
        proc_timer = None
        try:
            tool_file = get_file_absolute_path(aapt_tool_name, paths)
            LOG.debug("Aapt file is {}".format(tool_file))

            if platform.system() == "Linux" or platform.system() == "Darwin":
                if not oct(os.stat(tool_file).st_mode)[-3:] == "755":
                    os.chmod(tool_file, FilePermission.mode_755)

            cmd = [tool_file, "dump", "badging", app_path]
            timeout = 300
            LOG.info("Execute command {} with {}".format(" ".join(cmd), timeout))

            sub_process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
            proc_timer = Timer(timeout, timeout_callback, [sub_process])
            proc_timer.start()
            # The package name must be return in first line
            output = sub_process.stdout.readline()
            error = sub_process.stderr.readline()
            LOG.debug("The output of aapt is {}".format(output))
            if error:
                LOG.debug("The error of aapt is {}".format(error))
            if output:
                pkg_match = re.match(rex, output.decode("utf8", 'ignore'))
                if pkg_match is not None:
                    LOG.info(
                        "Obtain the app name {} successfully by using "
                        "aapt".format(pkg_match.group(1)))
                    return pkg_match.group(1)
            return None
        except (FileNotFoundError, ParamError) as error:
            LOG.debug("Aapt error: {}".format(error.args))
            return None
        finally:
            if proc_timer:
                proc_timer.cancel()
    else:
        LOG.error("get_app_name_by_tool error.")
        return None


def timeout_callback(proc):
    try:
        LOG.error("Error: execute command timeout.")
        LOG.error(proc.pid)
        if platform.system() != "Windows":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            subprocess.call(
                ["C:\\Windows\\System32\\taskkill", "/F", "/T", "/PID",
                 str(proc.pid)], shell=False)
    except (FileNotFoundError, KeyboardInterrupt, AttributeError) as error:
        LOG.exception("Timeout callback exception: {}".format(error, exc_info=False))


def disable_keyguard(device):
    unlock_screen(device)
    unlock_device(device)


def unlock_screen(device):
    device.execute_shell_command("svc power stayon true")
    time.sleep(1)


def unlock_device(device):
    device.execute_shell_command("input keyevent 82")
    time.sleep(1)
    device.execute_shell_command("wm dismiss-keyguard")
    time.sleep(1)


def check_device_ohca(device):
    return False


def check_device_name(device, kit, step="setup"):
    kit_name = kit.__class__.__name__
    kit_device_name = getattr(kit, "device_name", None)
    device_name = device.get("name")
    if kit_device_name and device_name and \
            kit_device_name != device_name:
        return False
    if kit_device_name and device_name:
        LOG.debug("Do kit:%s %s for device:%s", kit_name, step, device_name)
    else:
        LOG.debug("Do kit:%s %s", kit_name, step)
    return True


def check_device_env_index(device, kit):
    if not hasattr(device, "env_index"):
        return True
    kit_device_index_list = getattr(kit, "env_index_list", None)
    env_index = device.get("env_index")
    if kit_device_index_list and env_index \
            and len(kit_device_index_list) > 0 \
            and env_index not in kit_device_index_list:
        return False
    return True


def do_module_kit_setup(request, kits):
    tf_kits = request.get_tf_kits()
    if tf_kits:
        kits.extend(init_kit_instances(tf_kits))
    kit_setup(request, kits, ConfigConst.module_kits)


def do_module_kit_teardown(request):
    kit_teardown(request, ConfigConst.module_kits)


def do_common_module_kit_setup(request, kits):
    kit_setup(request, kits, ConfigConst.common_module_kits)


def do_common_module_kit_teardown(request):
    try:
        kit_teardown(request, ConfigConst.common_module_kits)
    except Exception as e:
        LOG.error("common module kit teardown error: {}".format(e))


def get_kit_instances(json_config, resource_path="", testcases_path=""):
    if not isinstance(json_config, JsonParser):
        return []
    return init_kit_instances(json_config.config.kits, resource_path, testcases_path)


def init_kit_instances(kits, resource_path="", testcases_path=""):
    kit_instances = []
    for kit in kits:
        kit["paths"] = [resource_path, testcases_path]
        kit_type = kit.get("type", "")
        device_name = kit.get("device_name", None)
        plugin = get_plugin(plugin_type=Plugin.TEST_KIT, plugin_id=kit_type)
        if plugin:
            test_kit_instance = plugin[0].__class__()
            test_kit_instance.__check_config__(kit)
            setattr(test_kit_instance, "device_name", device_name)
            kit_instances.append(test_kit_instance)
        else:
            raise ParamError(ErrorMessage.Common.Code_0101003.format(kit_type))
    return kit_instances


def kit_setup(request, kits, kit_type):
    devices = request.get_devices()
    if not devices or not kits:
        return
    for device in devices:
        setattr(device, kit_type, [])
        kit_name = ""
        run_flag = False
        for kit in kits:
            kit_name = kit.__class__.__name__
            if not Context.is_executing():
                raise ExecuteTerminate()
            if not check_device_env_index(device, kit):
                continue
            if check_device_name(device, kit):
                run_flag = True
                kit_copy = copy.deepcopy(kit)
                module_kits = getattr(device, kit_type)
                module_kits.append(kit_copy)
                kit_copy.__setup__(device, request=request)
        if not run_flag:
            err_msg = ErrorMessage.Common.Code_0101004.format(kit_name)
            LOG.error(err_msg)
            raise ParamError(err_msg)


def kit_teardown(request, kit_type):
    devices = request.get_devices()
    if not devices:
        return
    for device in devices:
        for kit in getattr(device, kit_type, []):
            if check_device_name(device, kit, step="teardown"):
                kit.__teardown__(device)
        setattr(device, kit_type, [])
