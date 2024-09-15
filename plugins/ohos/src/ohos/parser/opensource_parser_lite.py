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
from ohos.constants import ParserType


__all__ = ["OpenSourceParser"]

_TEST_PASSED_LOWER = "pass"


LOG = platform_logger("OpenSourceParser")


@Plugin(type=Plugin.PARSER, id=ParserType.open_source_test)
class OpenSourceParser(IParser):
    def __init__(self):
        self.state_machine = StateRecorder()
        self.suite_name = ""
        self.test_name = ""
        self.test_num = 1
        self.listeners = []
        self.output = ""
        self.lines = []
        self.start_time = None

    def get_suite_name(self):
        return self.suite_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        if not self.start_time:
            self.start_time = get_cst_time()
        self.lines.extend(lines)

    def __done__(self):
        if not self.state_machine.suites_is_started():
            self.state_machine.trace_logs.extend(self.lines)
        self.handle_suite_started_tag(self.test_num)

        test_result = self.state_machine.test(reset=True,
                                              test_index=self.test_name)
        test_result.run_time = 0
        test_result.test_class = self.suite_name
        test_result.test_name = self.test_name
        test_result.test_num = 1
        test_result.current = 1
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, result)
        for line in self.lines:
            self.output = "{}{}".format(self.output, line)
            if _TEST_PASSED_LOWER in line.lower():
                test_result.code = ResultCode.PASSED.value
                if self.start_time:
                    end_time = get_cst_time()
                    run_time = (end_time - self.start_time).total_seconds()
                    test_result.run_time = int(run_time * 1000)
                for listener in self.get_listeners():
                    result = copy.copy(test_result)
                    listener.__ended__(LifeCycle.TestCase, result)
                break
        else:
            test_result.code = ResultCode.FAILED.value
            test_result.stacktrace = "\\n".join(self.lines)
            if self.start_time:
                end_time = get_cst_time()
                run_time = (end_time - self.start_time).total_seconds()
                test_result.run_time = int(run_time * 1000)
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__ended__(LifeCycle.TestCase, result)

        self.state_machine.test().is_completed = True
        self.handle_suite_ended_tag()

    def handle_suite_started_tag(self, test_num):
        test_suite = self.state_machine.suite()
        if test_num >= 0:
            test_suite.suite_name = self.suite_name
            test_suite.test_num = test_num
            for listener in self.get_listeners():
                suite_report = copy.copy(test_suite)
                listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_ended_tag(self):
        suite_result = self.state_machine.suite()
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite,
                               suite_report=True)
