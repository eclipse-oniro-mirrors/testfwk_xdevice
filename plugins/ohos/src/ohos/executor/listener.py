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
import uuid

from xdevice import Plugin
from xdevice import IListener
from xdevice import LifeCycle
from xdevice import platform_logger
from xdevice import ListenerType
from xdevice import TestDescription
from xdevice import ResultCode
from xdevice import UniversalReportListener

from ohos.executor.bean import StackCaseResult


__all__ = ["CollectingLiteGTestListener", "CollectingPassListener"]

LOG = platform_logger("Listener")


@Plugin(type=Plugin.LISTENER, id=ListenerType.collect_lite)
class CollectingLiteGTestListener(IListener):
    """
    Listener test status information to the console
    """

    def __init__(self):
        self.tests = []

    def __started__(self, lifecycle, test_result):
        if lifecycle == LifeCycle.TestCase:
            if not test_result.test_class or not test_result.test_name:
                return
            test = TestDescription(test_result.test_class,
                                   test_result.test_name)
            if test not in self.tests:
                self.tests.append(test)

    def __ended__(self, lifecycle, test_result=None, **kwargs):
        pass

    def __skipped__(self, lifecycle, test_result):
        pass

    def __failed__(self, lifecycle, test_result):
        if lifecycle == LifeCycle.TestCase:
            if not test_result.test_class or not test_result.test_name:
                return
            test = TestDescription(test_result.test_class,
                                   test_result.test_name)
            if test not in self.tests:
                self.tests.append(test)

    def get_current_run_results(self):
        return self.tests


@Plugin(type=Plugin.LISTENER, id=ListenerType.collect_pass)
class CollectingPassListener(IListener):
    """
    listener test status information to the console
    """

    def __init__(self):
        self.tests = []

    def __started__(self, lifecycle, test_result):
        pass

    def __ended__(self, lifecycle, test_result=None, **kwargs):
        if lifecycle == LifeCycle.TestCase:
            if not test_result.test_class or not test_result.test_name:
                return
            if test_result.code != ResultCode.PASSED.value:
                return
            test = TestDescription(test_result.test_class,
                                   test_result.test_name)
            if test not in self.tests:
                self.tests.append(test)
            else:
                LOG.warning("Duplicate testcase: %s#%s" % (
                    test_result.test_class, test_result.test_name))

    def __skipped__(self, lifecycle, test_result):
        pass

    def __failed__(self, lifecycle, test_result):
        pass

    def get_current_run_results(self):
        return self.tests


@Plugin(type=Plugin.LISTENER, id=ListenerType.stack_report)
class StackReportListener(UniversalReportListener):
    """
    Listener suite event
    """

    def __init__(self):
        super().__init__()
        self._suites_index_stack = list()
        self._suite_names_mapping = dict()
        self.cycle = 0

    def _get_test_result(self, test_result, create=False):
        if test_result.index in self.tests:
            return self.tests.get(test_result.index)
        elif create:
            test = StackCaseResult()
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
        if len(self._suites_index_stack) > 0:
            test.parent_index = self._suites_index_stack[-1]
        self.current_test_id = test.index

    def _handle_testsuite_start(self, test_result):
        suite = self._get_suite_result(test_result=test_result,
                                       create=True)
        suite.suite_name = test_result.suite_name
        suite.test_num = test_result.test_num
        self.current_suite_id = suite.index
        self._suites_index_stack.append(suite.index)

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
        if len(self._suites_index_stack) > 0:
            self._suites_index_stack.pop(-1)

    def _handle_suite_end_data(self, suite, kwargs):
        if not kwargs.get("suite_report", False):
            results_of_same_suite = list()
            test_values = list(self.tests.values())
            have_marked_list = list()
            for index in range(len(test_values)-1, -1, -1):
                cur_test = test_values[index]
                if cur_test.parent_index == suite.index:
                    results_of_same_suite.insert(0, cur_test)
                    have_marked_list.append(cur_test.index)
            for have_marked in have_marked_list:
                self.tests.pop(have_marked)

            if suite.suite_name not in self._suite_names_mapping.keys():
                self._suite_names_mapping.update({suite.suite_name: suite.index})
            if self.cycle > 0:
                suite_index = self._suite_names_mapping.get(suite.suite_name, "")
                if suite_index in self.suite_distributions.keys():
                    for suite_item, result_list in self.result:
                        if suite_item.index != suite_index:
                            continue
                        self.suites.pop(suite.index)
                        if result_list and result_list[-1].is_completed is not True:
                            result_list.pop(-1)
                        result_list.extend(results_of_same_suite)
                        break
                else:
                    self.suite_distributions.update({suite.index: len(self.result)})
                    self.result.append((self.suites.get(suite.index), results_of_same_suite))
            else:
                self.suite_distributions.update({suite.index: len(self.result)})
                self.result.append((self.suites.get(suite.index), results_of_same_suite))
