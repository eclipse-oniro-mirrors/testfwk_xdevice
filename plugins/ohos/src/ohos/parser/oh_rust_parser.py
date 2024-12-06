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

__all__ = ["OHRustTestParser"]

LOG = platform_logger("Parser")


@Plugin(type=Plugin.PARSER, id=CommonParserType.oh_rust)
class OHRustTestParser(IParser):

    def __init__(self):
        self.test_pattern = "test (?:tests::)?(.+) ... (ok|FAILED)"
        self.stout_pattern = "---- tests::(.+) stdout ----"
        self.running_pattern = "running (\\d+) test|tests"
        self.test_result_pattern = \
            "test result: (ok|FAILED)\\..+finished in (.+)s"
        self.suite_name = ""
        self.result_list = list()
        self.stdout_list = list()
        self.failures_stdout = list()
        self.cur_fail_case = ""
        self.state_machine = StateRecorder()
        self.listeners = []

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        for line in lines:
            LOG.debug(line)
            self.parse(line)

    def __done__(self):
        self.handle_suite_end()

    def parse(self, line):
        if line.startswith("running"):
            matcher = re.match(self.running_pattern, line)
            if not (matcher and matcher.group(1)):
                return
            self.handle_suite_start(matcher)
        elif line.startswith("test result:"):
            matcher = re.match(self.test_result_pattern, line)
            if not (matcher and matcher.group(2)):
                return
            self.handle_case_lifecycle(matcher)

        elif "..." in line:
            matcher = re.match(self.test_pattern, line)
            if not (matcher and matcher.group(1) and matcher.group(2)):
                return
            self.collect_case(matcher)
        elif line.startswith("---- tests::"):
            matcher = re.match(self.stout_pattern, line)
            if not (matcher and matcher.group(1)):
                return
            self.cur_fail_case = matcher.group(1)
        else:
            if self.cur_fail_case:
                self.handle_stdout(line)

    def handle_case_lifecycle(self, matcher):
        cost_time = matcher.group(2)
        for test_result in self.result_list:
            if test_result.code == ResultCode.FAILED.value:
                if self.stdout_list and \
                        self.stdout_list[0][0] == test_result.test_name:
                    test_result.stacktrace = self.stdout_list[0][1]
                    self.stdout_list.pop(0)
            test_result.current = self.state_machine.running_test_index + 1
            for listener in self.get_listeners():
                test_result = copy.copy(test_result)
                listener.__started__(LifeCycle.TestCase, test_result)
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__ended__(LifeCycle.TestCase, result)
        test_suite = self.state_machine.suite()
        test_suite.run_time = float(cost_time) * 1000

    def handle_stdout(self, line):
        if line.strip():
            self.failures_stdout.append(line.strip())
        else:
            self.stdout_list.append((self.cur_fail_case,
                                     " ".join(self.failures_stdout)))
            self.cur_fail_case = ""
            self.failures_stdout.clear()

    def collect_case(self, matcher):
        test_result = self.state_machine.test(reset=True)
        test_result.test_class = self.suite_name
        test_result.test_name = matcher.group(1)
        test_result.code = ResultCode.PASSED.value if \
            matcher.group(2) == "ok" else ResultCode.FAILED.value
        self.result_list.append(test_result)

    def handle_suite_start(self, matcher):
        self.state_machine.suite(reset=True)
        test_suite = self.state_machine.suite()
        test_suite.suite_name = self.suite_name
        test_suite.test_num = int(matcher.group(1))

        for listener in self.get_listeners():
            suite_report = copy.copy(test_suite)
            listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_end(self):
        suite_result = self.state_machine.suite()
        suite_result.run_time += suite_result.run_time
        suite_result.is_completed = True
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, suite_report=True)
