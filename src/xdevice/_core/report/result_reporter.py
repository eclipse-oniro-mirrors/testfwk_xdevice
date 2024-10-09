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

import collections
import copy
import json
import os
import platform
import re
import shutil
import time
import stat
from ast import literal_eval
from importlib import util
from xml.etree import ElementTree

from _core.interface import IReporter
from _core.plugin import Plugin
from _core.constants import CaseResult
from _core.constants import DeviceProperties
from _core.constants import ModeType
from _core.constants import TestType
from _core.constants import FilePermission
from _core.logger import platform_logger
from _core.exception import ParamError
from _core.utils import calculate_elapsed_time
from _core.utils import calculate_percent
from _core.utils import copy_folder
from _core.utils import get_filename_extension
from _core.utils import show_current_environment
from _core.report.encrypt import check_pub_key_exist
from _core.report.encrypt import do_rsa_encrypt
from _core.report.reporter_helper import DataHelper
from _core.report.reporter_helper import ExecInfo
from _core.report.reporter_helper import ReportConstant
from _core.report.repeater_helper import RepeatHelper
from _core.variables import Variables
from _core.context.center import Context
from _core.context.handler import get_case_result
from _core.context.upload import Uploader

LOG = platform_logger("ResultReporter")


class ResultSummary:

    def __init__(self):
        self.modules = 0
        self.repeat = 1
        self.runmodules = 0
        self.tests = 0
        self.passed = 0
        self.failed = 0
        self.blocked = 0
        self.ignored = 0
        self.unavailable = 0
        self.devices = []
        self.__module_list = []

    def get_data(self):
        self.__module_list.clear()
        LOG.info(f"Test Summary: modules: {self.modules}, repeat: {self.repeat}, run modules: {self.runmodules}, "
                 f"total: {self.tests}, passed: {self.passed}, failed: {self.failed}, "
                 f"blocked: {self.blocked}, ignored: {self.ignored}, unavailable: {self.unavailable}")
        data = {
            "modules": self.modules,
            "repeat": self.repeat,
            "runmodules": self.runmodules,
            "tests": self.tests,
            "passed": self.passed,
            "failed": self.failed,
            "blocked": self.blocked,
            "ignored": self.ignored,
            "unavailable": self.unavailable
        }
        return data

    def get_devices(self):
        return self.devices

    def add_module(self, name):
        if name not in self.__module_list:
            self.__module_list.append(name)
            self.modules += 1


@Plugin(type=Plugin.REPORTER, id=TestType.all)
class ResultReporter(IReporter):

    def __init__(self):
        self.report_path = None
        self.task_info = None
        self.summary_data_path = None
        self.summary_data_str = ""
        self.exec_info = None
        self.data_helper = None
        self.repeat_helper = None
        self.summary = ResultSummary()

        # task_record.info数据
        self._failed_cases = []
        self.record_params = {}
        self.record_reports = {}

    def __generate_reports__(self, report_path, **kwargs):
        LOG.info("")
        LOG.info("**************************************************")
        LOG.info("************** Start generate reports ************")
        LOG.info("**************************************************")
        LOG.info("")

        if self._check_params(report_path, **kwargs):
            # generate data report
            self._generate_data_report()

            # generate vision reports
            self._generate_test_report()

            # generate task info record
            self._generate_task_record()

            # generate summary ini
            self._generate_summary()

            # copy reports to reports/latest folder
            self._copy_report()

            self._transact_all()

        LOG.info("")
        LOG.info("**************************************************")
        LOG.info("************** Ended generate reports ************")
        LOG.info("**************************************************")
        LOG.info("")
        show_current_environment()

    def _check_params(self, report_path, **kwargs):
        task_info = kwargs.get("task_info", "")
        if not report_path:
            LOG.error("Report path is wrong", error_no="00440",
                      ReportPath=report_path)
            return False
        if not task_info or not isinstance(task_info, ExecInfo):
            LOG.error("Task info is wrong", error_no="00441",
                      TaskInfo=task_info)
            return False

        os.makedirs(report_path, exist_ok=True)
        self.report_path = report_path
        self.task_info = task_info
        self.summary_data_path = os.path.join(
            self.report_path, ReportConstant.summary_data_report)
        self.exec_info = task_info
        self.data_helper = DataHelper()
        self.repeat_helper = RepeatHelper(report_path)
        return True

    def _generate_test_report(self):
        report_template = os.path.join(Variables.res_dir, "template")
        missing_files = []
        for source in ReportConstant.new_template_sources:
            file = source.get("file")
            to_path = os.path.join(report_template, file)
            if not os.path.exists(to_path):
                missing_files.append(to_path)
        # 若新报告模板文件缺失，则使用旧报告模板生成测试报告
        if len(missing_files) > 0:
            self._generate_vision_reports()
            return

        copy_folder(report_template, self.report_path)
        temp_file_report_html = os.path.join(self.report_path, "report.html")
        if os.path.exists(temp_file_report_html):
            os.remove(temp_file_report_html)
        content = json.dumps(self._get_summary_data(), separators=(",", ":"))
        data_js = os.path.join(self.report_path, "static", "data.js")
        data_fd = os.open(data_js, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
        with os.fdopen(data_fd, mode="w", encoding="utf-8") as jsf:
            jsf.write(f"window.reportData = {content}")
        test_report = os.path.join(self.report_path, ReportConstant.summary_vision_report).replace("\\", "/")
        LOG.info(f"Log path: {self.report_path}")
        LOG.info(f"Generate test report: file:///{test_report}")
        # 重新生成对象，避免在retry场景数据统计有误
        self.summary = ResultSummary()

    def _get_summary_data(self):
        self.summary.repeat = self.task_info.repeat
        modules = []
        for data_report, _ in self.data_reports:
            if data_report.endswith(ReportConstant.summary_data_report):
                continue
            info = self._parse_module(data_report)
            if info is not None:
                modules.append(info)
        if self.summary.failed != 0 or self.summary.blocked != 0 or self.summary.unavailable != 0:
            if Context.get_scheduler():
                Context.get_scheduler().set_need_auto_retry(True)
        data = {
            "exec_info": self._get_exec_info(),
            "summary": self.summary.get_data(),
            "devices": self.summary.get_devices(),
            "modules": modules,
        }
        return data

    def _get_exec_info(self):
        start_time = self.task_info.test_time
        end_time = time.strftime(ReportConstant.time_format, time.localtime())
        test_time = "%s/ %s" % (start_time, end_time)
        execute_time = calculate_elapsed_time(
            time.mktime(time.strptime(start_time, ReportConstant.time_format)),
            time.mktime(time.strptime(end_time, ReportConstant.time_format)))
        host_info = platform.platform()
        device_name = getattr(self.task_info, ReportConstant.device_name, "None")
        device_type = getattr(self.task_info, ReportConstant.device_label, "None")
        platform_info = getattr(self.task_info, ReportConstant.platform, "None")
        test_type = getattr(self.task_info, ReportConstant.test_type, "None")

        # 为报告文件summary.ini提供数据
        exec_info = ExecInfo()
        exec_info.device_name = device_name
        exec_info.device_label = device_type
        exec_info.execute_time = execute_time
        exec_info.host_info = host_info
        exec_info.log_path = self.report_path
        exec_info.platform = platform_info
        exec_info.test_time = test_time
        exec_info.test_type = test_type
        self.exec_info = exec_info

        info = {
            "test_start": start_time,
            "test_end": end_time,
            "execute_time": execute_time,
            "test_type": test_type,
            "host_info": host_info,
            "logs": self._get_task_log()
        }
        return info

    def _parse_module(self, xml_file):
        """解析测试模块"""
        file_name = os.path.basename(xml_file)
        try:
            xml_file_open = os.open(xml_file, os.O_RDWR, stat.S_IWUSR | stat.S_IRUSR)
            with os.fdopen(xml_file_open, mode="r", encoding="utf-8") as file_handler:
                xml_str = file_handler.read()
            for char_index in range(32):
                if char_index in [10, 13]:
                    continue
                xml_str = xml_str.replace(chr(char_index), "")
            ele_module = ElementTree.fromstring(xml_str)
        except ElementTree.ParseError as e:
            LOG.error(f"parse result xml error! xml file {xml_file}")
            LOG.error(f"error message: {e}")
            return None
        module = ResultReporter._count_result(ele_module)
        # 当模块名为空或为AllTests，将模块名设为结果xml的文件名
        module_name = file_name[:-4] if module.name in ["", "AllTests"] else module.name.strip()
        suites = [self._parse_testsuite(ele_suite) for ele_suite in ele_module]

        # 为报告文件task_record.info提供数据
        self.record_reports.update({module_name: xml_file})
        if len(self._failed_cases) != 0:
            self.record_params.update({module_name: copy.copy(self._failed_cases)})
            self._failed_cases.clear()

        self.summary.add_module(module_name)
        self.summary.tests += module.tests
        self.summary.passed += module.passed
        self.summary.failed += module.failed
        self.summary.blocked += module.blocked
        self.summary.ignored += module.ignored
        if module.unavailable == 0:
            self.summary.runmodules += 1
        else:
            self.summary.unavailable += 1
        devices = self._parse_devices(ele_module)

        module_report, module_time = module.report, module.time
        if len(suites) == 1 and suites[0].get(ReportConstant.name) == module_name:
            report = suites[0].get(ReportConstant.report)
            if report != "":
                module_report = report
            module_time = suites[0].get(ReportConstant.time)
        repeat = int(ele_module.get(ReportConstant.repeat, "1"))
        if self.summary.repeat < repeat:
            self.summary.repeat = repeat
        repeat_round = int(ele_module.get(ReportConstant.round, "1"))
        test_type = ele_module.get(ReportConstant.test_type, "-")
        test_start = ele_module.get(ReportConstant.start_time, "-")
        test_end = ele_module.get(ReportConstant.end_time, "-")
        if test_start != "-" and test_end != "-":
            execute_time = calculate_elapsed_time(
                time.mktime(time.strptime(test_start, ReportConstant.time_format)),
                time.mktime(time.strptime(test_end, ReportConstant.time_format)))
        else:
            execute_time = calculate_elapsed_time(0, module_time)
        info = {
            "name": module_name,
            "report": module_report,
            "round": repeat_round,
            "test_type": test_type,
            "test_start": test_start,
            "test_end": test_end,
            "time": module_time,
            "execute_time": execute_time,
            "tests": module.tests,
            "passed": module.passed,
            "failed": module.failed,
            "blocked": module.blocked,
            "ignored": module.ignored,
            "unavailable": module.unavailable,
            "passingrate": calculate_percent(module.passed, module.tests),
            "error": ele_module.get(ReportConstant.message, ""),
            "logs": self._get_module_logs(module_name, repeat=repeat, repeat_round=repeat_round),
            "devices": devices,
            "suites": suites
        }
        return info

    def _parse_testsuite(self, ele_suite):
        """解析测试套"""
        suite = ResultReporter._count_result(ele_suite)
        cases = [self._parse_testcase(case) for case in ele_suite]
        info = {
            "name": suite.name,
            "report": suite.report,
            "time": suite.time,
            "tests": suite.tests,
            "passed": suite.passed,
            "failed": suite.failed,
            "blocked": suite.blocked,
            "ignored": suite.ignored,
            "passingrate": calculate_percent(suite.passed, suite.tests),
            "cases": cases
        }
        return info

    def _parse_testcase(self, ele_case):
        """解析测试用例"""
        name = ele_case.get(ReportConstant.name)
        class_name = ele_case.get(ReportConstant.class_name, "")
        result, error = get_case_result(ele_case)
        if result != CaseResult.passed:
            self._failed_cases.append(f"{class_name}#{name}")
        return [name, class_name, result, ResultReporter._parse_time(ele_case),
                error, ele_case.get(ReportConstant.report, "")]

    @staticmethod
    def _parse_time(ele):
        try:
            _time = float(ele.get(ReportConstant.time, "0"))
        except ValueError:
            _time = 0.0
            LOG.error("parse test time error, set it to 0.0")
        return _time

    def _parse_devices(self, ele_module):
        devices_str = ele_module.get(ReportConstant.devices, "")
        if devices_str == "":
            return []
        try:
            devices = literal_eval(devices_str)
        except SyntaxError:
            return []
        # 汇总测试设备信息
        for device in devices:
            device_sn = device.get(DeviceProperties.sn, "")
            temp = [d for d in self.summary.get_devices() if d.get(DeviceProperties.sn, "") == device_sn]
            if len(temp) != 0:
                continue
            self.summary.get_devices().append(device)
        return devices

    @staticmethod
    def _count_result(ele):
        name = ele.get(ReportConstant.name, "")
        report = ele.get(ReportConstant.report, "")
        _time = ResultReporter._parse_time(ele)
        tests = int(ele.get(ReportConstant.tests, "0"))
        failed = int(ele.get(ReportConstant.failures, "0"))
        disabled = ele.get(ReportConstant.disabled, "0")
        if disabled == "":
            disabled = "0"
        errors = ele.get(ReportConstant.errors, "0")
        if errors == "":
            errors = "0"
        blocked = int(disabled) + int(errors)
        ignored = int(ele.get(ReportConstant.ignored, "0"))
        unavailable = int(ele.get(ReportConstant.unavailable, "0"))

        tmp_pass = tests - failed - blocked - ignored
        passed = tmp_pass if tmp_pass > 0 else 0

        Result = collections.namedtuple(
            'Result',
            ['name', 'report', 'time', 'tests', 'passed', 'failed', 'blocked', 'ignored', 'unavailable'])
        return Result(name, report, _time, tests, passed, failed, blocked, ignored, unavailable)

    def _get_module_logs(self, module_name, repeat=1, repeat_round=1):
        """获取模块运行日志和设备日志
        注：黑盒用例的测试报告是单独生成的，而xts只有模块级的设备日志，无用例级日志，故本方法仅支持获取模块级的设备日志
        """
        device_log = {}
        round_folder = f"round{repeat_round}" if repeat > 1 else ""
        log_path = os.path.join(self.report_path, "log", round_folder, module_name)
        if not os.path.exists(log_path):
            return device_log
        module_log_uri = f"log/{round_folder}/{module_name}" if round_folder else f"log/{module_name}"
        for filename in os.listdir(log_path):
            file_link = f"{module_log_uri}/{filename}"
            file_path = os.path.join(log_path, filename)
            # 目录和模块运行日志，都提供链接
            if os.path.isdir(file_path) or filename.startswith(ReportConstant.module_run_log):
                device_log.setdefault(filename, file_link)
                continue
            # 是文件，仅提供模块级的设备日志链接
            # 测试套日志命名格式device_log_sn.log、测试套子用例日志命名格式device_log_case_sn.log，后者“_”大于2
            ret = re.fullmatch(r'(device_(?:hi)?log)_\S+\.log', filename)
            if ret is None or filename.count("_") > 2:
                continue
            device_log.setdefault(ret.group(1), file_link)
        return device_log

    def _get_task_log(self):
        log_path = os.path.join(self.report_path, "log")
        if not os.path.exists(log_path):
            return {}
        return {f: f"log/{f}" for f in os.listdir(log_path) if f.startswith(ReportConstant.task_run_log)}

    def _generate_data_report(self):
        # initial element
        test_suites_element = self.data_helper.initial_suites_element()

        # update test suites element
        update_flag = self._update_test_suites(test_suites_element)
        if not update_flag:
            return

        # generate report
        if not self._check_mode(ModeType.decc):
            self.data_helper.generate_report(test_suites_element,
                                             self.summary_data_path)

    def _update_test_suites(self, test_suites_element):
        # initial attributes for test suites element
        test_suites_attributes, need_update_attributes = \
            self._init_attributes()

        # get test suite elements that are children of test suites element
        modules = dict()
        test_suite_elements = []
        for data_report, module_name in self.data_reports:
            if data_report.endswith(ReportConstant.summary_data_report):
                continue
            root = self.data_helper.parse_data_report(data_report)
            self._parse_devices(root)
            if module_name == ReportConstant.empty_name:
                module_name = self._get_module_name(data_report, root)
            total = int(root.get(ReportConstant.tests, 0))
            if module_name not in modules.keys():
                modules[module_name] = list()
            modules[module_name].append(total)

            for child in root:
                child.tail = self.data_helper.LINE_BREAK_INDENT
                if not child.get(ReportConstant.module_name) or child.get(
                        ReportConstant.module_name) == \
                        ReportConstant.empty_name:
                    child.set(ReportConstant.module_name, module_name)
                self._check_tests_and_unavailable(child)
                # covert the status of "notrun" to "ignored"
                for element in child:
                    if element.get(ReportConstant.status, "") == \
                            ReportConstant.not_run:
                        ignored = int(child.get(ReportConstant.ignored, 0)) + 1
                        child.set(ReportConstant.ignored, "%s" % ignored)
                test_suite_elements.append(child)
                for update_attribute in need_update_attributes:
                    update_value = child.get(update_attribute, 0)
                    if not update_value:
                        update_value = 0
                    test_suites_attributes[update_attribute] += int(
                        update_value)

        if test_suite_elements:
            child = test_suite_elements[-1]
            child.tail = self.data_helper.LINE_BREAK
        else:
            LOG.error("Execute result not exists")
            return False

        # set test suites element attributes and children
        self._handle_module_tests(modules, test_suites_attributes)
        self.data_helper.set_element_attributes(test_suites_element,
                                                test_suites_attributes)
        test_suites_element.extend(test_suite_elements)
        return True

    @classmethod
    def _check_tests_and_unavailable(cls, child):
        total = child.get(ReportConstant.tests, "0")
        unavailable = child.get(ReportConstant.unavailable, "0")
        if total and total != "0" and unavailable and \
                unavailable != "0":
            child.set(ReportConstant.unavailable, "0")
            LOG.warning("%s total: %s, unavailable: %s", child.get(
                ReportConstant.name), total, unavailable)

    @classmethod
    def _get_module_name(cls, data_report, root):
        # get module name from data report
        module_name = get_filename_extension(data_report)[0]
        if "report" in module_name or "summary" in module_name or \
                "<" in data_report or ">" in data_report:
            module_name = root.get(ReportConstant.name,
                                   ReportConstant.empty_name)
            if "report" in module_name or "summary" in module_name:
                module_name = ReportConstant.empty_name
        return module_name

    def _init_attributes(self):
        test_suites_attributes = {
            ReportConstant.name:
                ReportConstant.summary_data_report.split(".")[0],
            ReportConstant.start_time: self.task_info.test_time,
            ReportConstant.end_time: time.strftime(ReportConstant.time_format,
                                                   time.localtime()),
            ReportConstant.errors: 0, ReportConstant.disabled: 0,
            ReportConstant.failures: 0, ReportConstant.tests: 0,
            ReportConstant.ignored: 0, ReportConstant.unavailable: 0,
            ReportConstant.modules: 0, ReportConstant.run_modules: 0}
        need_update_attributes = [ReportConstant.tests, ReportConstant.ignored,
                                  ReportConstant.failures,
                                  ReportConstant.disabled,
                                  ReportConstant.errors,
                                  ReportConstant.unavailable]
        return test_suites_attributes, need_update_attributes

    @property
    def summary_data_report_exist(self):
        return "<" in self.summary_data_str or \
               os.path.exists(self.summary_data_path)

    @property
    def data_reports(self):
        if check_pub_key_exist() or self._check_mode(ModeType.decc):
            from xdevice import SuiteReporter
            suite_reports = SuiteReporter.get_report_result()
            if self._check_mode(ModeType.decc):
                LOG.debug("Handle history result, data reports length:{}".
                          format(len(suite_reports)))
                SuiteReporter.clear_history_result()
                SuiteReporter.append_history_result(suite_reports)
            data_reports = []
            for report_path, report_result in suite_reports:
                module_name = get_filename_extension(report_path)[0]
                data_reports.append((report_result, module_name))
            SuiteReporter.clear_report_result()
            return data_reports

        if not os.path.isdir(self.report_path):
            return []
        data_reports = []
        result_path = os.path.join(self.report_path, "result")
        for root, _, files in os.walk(result_path):
            for file_name in files:
                if not file_name.endswith(self.data_helper.DATA_REPORT_SUFFIX):
                    continue
                module_name = self._find_module_name(result_path, root)
                data_reports.append((os.path.join(root, file_name),
                                     module_name))
        return data_reports

    @classmethod
    def _find_module_name(cls, result_path, root):
        # find module name from directory tree
        common_path = os.path.commonpath([result_path, root])
        if os.path.normcase(result_path) != os.path.normcase(common_path) or \
                os.path.normcase(result_path) == os.path.normcase(root):
            return ReportConstant.empty_name

        root_dir, module_name = os.path.split(root)
        if os.path.normcase(result_path) == os.path.normcase(root_dir):
            return ReportConstant.empty_name
        root_dir, subsystem_name = os.path.split(root_dir)
        while os.path.normcase(result_path) != os.path.normcase(root_dir):
            module_name = subsystem_name
            root_dir, subsystem_name = os.path.split(root_dir)
        return module_name

    def _generate_summary(self):
        if not self.summary_data_report_exist or \
                self._check_mode(ModeType.decc):
            return
        summary_ini_content = \
            "[default]\n" \
            "Platform={}\n" \
            "Test Type={}\n" \
            "Device Name={}\n" \
            "Host Info={}\n" \
            "Test Start/ End Time={}\n" \
            "Execution Time={}\n" \
            "Device Type={}\n".format(
                self.exec_info.platform, self.exec_info.test_type,
                self.exec_info.device_name, self.exec_info.host_info,
                self.exec_info.test_time, self.exec_info.execute_time,
                self.exec_info.device_label)

        if self.exec_info.product_info:
            for key, value in self.exec_info.product_info.items():
                summary_ini_content = "{}{}".format(
                    summary_ini_content, "%s=%s\n" % (key, value))

        if not self._check_mode(ModeType.factory):
            summary_ini_content = "{}{}".format(
                summary_ini_content, "Log Path=%s\n" % self.exec_info.log_path)

        # write summary_ini_content
        summary_filepath = os.path.join(self.report_path,
                                        ReportConstant.summary_ini)

        if platform.system() == "Windows":
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_BINARY
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        summary_filepath_open = os.open(summary_filepath, flags,
                                        FilePermission.mode_755)

        with os.fdopen(summary_filepath_open, "wb") as file_handler:
            if check_pub_key_exist():
                try:
                    cipher_text = do_rsa_encrypt(summary_ini_content)
                except ParamError as error:
                    LOG.error(error, error_no=error.error_no)
                    cipher_text = b""
                file_handler.write(cipher_text)
            else:
                file_handler.write(bytes(summary_ini_content, 'utf-8'))
            file_handler.flush()
            LOG.info("Generate summary ini: %s", summary_filepath)
        self.repeat_helper.__generate_repeat_xml__(self.summary_data_path)

    def _copy_report(self):
        if Uploader.is_enable() or self._check_mode(ModeType.decc):
            return

        dst_path = os.path.join(Variables.temp_dir, "latest")
        try:
            shutil.rmtree(dst_path, ignore_errors=True)
            os.makedirs(dst_path, exist_ok=True)
            LOG.info("Copy summary files to %s", dst_path)

            # copy reports to reports/latest folder
            for report_file in os.listdir(self.report_path):
                src_file = os.path.join(self.report_path, report_file)
                dst_file = os.path.join(dst_path, report_file)
                if os.path.isfile(src_file):
                    shutil.copyfile(src_file, dst_file)
        except OSError as _:
            return

    @classmethod
    def _check_mode(cls, mode):
        return Context.session().mode == mode

    def _generate_task_record(self):
        # under encryption status, don't handle anything directly
        if check_pub_key_exist() and not self._check_mode(ModeType.decc):
            return

        # get info from command_queue
        if Context.command_queue().size() == 0:
            return
        _, command, report_path = Context.command_queue().get(-1)

        record_info = {
            "command": command,
            "session_id": os.path.split(report_path)[-1],
            "report_path": report_path,
            "unsuccessful_params": self.record_params,
            "data_reports": self.record_reports
        }

        def encode(content):
            # inner function to encode
            return ' '.join([bin(ord(c)).replace('0b', '') for c in content])

        # write into file
        record_file = os.path.join(self.report_path,
                                   ReportConstant.task_info_record)
        _record_json = json.dumps(record_info, indent=2)

        with open(file=record_file, mode="wb") as file:
            if Context.session().mode == ModeType.decc:
                # under decc, write in encoded text
                file.write(bytes(encode(_record_json), encoding="utf-8"))
            else:
                # others, write in plain text
                file.write(bytes(_record_json, encoding="utf-8"))

        LOG.info("Generate record file: %s", record_file)

    @classmethod
    def get_task_info_params(cls, history_path):
        # under encryption status, don't handle anything directly
        if check_pub_key_exist() and not cls._check_mode(ModeType.decc):
            return ()

        def decode(content):
            result_list = []
            for b in content.split(' '):
                result_list.append(chr(int(b, 2)))
            return ''.join(result_list)

        record_path = os.path.join(history_path,
                                   ReportConstant.task_info_record)
        if not os.path.exists(record_path):
            LOG.error("%s not exists!", ReportConstant.task_info_record)
            return ()

        with open(record_path, mode="rb") as file:
            if Context.session().mode == ModeType.decc:
                # under decc, read from encoded text
                result = json.loads(decode(file.read().decode("utf-8")))
            else:
                # others, read from plain text
                result = json.loads(file.read())
        standard_length = 5
        if not len(result.keys()) == standard_length:
            LOG.error("%s error!", ReportConstant.task_info_record)
            return ()

        return result

    def _transact_all(self):
        pyc_path = os.path.join(Variables.res_dir, "tools", "binder.pyc")
        if not os.path.exists(pyc_path):
            return
        module_spec = util.spec_from_file_location("binder", pyc_path)
        if not module_spec:
            return
        module = util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        if hasattr(module, "transact") and callable(module.transact):
            module.transact(self, LOG)
        del module

    @classmethod
    def _handle_module_tests(cls, modules, test_suites_attributes):
        modules_list = list()
        modules_zero = list()
        for module_name, detail_list in modules.items():
            for total in detail_list:
                modules_list.append(total)
                if total == 0:
                    modules_zero.append(module_name)
        test_suites_attributes[ReportConstant.run_modules] = \
            len(modules_list) - len(modules_zero)
        test_suites_attributes[ReportConstant.modules] = len(modules_list)
        if modules_zero:
            LOG.info("The total tests of %s module is 0", ",".join(
                modules_zero))

    # ******************** 使用旧报告模板的代码 BEGIN ********************
    def _generate_vision_reports(self):
        from _core.report.reporter_helper import VisionHelper
        vision_helper = VisionHelper()
        vision_helper.report_path = self.report_path
        if not self._check_mode(ModeType.decc) and not \
                self.summary_data_report_exist:
            LOG.error("Summary data report not exists")
            return

        if check_pub_key_exist() or self._check_mode(ModeType.decc):
            from xdevice import SuiteReporter
            SuiteReporter.clear_report_result()

        # parse data
        if self.summary_data_str:
            # only in decc mode and pub key, self.summary_data_str is not empty
            summary_element_tree = self.data_helper.parse_data_report(
                self.summary_data_str)
        else:
            summary_element_tree = self.data_helper.parse_data_report(
                self.summary_data_path)
        parsed_data = vision_helper.parse_element_data(
            summary_element_tree, self.report_path, self.task_info)
        self.parsed_data = parsed_data
        self.exec_info, summary, _ = parsed_data

        if self._check_mode(ModeType.decc):
            return

        LOG.info("Summary result: modules: %s, run modules: %s, total: "
                 "%s, passed: %s, failed: %s, blocked: %s, ignored: %s, "
                 "unavailable: %s", summary.modules, summary.run_modules,
                 summary.result.total, summary.result.passed,
                 summary.result.failed, summary.result.blocked,
                 summary.result.ignored, summary.result.unavailable)
        LOG.info("Log path: %s", self.exec_info.log_path)

        if summary.result.failed != 0 or summary.result.blocked != 0 or\
                summary.result.unavailable != 0:
            from xdevice import Scheduler
            Scheduler.is_need_auto_retry = True

        # generate summary vision report
        report_generate_flag = self._generate_vision_report(
            vision_helper, parsed_data, ReportConstant.summary_title,
            ReportConstant.summary_vision_report)

        # generate details vision report
        if report_generate_flag and summary.result.total > 0:
            self._generate_vision_report(
                vision_helper, parsed_data, ReportConstant.details_title,
                ReportConstant.details_vision_report)

        # generate failures vision report
        if summary.result.total != (
                summary.result.passed + summary.result.ignored) or \
                summary.result.unavailable > 0:
            self._generate_vision_report(
                vision_helper, parsed_data, ReportConstant.failures_title,
                ReportConstant.failures_vision_report)

        # generate passes vision report
        if summary.result.passed != 0:
            self._generate_vision_report(
                vision_helper, parsed_data, ReportConstant.passes_title,
                ReportConstant.passes_vision_report)

        # generate ignores vision report
        if summary.result.ignored != 0:
            self._generate_vision_report(
                vision_helper, parsed_data, ReportConstant.ignores_title,
                ReportConstant.ignores_vision_report)

    def _generate_vision_report(self, vision_helper, parsed_data, title, render_target):
        # render data
        report_context = vision_helper.render_data(
            title, parsed_data,
            render_target=render_target, devices=self.summary.get_devices())

        # generate report
        if report_context:
            report_path = os.path.join(self.report_path, render_target)
            vision_helper.generate_report(report_path, report_context)
            return True
        else:
            LOG.error("Failed to generate %s", render_target)
            return False
    # ******************** 使用旧报告模板的代码 END ********************
