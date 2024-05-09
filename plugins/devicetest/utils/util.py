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
import os
import re
import secrets
import socket
import sys

from xdevice import calculate_elapsed_time
from xdevice import get_decode
from xdevice import ParamError
from xdevice import DeviceConnectorType

from devicetest.core.error_message import ErrorMessage
from devicetest.core.exception import DeviceTestError
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
        error_msg = "Can't load file {}".format(file_abs_path)
        log.error(error_msg, is_traceback=True)
        raise ImportError(error_msg) from exception
    return getattr(sys.modules[file_base_name], file_base_name)


def get_forward_ports(self=None):
    try:
        ports_list = []
        if hasattr(self, "is_oh") or self.usb_type == DeviceConnectorType.hdc:
            # get hdc
            cmd = "fport ls"
        else:
            cmd = "forward --list"
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
        log.error(ErrorMessage.Error_01208.Message.en,
                  error_no=ErrorMessage.Error_01208.Code)
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


def get_forward_port(self, host=None, port=None):
    try:
        ports_list = get_forward_ports(self)

        port = 9999 - secrets.randbelow(99)
        cnt = 0
        while cnt < 10 and port > 1024:
            if port not in ports_list and is_port_idle(host, port):
                cnt += 1
                break

            port -= 1
        return port
    except Exception as error:
        log.error(ErrorMessage.Error_01208.Message.en,
                  error_no=ErrorMessage.Error_01208.Code)
        raise DeviceTestError(ErrorMessage.Error_01208.Topic) from error


def get_local_ip_address():
    """
    查询本机ip地址
    :return: ip
    """
    ip = "127.0.0.1"
    return ip


def calculate_execution_time(begin, end):
    """计算时间间隔
    Args:
        begin: datetime, begin time
        end  : datetime, end time
    Returns:
        elapsed time description
    """
    return calculate_elapsed_time(begin, end)


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
