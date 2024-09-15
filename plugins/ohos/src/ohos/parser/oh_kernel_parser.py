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

from ohos.parser import *

__all__ = ["OHKernelTestParser"]

"""
OpenHarmony Kernel Test
"""
RUNTEST_TEST = "runtest test"
START_TO_TEST = "Start to test"
FINISHED_TO_TEST = "Finished to test"
TIMEOUT_TESTCASES = "Timeout testcases"
FAIL_DOT = "FAIL."
PASS_DOT = "PASS."
ERROR_EXCLAMATION = "ERROR!!!"
TIMEOUT_EXCLAMATION = "TIMEOUT!"

LOG = platform_logger("Parser")


@Plugin(type=Plugin.PARSER, id=CommonParserType.oh_kernel_test)
class OHKernelTestParser(IParser):

    def __init__(self):
        self.state_machine = StateRecorder()
        self.suites_name = ""
        self.listeners = []

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        if not self.state_machine.suites_is_started():
            self.state_machine.trace_logs.extend(lines)
        for line in lines:
            self.parse(line)

    def __done__(self):
        pass

    def parse(self, line):
        line = re.sub('\x1b.*?m', '', line)
        if self.state_machine.suites_is_started() or RUNTEST_TEST in line:
            if RUNTEST_TEST in line:
                self.handle_suites_started_tag(line)
            elif START_TO_TEST in line:
                self.handle_suite_start_tag(line)
            elif FINISHED_TO_TEST in line:
                self.handle_suite_end_tag(line)
            elif line.endswith(PASS_DOT) or line.endswith(FAIL_DOT):
                self.handle_one_test_case_tag(line)
            elif line.endswith(ERROR_EXCLAMATION) \
                    or line.endswith(TIMEOUT_EXCLAMATION):
                self.handle_test_case_error(line)
            elif TIMEOUT_TESTCASES in line:
                self.handle_suites_ended_tag(line)

    def handle_suites_started_tag(self, line):
        self.state_machine.get_suites(reset=True)
        test_suites = self.state_machine.get_suites()
        test_suites.suites_name = self.suites_name
        test_suites.test_num = 0
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suites)
            listener.__started__(LifeCycle.TestSuites, suite_report)

    def handle_suites_ended_tag(self, line):
        suites = self.state_machine.get_suites()
        suites.is_completed = True

        for listener in self.get_listeners():
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name)

    def handle_suite_start_tag(self, line):
        pattern = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}" \
                  " Start to test (.+)$"
        matcher = re.match(pattern, line)
        if matcher and matcher.group(1):
            self.state_machine.suite(reset=True)
            test_suite = self.state_machine.suite()
            test_suite.suite_name = matcher.group(1)
            for listener in self.get_listeners():
                suite_report = copy.copy(test_suite)
                listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_end_tag(self, line):
        pattern = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}" \
                  " Finished to test (.+)$"
        matcher = re.match(pattern, line)
        if matcher and matcher.group(1):
            suite_result = self.state_machine.suite()
            suites = self.state_machine.get_suites()
            suite_result.run_time = suite_result.run_time
            suites.run_time += suite_result.run_time
            suite_result.is_completed = True

            for listener in self.get_listeners():
                suite = copy.copy(suite_result)
                listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def handle_one_test_case_tag(self, line):
        pattern = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} (.+) " \
                  "(PASS)\\.$"
        matcher = re.match(pattern, line)
        if not (matcher and matcher.group(1) and matcher.group(2)):
            return
        test_result = self.state_machine.test(reset=True)
        test_suite = self.state_machine.suite()
        test_result.test_class = test_suite.suite_name
        test_result.test_name = matcher.group(1)
        test_result.current = self.state_machine.running_test_index + 1
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

        test_suites = self.state_machine.get_suites()
        if PASS_DOT in line:
            test_result.code = ResultCode.PASSED.value
        elif FAIL_DOT in line:
            test_result.code = ResultCode.FAILED.value
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__failed__(LifeCycle.TestCase, result)
        self.state_machine.test().is_completed = True
        test_suite.test_num += 1
        test_suites.test_num += 1
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)
        self.state_machine.running_test_index += 1

    def handle_test_case_error(self, line):
        pattern = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2} (.+) " \
                  "(ERROR!!!|TIMEOUT!)$"
        matcher = re.match(pattern, line)
        if not (matcher and matcher.group(1) and matcher.group(2)):
            return
        test_result = self.state_machine.test(reset=True)
        test_suite = self.state_machine.suite()
        test_result.test_class = test_suite.suite_name
        test_result.test_name = matcher.group(1)
        test_result.current = self.state_machine.running_test_index + 1
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

        test_suites = self.state_machine.get_suites()
        if ERROR_EXCLAMATION in line:
            test_result.code = ResultCode.FAILED.value
        elif TIMEOUT_EXCLAMATION in line:
            test_result.code = ResultCode.BLOCKED.value

        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__failed__(LifeCycle.TestCase, result)
        self.state_machine.test().is_completed = True
        test_suite.test_num += 1
        test_suites.test_num += 1
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)
        self.state_machine.running_test_index += 1
