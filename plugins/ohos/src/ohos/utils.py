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
import os
from typing import List, Tuple
from xml.etree import ElementTree

from ohos.constants import Constant
from xdevice import DataHelper
from xdevice import FilePermission
from xdevice import Request
from xdevice import TestDescription
from xdevice import Variables
from xdevice import platform_logger

__all__ = [
    "parse_line_key_value", "parse_strings_key_value", "get_ta_class", "group_list",
    "print_not_exist_class", "is_rpc_socket_running", "dump_pid_info", "modify_class_and_notclass", "build_tests_dict",
    "build_new_fault_case", "setup_teardown", "parse_and_modify_report", "build_xml", "is_rpc_unix_socket_running"
]
LOG = platform_logger("Utils")


def parse_line_key_value(line):
    """parse line which should format as 'key = value'"""
    param = {}
    if "=" in line:
        arr = line.split("=")
        if len(arr) == 2:
            param.setdefault(arr[0].strip(), arr[1].strip())
    return param


def parse_strings_key_value(in_str):
    """parse string which should format as 'key = value'"""
    is_param, params = False, {}
    for line in in_str.split("\n"):
        if Constant.PRODUCT_PARAMS_START in line:
            is_param = True
        elif Constant.PRODUCT_PARAMS_END in line:
            is_param = False
        if is_param:
            params.update(parse_line_key_value(line))
    return params


def modify_class_and_notclass(request: Request, _class: list = None, notclass: list = None):
    if _class is None:
        _class = []
    if notclass is None:
        notclass = []
    config = request.config
    test_args = config.testargs
    LOG.info("old test args {}".format(test_args))
    test_args.update({"class": _class})
    test_args.update({"notClass": notclass})
    LOG.info("new test args {}".format(test_args))


def get_ta_class(driver, request: Request):
    """
    all_tests         class       not_class   actual_run
    [1, 2, 3, 4, 5]   [1, 2, 3]   []          [1, 2, 3]
    [1, 2, 3, 4, 5]   []          [4, 5]      [1, 2, 3]
    """
    ta_class = request.get_ta_class()
    ta_not_class = request.get_ta_not_class()
    # 若指定了要运行的用例，可直接运行
    if ta_class:
        return list(set(ta_class))
    # 若指定了不要运行的用例，先运行dryrun获取用例全集，再获取要运行的用例
    if not ta_not_class or not getattr(driver, "collect_test_to_run", None):
        return []
    set_ta_not_class = set(ta_not_class)
    # 过滤项未包含“#”，表示按测试套进行过滤
    ignore_test_suites = [i for i in set_ta_not_class if "#" not in i]

    all_tests = []
    dry_run_tests = driver.collect_test_to_run() or []
    for test in dry_run_tests:
        class_name, test_name = test.class_name, test.test_name
        if class_name and test_name and class_name not in ignore_test_suites:
            all_tests.append(f"{class_name}#{test_name}")
    return list(set(all_tests) - set_ta_not_class)


def group_list(lst: List, size: int = 0):
    """对列表进行分组
    lst : list, 待分组的列表
    size: int , 分组大小
    """
    if size <= 0:
        size = Variables.config.get_batch_run_size()
    lst_len, results = len(lst), []
    for i in range(0, lst_len, size):
        if i + size > lst_len:
            results.append(lst[i:])
        else:
            results.append(lst[i:i + size])
    return results


def print_not_exist_class(ta_class: List[str], dry_run_tests: List[TestDescription]):
    """打印通过class参数配置的，而dryRun未收集到的用例"""
    set_ta_class, set_dry_run_tests = set(ta_class), set()
    if not set_ta_class or not dry_run_tests:
        return
    for test in dry_run_tests:
        class_name, test_name = test.class_name, test.test_name
        if class_name and test_name:
            set_dry_run_tests.add(class_name)
            set_dry_run_tests.add(f"{class_name}#{test_name}")
    result = list(set_ta_class - set_dry_run_tests)
    if result:
        LOG.info(f"these suites or tests may not exist! suites or tests: {result}")


def is_rpc_socket_running(device, port: int, check_server: bool = True, is_print: bool = True) -> bool:
    if not device.is_root:
        return True
    out = device.execute_shell_command("netstat -atn | grep :{}".format(port))
    if is_print:
        device.log.debug(out)
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


def is_rpc_unix_socket_running(device, unix_socket_name: str, is_print: bool = True) -> bool:
    if not device.is_root:
        return True
    out = device.execute_shell_command("cat /proc/net/unix | grep {}".format(unix_socket_name))
    if is_print:
        device.log.debug(out)
    if out:
        out = out.split("\n")
        for data in out:
            if unix_socket_name in data:
                return True
    return False


def dump_pid_info(device, pid: int, name: str):
    try:
        path = os.path.join(device.get_device_report_path(), "log", "pid_info")
        if not os.path.exists(path):
            os.makedirs(path)
        file_path = os.path.join(path, "{}_pid_info_{}.txt".format(name, pid))
        pid_info_file = os.open(file_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, FilePermission.mode_755)
        ret = device.execute_shell_command("dumpcatcher -p {}".format(pid))
        with os.fdopen(pid_info_file, "a") as pid_info_file_pipe:
            pid_info_file_pipe.write(ret)
    except Exception as e:
        device.log.error("Dump {} pid info fail. Error: {}".format(pid, e))


def build_tests_dict(tests: list) -> Tuple[dict, list]:
    tests_dict = {}
    case_list = []
    for test in tests:
        test_item = test.split("#")
        if len(test_item) < 2:
            continue
        case_list.append(test)
        if test_item[0] not in tests_dict:
            tests_dict[test_item[0]] = []
        tests_dict[test_item[0]].append(TestDescription(test_item[0], test_item[1]))
    return tests_dict, case_list


def build_new_fault_case(fault_case: list, case_list: list) -> list:
    new_fault_case = []
    for test in fault_case:
        faults = test.get("faults", [])
        class_case = [case for case in case_list if case.split("#")[2:] == faults]

        current_tests_dict = {}
        for case in class_case:
            test_item = case.split("#")
            if len(test_item) >= 2:
                if test_item[0] not in current_tests_dict:
                    current_tests_dict[test_item[0]] = []
                current_tests_dict[test_item[0]].append(TestDescription(test_item[0], test_item[1]))

        new_fault_case.append({
            "class": ["#".join(case.split("#")[:2]) for case in class_case],
            "faults": faults,
            "tests_dict": current_tests_dict
        })
        case_list = [case for case in case_list if case not in class_case]
    return new_fault_case


class setup_teardown:

    def __init__(self, device, kit, **kwargs):
        self.device = device
        self.kit = kit
        self.kwargs = kwargs

    def __enter__(self):
        self.kit.__setup__(self.device, **self.kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.kit.__teardown__(self.device)


def parse_and_modify_report(result_file: str, fault_name: str, elements: list):
    if not os.path.exists(result_file):
        return
    element = DataHelper.parse_data_report(result_file)
    os.remove(result_file)
    for testsuite in element.findall('testsuite'):
        testsuite.set('name', testsuite.get('name') + fault_name)
    for testcase in element.findall('.//testcase'):
        testcase.set('name', testcase.get('name') + fault_name)
    elements.append(element)


def build_xml(result_file: str, elements: list):
    if not elements:
        return
    target_element = elements.pop(0)
    for element in elements:
        DataHelper.merge_result_xml(element, target_element)

    tree = ElementTree.ElementTree(target_element)
    tree.write(result_file, encoding="UTF-8", xml_declaration=True, short_empty_elements=True)
    LOG.info("Generate data report: {}".format(result_file))
