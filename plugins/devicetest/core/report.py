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

import os
from ast import literal_eval
from xml.dom import minidom
from xml.etree import ElementTree

from xdevice import get_cst_time, FilePermission
from devicetest.core.constants import RunResult
from devicetest.core.exception import DeviceTestError
from devicetest.error import ErrorMessage
from devicetest.log.logger import DeviceTestLog as Log


class ReportConstants:
    time_format = "%Y-%m-%d %H:%M:%S"
    report_xml = "report.xml"


class ReportHandler:

    def __init__(self, report_path):
        self.report_path = report_path
        self.test_results = []

    def generate_test_report(self, test_runner, _test_results=None, report_type="normal"):
        if os.path.exists(self.report_path):
            root = ElementTree.parse(self.report_path).getroot()
            return self.report_path, ElementTree.tostring(root).decode()
        try:
            Log.info("start generate test report.")
            test_results = _test_results or test_runner.test_results

            start_time = test_runner.start_time

            testsuites = ElementTree.Element('testsuites')

            test_name = test_runner.configs.get("test_name")
            if test_name is not None:
                testsuites.set("name", test_name)
            else:
                testsuites.set("name", ReportConstants.report_xml)

            if report_type == "xts":
                tests_total, tests_error = self.report_xts_type(testsuites, test_results)
            else:
                tests_total, tests_error = self.report_normal_type(testsuites, test_results, test_name)

            testsuites.set("tests", str(tests_total))
            testsuites.set("failures", str(tests_error))
            testsuites.set("disabled", '')
            testsuites.set("errors", "")
            testsuites.set("starttime", self.get_strftime(start_time))
            testsuites.set("endtime", self.get_now_strftime())
            testsuites.set("report_version", "1.0")

            os.makedirs(os.path.dirname(self.report_path), exist_ok=True)
            xml_content = ElementTree.tostring(testsuites).decode()
            xml_pretty = minidom.parseString(xml_content).toprettyxml(indent="  ")

            result_fd = os.open(self.report_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, FilePermission.mode_644)
            with os.fdopen(result_fd, mode="w", encoding="utf-8") as result_file:
                result_file.write(xml_pretty)
            return self.report_path, xml_content

        except Exception as error:
            err_msg = ErrorMessage.Common.Code_0201003
            Log.error(err_msg, is_traceback=True)
            raise DeviceTestError(err_msg) from error

        finally:
            Log.info("exit generate test report.")

    def get_strftime(self, stamp_time):
        return stamp_time.strftime(ReportConstants.time_format)

    def get_now_strftime(self):
        return get_cst_time().strftime(ReportConstants.time_format)

    def report_normal_type(self, testsuites, test_results, test_name):
        tests_total = 0
        tests_error = 0
        for result_info in test_results:

            tests_total += 1
            case_error = 0
            case_result = "true"
            result = result_info.get('result')
            if result != RunResult.PASSED:
                tests_error += 1
                case_error += 1
                case_result = "false"
            case_name = result_info.get('case_name')
            case_start_time = result_info.get('start_time').timestamp()
            case_end_time = result_info.get('end_time').timestamp()
            error = result_info.get('error')
            report = result_info.get("report", "")
            case_time = case_end_time - case_start_time

            testcase = ElementTree.Element('testcase')
            testcase.set("name", case_name)
            testcase.set("status", 'run')
            testcase.set("classname", case_name)
            testcase.set("level", "")
            testcase.set("result", case_result)
            testcase.set("result_kind", result)
            testcase.set("message", error)
            testcase.set("report", report)
            # 用例测试结果的拓展内容
            result_content = result_info.get('result_content')
            if result_content:
                testcase.set("result_content", literal_eval(str(result_content)))

            testsuite = ElementTree.Element('testsuite')
            testsuite.set("modulename", test_name)
            testsuite.set("name", case_name)
            testsuite.set("tests", str(1))
            testsuite.set("failures", str(case_error))
            testsuite.set("disabled", '0')
            testsuite.set("time", "{:.2f}".format(case_time))
            testsuite.set("result", case_result)
            testsuite.set("result_kind", result)
            testsuite.set("report", report)

            testsuite.append(testcase)
            testsuites.append(testsuite)
        return tests_total, tests_error

    def report_xts_type(self, testsuites, test_results):
        tests_total = 0
        tests_error = 0
        test_suites = {}
        for result_info in test_results:

            tests_total += 1
            case_error = 0
            case_result = "true"
            result = result_info.get('result')
            if result != RunResult.PASSED:
                tests_error += 1
                case_error += 1
                case_result = "false"
            case_info = result_info.get('case_name').split("#")
            case_name = case_info[1]
            module_name = case_info[0]
            case_start_time = result_info.get('start_time').timestamp()
            case_end_time = result_info.get('end_time').timestamp()
            error = result_info.get('error')
            report = result_info.get("report", "")
            case_time = case_end_time - case_start_time

            testcase = ElementTree.Element('testcase')
            testcase.set("name", case_name)
            testcase.set("status", 'run')
            testcase.set("classname", module_name)
            testcase.set("level", "")
            testcase.set("result", case_result)
            testcase.set("result_kind", result)
            testcase.set("message", error)
            testcase.set("report", report)

            testsuite = ElementTree.Element('testsuite')
            testsuite.set("modulename", module_name)
            testsuite.set("name", module_name)
            testsuite.set("tests", str(1))
            testsuite.set("disabled", '0')
            testsuite.set("time", "{:.2f}".format(case_time))
            testsuite.set("report", report)
            if module_name not in test_suites:
                test_suites[module_name] = {"test_suite": testsuite, "tests": 0, "failures": 0}
                testsuites.append(testsuite)
            test_suites[module_name]["test_suite"].append(testcase)
            test_suites[module_name]["tests"] += 1
            tests = test_suites[module_name]["tests"]
            if case_result == "false":
                test_suites[module_name]["failures"] += 1
            failures = test_suites[module_name]["failures"]
            test_suites[module_name]["test_suite"].set("tests", str(tests))
            test_suites[module_name]["test_suite"].set("failures", str(failures))
        return tests_total, tests_error
