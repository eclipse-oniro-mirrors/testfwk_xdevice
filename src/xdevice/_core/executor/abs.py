#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2023 Huawei Device Co., Ltd.
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
import re
import stat
import uuid
from abc import ABC
from abc import abstractmethod

from _core.plugin import Plugin
from _core.plugin import get_plugin
from _core.constants import TestType
from _core.executor.bean import CaseResult
from _core.executor.bean import SuiteResult
from _core.executor.bean import SuitesResult
from _core.interface import LifeCycle
from _core.interface import IListener
from _core.report.suite_reporter import SuiteReporter
from _core.report.suite_reporter import ResultCode


__all__ = ["UniversalReportListener", "PlusReportListener"]


class AbsReportListener(IListener, ABC):

    @abstractmethod
    def _get_suite_result(self, test_result, create=False):
        pass

    @abstractmethod
    def _get_test_result(self, test_result, create=False):
        pass

    def __started__(self, lifecycle, result):
        if lifecycle == LifeCycle.TestSuites:
            self._handle_test_suites_start(result)
        elif lifecycle == LifeCycle.TestSuite:
            self._handle_testsuite_start(result)
        elif lifecycle == LifeCycle.TestCase:
            self._handle_case_start(result)

    def __ended__(self, lifecycle, test_result, **kwargs):
        if lifecycle == LifeCycle.TestSuite:
            self._handle_testsuite_end(test_result, kwargs)
        elif lifecycle == LifeCycle.TestSuites:
            self._handle_test_suites_end(test_result, kwargs)
        elif lifecycle == LifeCycle.TestCase:
            self._handle_case_end(test_result)
        elif lifecycle == LifeCycle.TestTask:
            self._handle_task_end(test_result, kwargs)

    def __skipped__(self, lifecycle, result):
        if lifecycle == LifeCycle.TestCase:
            self._handle_case_skip(result)

    def __failed__(self, lifecycle, test_result):
        if lifecycle == LifeCycle.TestSuite:
            self._handle_suite_fail(test_result)
        elif lifecycle == LifeCycle.TestCase:
            self._handle_case_fail(test_result)

    @abstractmethod
    def _handle_test_suites_start(self, test_result):
        pass

    @abstractmethod
    def _handle_testsuite_start(self, test_result):
        pass

    @abstractmethod
    def _handle_case_start(self, test_result):
        pass

    @abstractmethod
    def _handle_testsuite_end(self, test_result, kwargs):
        pass

    @abstractmethod
    def _handle_test_suites_end(self, test_result, kwargs):
        pass

    @abstractmethod
    def _handle_case_end(self, test_result):
        pass

    @abstractmethod
    def _handle_task_end(self, test_result, kwargs):
        pass

    @abstractmethod
    def _handle_case_skip(self, test_result):
        pass

    @abstractmethod
    def _handle_case_fail(self, test_result):
        pass

    @abstractmethod
    def _handle_suite_fail(self, test_result):
        pass


class ReportEventListener(AbsReportListener, ABC):

    def __init__(self):
        self.result = list()
        self.suites = dict()
        self.tests = dict()
        self.current_suite_id = 0
        self.current_test_id = 0
        self.report_path = ""

    def _get_suite_result(self, test_result, create=False):
        if test_result.index in self.suites:
            return self.suites.get(test_result.index)
        elif create:
            suite = SuiteResult()
            rid = uuid.uuid4().hex if test_result.index == "" else \
                test_result.index
            suite.index = rid
            return self.suites.setdefault(rid, suite)
        else:
            return self.suites.get(self.current_suite_id)

    def _get_test_result(self, test_result, create=False):
        if test_result.index in self.tests:
            return self.tests.get(test_result.index)
        elif create:
            test = CaseResult()
            rid = uuid.uuid4().hex if test_result.index == "" else \
                test_result.index
            test.index = rid
            return self.tests.setdefault(rid, test)
        else:
            return self.tests.get(self.current_test_id)

    def _handle_case_start(self, test_result):
        test = self._get_test_result(test_result=test_result, create=True)
        test.test_name = test_result.test_name
        test.test_class = test_result.test_class
        self.current_test_id = test.index

    def _handle_testsuite_start(self, test_result):
        suite = self._get_suite_result(test_result=test_result,
                                       create=True)
        suite.suite_name = test_result.suite_name
        suite.test_num = test_result.test_num
        self.current_suite_id = suite.index

    def _handle_test_suites_start(self, test_result):
        suites = self._get_suite_result(test_result=test_result,
                                        create=True)
        suites.suites_name = test_result.suites_name
        suites.test_num = test_result.test_num
        self.current_suite_id = suites.index

    def _handle_testsuite_end(self, test_result, kwargs):
        suite = self._get_suite_result(test_result=test_result,
                                       create=False)
        if not suite:
            return
        suite.run_time = test_result.run_time
        suite.code = test_result.code
        suite.report = test_result.report
        suite.test_num = max(test_result.test_num, len(self.tests))
        self._handle_suite_end_data(suite, kwargs)

    def _handle_task_end(self, test_result, kwargs):
        test_type = str(kwargs.get("test_type", TestType.all))
        reporter = get_plugin(plugin_type=Plugin.REPORTER,
                              plugin_id=test_type)
        if not reporter:
            reporter = get_plugin(plugin_type=Plugin.REPORTER,
                                  plugin_id=TestType.all)[0]
        else:
            reporter = reporter[0]
        reporter.__generate_reports__(self.report_path,
                                      task_info=test_result)

    def _handle_case_end(self, test_result):
        test = self._get_test_result(test_result=test_result, create=False)
        test.run_time = test_result.run_time
        test.stacktrace = test_result.stacktrace
        test.code = test_result.code
        test.report = test_result.report
        test.is_completed = test_result.is_completed

    def _handle_test_suites_end(self, test_result, kwargs):
        if not kwargs.get("suite_report", False):
            result_dir = os.path.join(self.report_path, "result")
            os.makedirs(result_dir, exist_ok=True)
            message = kwargs.get("message", "")
            # 有的场景传SuiteResult对象进来，导致报错，需要增加实例判断
            if isinstance(test_result, SuitesResult):
                message = test_result.stacktrace
                suites_name = test_result.suites_name
            else:
                suites_name = kwargs.get("suites_name", "")
            self._generate_data_report(result_dir, self.result, suites_name, message=message)

    def _handle_case_skip(self, test_result):
        test = self._get_test_result(test_result=test_result, create=False)
        test.stacktrace = test_result.stacktrace
        test.code = ResultCode.SKIPPED.value

    def _handle_case_fail(self, test_result):
        test = self._get_test_result(test_result=test_result, create=False)
        test.stacktrace = test_result.stacktrace
        test.code = ResultCode.FAILED.value

    def _handle_suite_fail(self, test_result):
        suite = self._get_suite_result(test_result=test_result,
                                       create=False)
        suite.stacktrace = test_result.stacktrace
        suite.code = ResultCode.FAILED.value

    @abstractmethod
    def _generate_data_report(self, result_dir, results, name, **kwargs):
        pass

    @abstractmethod
    def _handle_suite_end_data(self, suite, kwargs):
        pass


class UniversalReportListener(ReportEventListener, ABC):

    def __init__(self):
        super().__init__()
        self.suite_distributions = dict()

    def _handle_task_end(self, test_result, kwargs):
        pass

    @classmethod
    def _generate_data_report(cls, result_dir, results, name, **kwargs):
        suite_report = SuiteReporter(results, name, result_dir, **kwargs)
        suite_report.generate_data_report()


class PlusReportListener(ReportEventListener, ABC):

    def __init__(self):
        super().__init__()
        self.device_sn = ""
        self.suite_name = ""

    @classmethod
    def _generate_data_report(cls, result_dir, results, name, **kwargs):
        suite_report = SuiteReporter(results, name, result_dir, **kwargs)
        suite_report.generate_data_report()

    def _handle_case_end(self, test_result):
        test = self._get_test_result(test_result=test_result, create=False)
        test.run_time = test_result.run_time
        test.stacktrace = test_result.stacktrace
        test.code = test_result.code
        test.report = test_result.report
        if getattr(test_result, "result_content", ""):
            test.result_content = test_result.result_content
        if hasattr(self, "report_plus") and self.report_plus:
            self._update_result(test_result)
            test.normal_screen_urls = test_result.normal_screen_urls
            test.failure_screen_urls = test_result.failure_screen_urls
        if hasattr(self, "device_log_back_fill_path"):
            test_record, result_info = self._update_test_record(self.device_log_back_fill_path, test_result)
            test.test_record = test_record
            if hasattr(test_result, "result_info") and test_result.result_info:
                test.result_info = test_result.result_info
            else:
                test.result_info = result_info

    def _update_result(self, result):
        serial_re = re.sub(r'[^A-Za-z0-9]', '_', self.device_sn)
        screenshot_base_path = os.path.join(
            self.report_path, "screenshot", serial_re, self.suite_name)
        temp = "{}_{}=".format(result.test_class, result.test_name)
        result.normal_screen_urls = os.path.join(screenshot_base_path, "normal", temp)
        result.failure_screen_urls = os.path.join(screenshot_base_path, "failure", temp)

    def _update_test_record(self, device_log_back_fill_path, result):
        try:
            split_str = "{}_{}".format(result.test_class, result.test_name)
            test_record = ""
            result_info = ""
            test_class = '"{}"'.format(result.test_class)
            test_name = '"{}"'.format(result.test_name)

            fd = os.open(device_log_back_fill_path, os.O_RDONLY, stat.S_IWUSR | stat.S_IRUSR)
            with os.fdopen(fd, "r", encoding="utf-8") as file_content:
                for line in file_content.readlines():
                    suite_name = ""
                    if hasattr(self, "suite_name"):
                        suite_name = self.suite_name
                    if suite_name and suite_name in line and split_str in line:
                        str_arr = line.split(split_str)
                        if str_arr[1]:
                            test_record = str_arr[1].strip()
                    elif test_class in line and test_name in line:
                        json_arr = line.split("HtsIgnoredTest")
                        if len(json_arr) == 2:
                            result_info = json_arr[1].strip()
            return test_record, result_info
        except (FileNotFoundError, IOError) as error:
            raise error
