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

import importlib
import hashlib
import os
import platform
import re
import secrets
import site
import socket
import subprocess
import sys

from xdevice import get_decode
from xdevice import ParamError
from xdevice import DeviceConnectorType

from devicetest.core.exception import DeviceTestError
from devicetest.core.exception import ModuleNotAttributeError
from devicetest.error import ErrorCategory
from devicetest.error import ErrorMessage
from devicetest.log.logger import DeviceTestLog as log


def clean_sys_resource(file_path=None, file_base_name=None):
    """
    clean sys.path/sys.modules resource
    :param file_path: sys path
    :param file_base_name: module name
    :return: None
    """
    if file_path in sys.path:
        sys.path.remove(file_path)

    if file_base_name in sys.modules:
        del sys.modules[file_base_name]


def get_base_name(file_abs_path, is_abs_name=False):
    """
    Args:
        file_abs_path: str , file path
        is_abs_name  : bool,
    Returns:
        file base name
    Example:
        input: D:/xdevice/decc.py
        if is_abs_name return: D:/xdevice/decc, else return: decc
    """
    if isinstance(file_abs_path, str):
        base_name = file_abs_path if is_abs_name else os.path.basename(
            file_abs_path)
        file_base_name, _ = os.path.splitext(base_name)
        return file_base_name
    return None


def get_dir_path(file_path):
    if isinstance(file_path, str):
        if os.path.exists(file_path):
            return os.path.dirname(file_path)
    return None


def import_from_file(file_path, file_base_name):
    if file_path in sys.path:
        sys.path.remove(file_path)

    sys.path.insert(0, file_path)
    if file_base_name in sys.modules:
        del sys.modules[file_base_name]

    try:
        importlib.import_module(file_base_name)
    except Exception as exception:
        file_abs_path = os.path.join(file_path, file_base_name)
        error_msg = ErrorMessage.TestCase.Code_0203001.format(file_abs_path, exception)
        log.error(error_msg, is_traceback=True)
        raise ImportError(error_msg) from exception
    if not hasattr(sys.modules.get(file_base_name), file_base_name):
        raise ModuleNotAttributeError("File name and class name do not match")
    return getattr(sys.modules[file_base_name], file_base_name)


def get_forward_ports(self=None):
    try:
        ports_list = []
        cmd = "fport ls"
        out = get_decode(self.connector_command(cmd)).strip()
        clean_lines = out.split('\n')
        for line_text in clean_lines:
            # clear reverse port first  Example: 'tcp:8011 tcp:9963'     [Reverse]
            if "Reverse" in line_text and "fport" in cmd:
                connector_tokens = line_text.split()
                self.connector_command(["fport", "rm",
                                        connector_tokens[0].replace("'", ""),
                                        connector_tokens[1].replace("'", "")])
                continue
            connector_tokens = line_text.split("tcp:")
            if len(connector_tokens) != 3:
                continue
            ports_list.append(int(connector_tokens[1]))
        return ports_list
    except Exception:
        log.error(ErrorMessage.Common.Code_0201005)
        return []


def is_port_idle(host: str = "127.0.0.1", port: int = None) -> bool:
    """端口是否空闲"""
    s = None
    is_idle = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect((host, port))
    except Exception:
        # 已知会抛出ConnectionRefusedError和TimeoutError两种
        is_idle = True
    finally:
        if s is not None:
            s.close()
    return is_idle


def get_forward_port(self, host: str = None, port: int = None, filter_ports: list = None):
    if filter_ports is None:
        filter_ports = []
    try:
        ports_list = get_forward_ports(self)

        port = 9999 - secrets.randbelow(99)
        cnt = 0
        while cnt < 10 and port > 1024:
            if port not in filter_ports and port not in ports_list and is_port_idle(host, port):
                cnt += 1
                break

            port -= 1
        return port
    except Exception as error:
        err_msg = ErrorMessage.Common.Code_0201005
        log.error(err_msg)
        raise DeviceTestError(err_msg) from error


def get_local_ip_address():
    """
    查询本机ip地址
    :return: ip
    """
    ip = "127.0.0.1"
    return ip


def compare_version(version, base_version: tuple, rex: str):
    """比较两个版本号的大小,若version版本大于等于base_version,返回True
    Args:
        version: str, version
        rex: version style rex
        base_version: list, base_version
    Example:
        version: "4.0.0.1" base_version:[4.0.0.0]
        if version bigger than base_version or equal to base_version, return True, else return False
    """
    version = version.strip()
    if re.match(rex, version):
        version = tuple(version.split("."))
        if version > base_version:
            return True
    else:
        return True
    return False


def extract_version(version_str: str):
    """
    获取版本
    :param version_str: 版本信息 ALN-AL00 5.0.0.26(SP1C00E25R4P5log)
    :return: 5.0.0.26
    """
    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version_str)
    if match:
        return match.group(1)
    return None


def compare_versions_by_product(version1: str, version2: str):
    """
    比较两个版本号
    :param version1: 5.0.0.26
    :param version2: 5.0.0.23
    :return:
    """
    version1 = extract_version(version1)
    version2 = extract_version(version2)
    v1 = tuple(map(int, version1.split('.')))
    v2 = tuple(map(int, version2.split('.')))
    if v1 > v2:
        return True
    else:
        return False


class DeviceFileUtils:
    @staticmethod
    def check_remote_file_is_exist(_ad, remote_file):
        # test -f remotepath judge file exists.
        # if exist,return 0,else return None
        # 判断设备中文件是否存在
        ret = _ad.execute_shell_command("test -f %s && echo 0" % remote_file)
        if ret != "" \
                and len(str(ret).split()) \
                != 0 and str(ret).split()[0] == "0":
            return True
        return False

    @staticmethod
    def check_remote_dict_is_exist(_ad, remote_file):
        # test -f remotepath judge folder exists.
        # if exist,return 0,else return None
        # 判断设备中文件夹是否存在
        ret = _ad.execute_shell_command(
            "test -d {} && echo 0".format(remote_file))
        if ret != "" \
                and len(str(ret).split()) != 0 and str(ret).split()[0] == "0":
            return True
        return False


def compare_text(text, expect_text, fuzzy):
    """支持多种匹配方式的文本匹配"""
    if fuzzy is None or fuzzy.startswith("equal"):
        result = (expect_text == text)
    elif fuzzy == "starts_with":
        result = text.startswith(expect_text)
    elif fuzzy == "ends_with":
        result = text.endswith(expect_text)
    elif fuzzy == "contains":
        result = expect_text in text
    elif fuzzy == "regexp":
        result = re.search(expect_text, text)
        result = False if result is None else True
    else:
        raise ParamError("expected [equal, starts_with, ends_with, contains], get [{}]".format(fuzzy))
    return result


def get_process_pid(device, process_name):
    cmd = "ps -ef | grep '{}'".format(process_name)
    ret = device.execute_shell_command(cmd)
    ret = ret.strip()
    pids = ret.split("\n")
    for pid in pids:
        if "grep" not in pid:
            pid = pid.split()
            return pid[1]
    return None


def check_port_state(port: int = None) -> None:
    """查看端口状态"""
    try:
        log.debug("##########port state##########")
        sys_type = platform.system()
        if sys_type == "Linux" or sys_type == "Darwin":
            cmd = "lsof -i:{}".format(port)
            out = shell_command(cmd)
            log.debug(out)
        else:
            out = shell_command("netstat -aon", "findstr :{}".format(port))
            log.debug(out)
            results = out.strip("\r\n")
            if results:
                results = results.split("\r\n")
            for result in results:
                items = result.split()
                if items[0] == "TCP" and items[-2] == "LISTENING":
                    out = shell_command("tasklist", "findstr {}".format(items[-1]))
                    log.debug(out)
        log.debug("##########port state##########")
    except Exception as e:
        log.error("check port state error, reason: {}".format(e))


def shell_command(cmd: str, findstr: str = "") -> str:
    command = cmd.split(" ")
    first_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    if findstr:
        findstr_command = findstr.split(" ")
        findstr_process = subprocess.Popen(findstr_command, stdin=first_process.stdout,
                                           stderr=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           shell=False)
        out, _ = findstr_process.communicate(timeout=10)
    else:
        out, _ = first_process.communicate(timeout=10)
    out = out.decode("utf-8")
    return out


def check_device_file_md5(device, pc_file: str, device_file: str) -> bool:
    if not os.path.isfile(pc_file):
        raise FileNotFoundError(ErrorMessage.Common.Code_0201001.format(ErrorCategory.Environment, pc_file))
    _, local_file_name = os.path.split(pc_file)
    device_md5 = device.execute_shell_command(
        "md5sum {}".format(device_file)).split()[0].strip()
    device.log.debug("device {} md5: {}".format(local_file_name, device_md5))
    with open(pc_file, "rb") as f:
        data = f.read()
        md5hash = hashlib.md5(data)
        local_md5 = md5hash.hexdigest()
    device.log.debug("local {} md5: {}".format(local_file_name, local_md5))
    return True if device_md5 == local_md5 else False


def is_standard_lib(file_path):
    """Check if the file is part of the standard library."""
    std_lib_path = os.path.join(sys.base_prefix, 'lib')
    return file_path.startswith(std_lib_path)


def is_third_party_lib(file_path):
    """Check if the file is part of a third-party library."""
    site_packages = [os.path.join(sys.prefix, 'lib', 'site-packages')]
    if hasattr(sys, 'real_prefix'):  # This means we are in a virtual environment
        site_packages.append(os.path.join(sys.real_prefix, 'lib', 'site-packages'))
    site_packages.append(site.getusersitepackages())
    return any(file_path.startswith(site_package) for site_package in site_packages)


def extract_file_method_code(stack_line):
    """Extract the Python file name and the method after 'in' from a stack trace line."""
    match = re.search(r'File "(.*?)", line \d+, in (.+)', stack_line)
    if match:
        file_name = match.group(1).split(os.sep)[-1]
        method_name = match.group(2).strip()
        code_line = stack_line.split('\n')[-2].strip()
        return file_name, method_name, code_line
    return None, None, None
