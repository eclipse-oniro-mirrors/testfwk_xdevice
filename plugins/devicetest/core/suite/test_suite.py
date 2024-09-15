#!/usr/bin/python3.4
# coding=utf-8
#

# Copyright (C) 2016 Huawei Technologies Co., HUTAF xDevice
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.

import copy
import sys
import os
import traceback
from typing import List, Tuple

from xdevice import ConfigConst
from xdevice import calculate_elapsed_time
from xdevice import get_cst_time
from xdevice import get_file_absolute_path
from xdevice import FilePermission
from xdevice import CaseEnd
from xdevice import Binder
from xdevice import Variables

from devicetest.core.constants import RunResult
from devicetest.core.constants import FileAttribute
from devicetest.core.test_case import UpdateStep
from devicetest.core.variables import CurCase
from devicetest.core.variables import DeccVariable
from devicetest.core.variables import ProjectVariables
from devicetest.error import ErrorMessage
from devicetest.report.generation import add_log_caching_handler
from devicetest.report.generation import del_log_caching_handler
from devicetest.report.generation import get_caching_logs
from devicetest.report.generation import generate_report
from devicetest.utils.util import get_base_name
from devicetest.utils.util import get_dir_path
from devicetest.utils.util import import_from_file


class TestSuite:
    """Base class for all test classes to inherit from.

    This class gets all the controller objects from test_runner and executes
    the test cases requested within itself.

    """

    def __init__(self, configs, path):
        self.configs = configs
        self.devices = []
        self.device1 = None
        self.device2 = None
        # 透传的参数
        self.pass_through = Variables.config.pass_through
        self.set_devices(self.configs["devices"])
        self.path = path
        self.log = self.configs["log"]
        self.error_msg = ''
        self.trace_info = ''
        self.case_list: List[Tuple[str, str]] = []
        self.case_result = dict()
        self.suite_name = self.configs.get("suite_name")
        # 白名单用例
        self.white_case_list = []
        # 黑名单用例
        self.black_case_list = []
        # 初始化透传参数的列表
        self.arg_list = dict()
        self.app_result_info = dict()
        self._test_args_para_parse(self.configs["testargs"])
        # 往DeviceTest的用例中注入logger并防止重复初始化测试套级别的变量
        self.inject_logger = None
        self.cur_case = None
        # device log
        self.device_log = dict()
        self.hilog = dict()
        self.log_proc = dict()
        self.hilog_proc = dict()

        self.suite_case_results = []
        self.suite_report_path = ""
        self._case_log_buffer_hdl = None

        # device录屏截图属性
        self.devices_media = dict()

        self._repeat = self.configs.get("request").config.repeat
        self._repeat_round = self.configs.get("request").get_repeat_round()
        self._round_folder = f"round{self._repeat_round}" if self._repeat > 1 else ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def _device_close(self):
        self.log.debug("Start device close")
        for device in self.devices:
            device.close()
        self.log.debug("Finish device close.")

    def run(self):
        self._init_devicetest()
        report_path = os.path.join("details", self._round_folder, self.suite_name, self.suite_name + ".html")
        start_time = get_cst_time()
        # 记录录屏和截图属性
        self._get_screenrecorder_and_screenshot()
        # 开始收集测试套（setup和teardown）的运行日志
        suite_log_buffer_hdl = add_log_caching_handler()
        try:
            self.cur_case.set_suite_instance(self)
            # 1.先判断是否在json中指定，否则先收集当前文件夹下所有testcase得到run_list
            for case_path in self._get_case_list(self.path):
                case_name = get_base_name(case_path)
                if (self.black_case_list and case_name in self.black_case_list) \
                        or (self.white_case_list and case_name not in self.white_case_list):
                    self.log.warning("case name {} is in black list or not in white list, ignored".format(case_name))
                    continue
                self.case_list.append((case_name, case_path))
            self.log.debug("Execute test case list: {}".format(self.case_list))
            # 2.先执行self.setup
            if self.run_setup():
                # 在运行测试套子用例前，停止收集测试套setup步骤的运行日志
                del_log_caching_handler(suite_log_buffer_hdl)
                # 3.依次执行所有的run_list
                # 开始收集测试套子用例的运行日志
                self._case_log_buffer_hdl = add_log_caching_handler()
                total_case_num = len(self.case_list)
                for index, case in enumerate(self.case_list, 1):
                    self._reset_screenrecorder_and_screenshot()
                    self.log.info("[{} / {}] Executing suite case: {}".format(index, total_case_num, case[1]))
                    self.run_one_test_case(case)
                # 停止收集测试套子用例的运行日志
                del_log_caching_handler(self._case_log_buffer_hdl)
            else:
                self.error_msg = ErrorMessage.TestCase.Code_0203017.format(self.error_msg)
                for case in self.case_list:
                    self.case_result[case[0]] = {
                        "result": RunResult.BLOCKED,
                        "error": self.error_msg,
                        "run_time": 0,
                        "report": report_path
                    }
            self._case_log_buffer_hdl = None
            # 在运行测试套子用例后，重新开始收集测试套teardown步骤的运行日志
            add_log_caching_handler(buffer_hdl=suite_log_buffer_hdl)
        finally:
            # 4.执行self.teardown
            self.run_teardown()
            self.cur_case.set_suite_instance(None)

        steps = self.cur_case.get_steps_info()
        # 停止收集测试套（setup和teardown）的运行日志
        del_log_caching_handler(suite_log_buffer_hdl)
        if suite_log_buffer_hdl is None:
            return
        # 生成测试套的报告
        self.log.info("generate suite report")
        end_time = get_cst_time()
        environment = self.configs.get("request").config.environment
        suite_info = {
            "name": self.suite_name,
            "result": "",
            "begin": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'elapsed': calculate_elapsed_time(start_time, end_time),
            "error": "",
            "logs": "",
            "subcases": self.suite_case_results,
            "devices": [] if environment is None else environment.get_description(),
            "steps": steps
        }
        log_content = {
            "content": get_caching_logs(suite_log_buffer_hdl)
        }
        to_file = os.path.join(self.get_case_report_path(), report_path)
        generate_report(to_file, case=suite_info, logs=log_content)
        del suite_log_buffer_hdl

        # 往结果xml添加测试套的报告路径
        self.suite_report_path = report_path
        steps.clear()
        DeccVariable.reset()

    def setup(self):
        """Setup function that will be called before executing any test suite.
        Implementation is optional.
        """
        pass

    def setup_start(self):
        """
        setup_start function that will be called after setup function.
        Implementation is optional.
        """
        pass

    def setup_end(self):
        """
        setup_end function that will be called after setup function.
        Implementation is optional.
        """
        pass

    def teardown(self):
        """Teardown function that will be called after all the selected test
        suite.
        Implementation is optional.
        """
        pass

    def teardown_start(self):
        """
        teardown_start function that will be called before Teardown function.
        Implementation is optional.
        """
        pass

    def teardown_end(self):
        """
        teardown_end function that will be called after Teardown function.
        Implementation is optional.
        """
        pass

    def get_params(self):
        return self.arg_list

    def set_devices(self, devices):
        self.devices = devices
        if not devices:
            return

        try:
            for num, _ad in enumerate(self.devices, 1):
                if not hasattr(_ad, "device_id") or not getattr(_ad, "device_id"):
                    setattr(_ad, "device_id", "device{}".format(num))
                # 兼容release2 增加id、serial
                setattr(_ad, "id", _ad.device_id)
                setattr(_ad, "serial", _ad.device_sn)
                setattr(self, _ad.device_id, _ad)
                setattr(self, "device{}".format(num), _ad)
        except Exception as error:
            self.log.error("Failed to initialize the device object in the "
                           "TestCase.", error_no="01218")
            raise error

    def _get_case_list(self, path):
        result = []
        if len(self.configs["suitecases"]) > 0:
            for _, case in enumerate(self.configs["suitecases"]):
                if os.path.exists(case):
                    case_path = case
                else:
                    case_path = get_file_absolute_path(case, [path,
                                                              self.configs["resource_path"],
                                                              self.configs["testcases_path"]])
                result.append(case_path)
        else:
            all_file_list = os.listdir(path)
            # 遍历该文件夹下的所有目录或者文件
            for file in all_file_list:
                filepath = os.path.join(path, file)
                # 如果是文件夹，递归调用函数
                if os.path.isdir(filepath):
                    result.extend(self._get_case_list(filepath))
                # 如果不是文件夹，保存文件路径及文件名
                elif os.path.isfile(filepath) and \
                        "__pycache__" not in filepath:
                    if file.startswith(FileAttribute.TESTCASE_PREFIX) and \
                            (file.endswith(FileAttribute.TESTCASE_POSFIX_PY) or
                             file.endswith(FileAttribute.TESTCASE_POSFIX_PYC) or
                             file.endswith(FileAttribute.TESTCASE_POSFIX_PYD)):
                        result.append(filepath)
        return result

    def _exec_func(self, func, *args):
        result = False
        try:
            func(*args)
        except Exception as exception:
            self.error_msg = str(exception)
            self.trace_info = traceback.format_exc()

            index = self.cur_case.step_index
            if index == -1:
                self.log.error(self.error_msg)
                self.log.error(self.trace_info)
            else:
                step_error_id = f'step_error_{index}'
                self.log.error(f'<span id="{step_error_id}">{self.error_msg}</span>')
                self.log.error(self.trace_info)
                _error = f'<a href="javascript:" onclick="gotoStep(\'{step_error_id}\')">{self.error_msg}</a>'
                UpdateStep(index, error=_error)
        else:
            result = True
        return result

    def run_setup(self):
        self.setup_start()
        self.log.info("**********SetUp Starts!")
        ret = self._exec_func(self.setup)
        self.log.info("**********SetUp Ends!")
        if ret:
            self.setup_end()
            return True
        self.log.info("SetUp Failed!")
        return False

    def run_one_test_case(self, case: Tuple[str, str]):
        case_name, case_path = case[0], case[1]
        start_time = get_cst_time()
        case_result = RunResult.FAILED
        test_cls_instance = None
        result_content = None   # 用例测试结果的拓展内容
        try:
            test_cls = import_from_file(get_dir_path(case_path), case_name)
            self.log.info("Success to import {}.".format(case_name))
            self._compatible_testcase(case_path, case_name)
            with test_cls(self.configs) as test_cls_instance:
                self.cur_case.set_case_instance(test_cls_instance)
                test_cls_instance.run()
            case_result, error_msg = test_cls_instance.result, test_cls_instance.error_msg
            result_content = getattr(test_cls_instance, "result_content", None)
        except Exception as e:
            error_msg = str(e)
            self.log.error("run case error! Exception: {}".format(e))
            self.log.error(traceback.format_exc())

        if test_cls_instance is None:
            case_result = RunResult.BLOCKED
        if test_cls_instance:
            try:
                del test_cls_instance
                self.log.debug("del test case instance success")
            except Exception as e:
                self.log.debug(traceback.format_exc())
                self.log.warning("del test case instance exception. Exception: {}".format(e))
        Binder.notify_stage(CaseEnd(case_name, case_result))

        end_time = get_cst_time()
        cost = int(round((end_time - start_time).total_seconds() * 1000))
        self.log.info("Executed case: {}, result: {}, cost time: {}ms".format(case_name, case_result, cost))
        self.case_result[case_name] = {
            "result": case_result, "error": error_msg,
            "run_time": cost, "report": "", "result_content": result_content}

        try:
            self._device_close()
        except Exception as e:
            self.log.error("stop catch device log error! {}".format(e))
            self.log.debug(traceback.format_exc())

        if self._case_log_buffer_hdl is None:
            return
        # 生成子用例的报告
        steps = self.cur_case.get_steps_info()
        base_info = {
            "name": case_name,
            "result": case_result,
            "begin": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            'elapsed': calculate_elapsed_time(start_time, end_time),
            "error": error_msg
        }
        case_info = copy.copy(base_info)
        case_info.update({
            "logs": "",
            "devices": [],
            "steps": steps
        })
        log_content = {
            "content": copy.copy(get_caching_logs(self._case_log_buffer_hdl))
        }
        case_html = case_name + ".html"
        report_path = os.path.join("details", self._round_folder, self.suite_name, case_html)
        to_file = os.path.join(self.configs.get("report_path"), report_path)
        generate_report(to_file, case=case_info, logs=log_content)
        base_info["report"] = case_html
        self.suite_case_results.append(base_info)
        # 清空日志缓存
        self._case_log_buffer_hdl.buffer.clear()
        steps.clear()
        # 往结果xml添加子用例的报告路径
        self.case_result[case_name]["report"] = report_path
        # 将用例实例对象和用例名置为空
        self.cur_case.set_case_instance(None)
        self.cur_case.set_name("")

    def run_teardown(self):
        self.log.info("**********TearDown Starts!")
        self.teardown_start()
        self._exec_func(self.teardown)
        self.teardown_end()
        self.log.info("**********TearDown Ends!")

    def _test_args_para_parse(self, paras):
        paras = dict(paras)
        for para_name in paras.keys():
            para_name = para_name.strip()
            para_values = paras.get(para_name, [])
            if para_name == "class":
                self.white_case_list.extend(para_values)
            elif para_name == "notClass":
                self.black_case_list.extend(para_values)
            elif para_name == "para":
                for arg in para_values:
                    key, value = arg.split("#")
                    self.arg_list[key] = value
            elif para_name == "deveco_planet_info":
                for app_info in para_values:
                    key, value = app_info.split("#")
                    if key == "task_type":
                        setattr(sys, "category", value)
                    else:
                        self.app_result_info[key] = value
                        setattr(sys, "app_result_info", self.app_result_info)
            else:
                continue

        self.configs["pass_through"] = self.pass_through
        self.configs["arg_list"] = self.arg_list

    def get_case_report_path(self):
        return self.configs["report_path"]

    def _compatible_testcase(self, case_path, case_name):
        DeccVariable.cur_case().set_name(case_name)
        project_var = ProjectVariables(self.inject_logger)
        project_var.execute_case_name = case_name
        project_var.cur_case_full_path = case_path
        project_var.task_report_dir = self.get_case_report_path()
        self.configs["project"] = project_var

    def _init_devicetest(self):
        self.cur_case = CurCase(self.log)
        self.cur_case.suite_name = self.suite_name
        self.cur_case.set_case_screenshot_dir(
            None, self.get_case_report_path(), None,
            repeat=self._repeat, repeat_round=self._repeat_round)
        DeccVariable.set_cur_case_obj(self.cur_case)
