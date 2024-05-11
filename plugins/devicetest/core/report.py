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
import xml.dom.minidom
from xdevice import get_cst_time
from devicetest.core.constants import RunResult
from devicetest.core.error_message import ErrorMessage
from devicetest.core.exception import DeviceTestError
from devicetest.log.logger import DeviceTestLog as log


class ReportConstants:
    _STRIP_FORMAT_TIME = "%Y-%m-%d-%H-%M-%S-%f"
    _STRF_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    _XML_NAME = "report.xml"
    _FILE_FARMAT = ".xml"


class ReportHandler:

    def __init__(self, report_path):
        self.report_path = report_path
        self.test_results = []

    def generate_test_report(self, test_runner, _test_results=None, report_type="normal"):
        if os.path.exists(self.report_path):
            dom = xml.dom.minidom.parse(self.report_path)
            result_node = dom.documentElement
            return self.report_path, result_node.toxml()
        try:
            log.info("start generate test report.")
            test_results = _test_results or test_runner.test_results

            start_time = test_runner.start_time

            impl = xml.dom.minidom.getDOMImplementation()
            dom = impl.createDocument(None, 'testsuites', None)
            result_node = dom.documentElement

            test_name = test_runner.configs.get("test_name")
            if test_name is not None:
                result_node.setAttribute("name", test_name)
            else:
                result_node.setAttribute("name", ReportConstants._XML_NAME)

            result_node.setAttribute("report_version", "1.0")

            if report_type == "xts":
                tests_total, tests_error = self.report_xts_type(test_results, dom, result_node)
            else:
                tests_total, tests_error = self.report_normal_type(test_results, dom, test_name, result_node)

            result_node.setAttribute("tests", str(tests_total))
            result_node.setAttribute("failures", str(tests_error))
            result_node.setAttribute("disabled", '')
            result_node.setAttribute("errors", "")
            result_node.setAttribute("starttime",
                                     self.get_strftime(start_time))
            result_node.setAttribute("endtime", self.get_now_strftime())

            if not os.path.exists(os.path.dirname(self.report_path)):
                os.makedirs(os.path.dirname(self.report_path))
            with open(self.report_path, mode='w',
                      encoding='utf-8') as fre:
                dom.writexml(fre, addindent='\t', newl='\n',
                             encoding="utf-8")
            return self.report_path, result_node.toxml()

        except Exception as error:
            log.error(ErrorMessage.Error_01207.Message.en,
                      error_no=ErrorMessage.Error_01207.Code,
                      is_traceback=True)
            raise DeviceTestError(ErrorMessage.Error_01207.Topic) from error

        finally:
            log.info("exit generate test report.")

    def get_strftime(self, stamp_time):
        return stamp_time.strftime(ReportConstants._STRF_TIME_FORMAT)

    def get_now_strftime(self):
        return get_cst_time().strftime(ReportConstants._STRF_TIME_FORMAT)

    def report_normal_type(self, test_results, dom, test_name, result_node):
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

            test_case = dom.createElement("testcase")
            test_case.setAttribute("name", case_name)
            test_case.setAttribute("status", 'run')
            test_case.setAttribute("classname", case_name)
            test_case.setAttribute("level", None)
            test_case.setAttribute("result", case_result)
            test_case.setAttribute("result_kind", result)
            test_case.setAttribute("message", error)
            test_case.setAttribute("report", report)

            test_suite = dom.createElement("testsuite")
            test_suite.setAttribute("modulename", test_name)
            test_suite.setAttribute("name", case_name)
            test_suite.setAttribute("tests", str(1))
            test_suite.setAttribute("failures", str(case_error))
            test_suite.setAttribute("disabled", '0')
            test_suite.setAttribute("time", "{:.2f}".format(case_time))
            test_suite.setAttribute("result", case_result)
            test_suite.setAttribute("result_kind", result)
            test_suite.setAttribute("report", report)
            test_suite.appendChild(test_case)
            result_node.appendChild(test_suite)
        return tests_total, tests_error

    def report_xts_type(self, test_results, dom, result_node):
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

            test_case = dom.createElement("testcase")
            test_case.setAttribute("name", case_name)
            test_case.setAttribute("status", 'run')
            test_case.setAttribute("classname", module_name)
            test_case.setAttribute("level", None)
            test_case.setAttribute("result", case_result)
            test_case.setAttribute("result_kind", result)
            test_case.setAttribute("message", error)
            test_case.setAttribute("report", report)

            test_suite = dom.createElement("testsuite")
            test_suite.setAttribute("modulename", module_name)
            test_suite.setAttribute("name", module_name)
            test_suite.setAttribute("tests", str(1))
            test_suite.setAttribute("disabled", '0')
            test_suite.setAttribute("time", "{:.2f}".format(case_time))
            test_suite.setAttribute("report", report)
            if module_name not in test_suites:
                test_suites[module_name] = {"test_suite": test_suite, "tests": 0, "failures": 0}
                result_node.appendChild(test_suite)
            test_suites[module_name]["test_suite"].appendChild(test_case)
            test_suites[module_name]["tests"] += 1
            tests = test_suites[module_name]["tests"]
            if case_result == "false":
                test_suites[module_name]["failures"] += 1
            failures = test_suites[module_name]["failures"]
            test_suites[module_name]["test_suite"].setAttribute("tests", str(tests))
            test_suites[module_name]["test_suite"].setAttribute("failures", str(failures))
        return tests_total, tests_error
