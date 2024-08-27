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

from _core.plugin import Plugin
from _core.constants import ListenerType
from _core.executor.abs import PlusReportListener
from _core.interface import LifeCycle
from _core.interface import IListener
from _core.logger import platform_logger
from _core.report.suite_reporter import ResultCode
from _core.report.encrypt import check_pub_key_exist

__all__ = ["LogListener", "ReportListener", "UploadListener",
           "CollectingTestListener", "CollectingLiteGTestListener",
           "TestDescription"]

LOG = platform_logger("Listener")


class TestDescription(object):
    def __init__(self, class_name, test_name):
        self.class_name = class_name
        self.test_name = test_name

    def __eq__(self, other):
        return self.class_name == other.class_name and \
               self.test_name == other.test_name

    @classmethod
    def remove_test(cls, tests, execute_tests):
        for execute_test in execute_tests:
            if execute_test in tests:
                tests.remove(execute_test)
        return tests


@Plugin(type=Plugin.LISTENER, id=ListenerType.log)
class LogListener(IListener):
    """
    Listener test status information to the console and log
    """
    test_num = 0
    device_sn = ""

    def __started__(self, lifecycle, test_result):
        if check_pub_key_exist():
            return
        if lifecycle == LifeCycle.TestSuite:
            LOG.debug("Start test suite [{}] with {} tests"
                      .format(test_result.suite_name, test_result.test_num))
            self.test_num = test_result.test_num
        elif lifecycle == LifeCycle.TestCase:
            LOG.debug("TestStarted({}#{})"
                      .format(test_result.test_class, test_result.test_name))

    def __ended__(self, lifecycle, test_result, **kwargs):
        if check_pub_key_exist():
            return

        from _core.utils import convert_serial
        del kwargs
        if lifecycle == LifeCycle.TestSuite:
            LOG.debug("End test suite cost {}ms."
                      .format(test_result.run_time))
            LOG.info("End test suite [{}]."
                     .format(test_result.suite_name))
        elif lifecycle == LifeCycle.TestCase:
            LOG.debug("TestEnded({}#{})"
                      .format(test_result.test_class, test_result.test_name))
            ret = ResultCode(test_result.code).name
            if self.test_num:
                LOG.info("[{}/{} {}] {}#{} {}"
                         .format(test_result.current, self.test_num, convert_serial(self.device_sn),
                                 test_result.test_class, test_result.test_name, ret))
            else:
                LOG.info("[{}/- {}] {}#{} {}"
                         .format(test_result.current, convert_serial(self.device_sn),
                                 test_result.test_class, test_result.test_name, ret))

    @staticmethod
    def __skipped__(lifecycle, test_result, **kwargs):
        if check_pub_key_exist():
            return

        del kwargs
        if lifecycle == LifeCycle.TestSuite:
            LOG.debug("Test suite [{}] skipped".format(test_result.suite_name))
        elif lifecycle == LifeCycle.TestCase:
            ret = ResultCode(test_result.code).name
            LOG.debug("[{}] {}#{}".format(ret, test_result.test_class,
                                          test_result.test_name))

    @staticmethod
    def __failed__(lifecycle, test_result, **kwargs):
        pass


@Plugin(type=Plugin.LISTENER, id=ListenerType.report)
class ReportListener(PlusReportListener):
    """
    Listener test status information to the console
    """

    def handle_half_break(self, suites_name, error_message=''):
        """测试套运行异常，将已运行的部分用例结果记录到结果文件"""
        test_result = self.suites.get(self.current_suite_id)
        if test_result is None:
            return
        self.__ended__(lifecycle=LifeCycle.TestSuite, test_result=test_result)
        LOG.warning(f"Testsuite({test_result.suite_name}) is running abnormally")
        self.__ended__(lifecycle=LifeCycle.TestSuites, test_result=test_result,
                       suites_name=suites_name, message=error_message)

    def _handle_suite_end_data(self, suite, kwargs):
        is_clear = kwargs.get("is_clear", False)
        # generate suite report
        if not kwargs.get("suite_report", False):
            if len(self.result) > 0 and self.result[-1][0].suite_name == \
                    self.suites.get(suite.index).suite_name:
                self.result[-1][1].extend(list(self.tests.values()))
                self.result[-1][0].test_num = max(suite.test_num,
                                                  len(self.result[-1][1]))
            else:
                self.result.append((self.suites.get(suite.index),
                                    list(self.tests.values())))
        else:
            result_dir = os.path.join(self.report_path, "result")
            os.makedirs(result_dir, exist_ok=True)
            self.result.append((self.suites.get(suite.index),
                                list(self.tests.values())))
            results = [(suite, list(self.tests.values()))]
            self._generate_data_report(result_dir, results, suite.suite_name)
        if is_clear:
            self.tests.clear()


@Plugin(type=Plugin.LISTENER, id=ListenerType.upload)
class UploadListener(IListener):
    def __started__(self, lifecycle, test_result):
        pass

    @staticmethod
    def __ended__(lifecycle, test_result, **kwargs):
        del test_result, kwargs
        if lifecycle == LifeCycle.TestCase:
            pass

    @staticmethod
    def __skipped__(lifecycle, test_result, **kwargs):
        pass

    @staticmethod
    def __failed__(lifecycle, test_result, **kwargs):
        pass


@Plugin(type=Plugin.LISTENER, id=ListenerType.collect)
class CollectingTestListener(IListener):
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
        pass

    def get_current_run_results(self):
        return self.tests


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
