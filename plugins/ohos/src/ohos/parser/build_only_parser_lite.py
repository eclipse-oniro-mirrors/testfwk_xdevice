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
from ohos.parser import *
from ohos.constants import ParserType

__all__ = ["BuildOnlyParser"]


_COMPILE_PASSED = "compile PASSED"
_COMPILE_PARA = r"(.* compile .*)"

LOG = platform_logger("BuildOnlyParser")


@Plugin(type=Plugin.PARSER, id=ParserType.build_only_test)
class BuildOnlyParser(IParser):
    def __init__(self):
        self.state_machine = StateRecorder()
        self.suite_name = ""
        self.test_name = ""
        self.test_num = 0
        self.listeners = []
        self.output = ""

    def get_suite_name(self):
        return self.suite_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        if not self.state_machine.suites_is_started():
            self.state_machine.trace_logs.extend(lines)
        self.handle_suite_started_tag(self.test_num)

        self.state_machine.running_test_index = \
            self.state_machine.running_test_index + 1

        for line in lines:
            if re.match(_COMPILE_PARA, line):
                self.test_name = str(line).split('compile')[0].strip()
                test_result = self.state_machine.test(reset=True)
                test_result.run_time = 0
                test_result.test_class = self.suite_name
                test_result.test_name = self.test_name
                for listener in self.get_listeners():
                    result = copy.copy(test_result)
                    listener.__started__(LifeCycle.TestCase, result)
                if _COMPILE_PASSED in line:
                    test_result.code = ResultCode.PASSED.value
                    for listener in self.get_listeners():
                        result = copy.copy(test_result)
                        listener.__ended__(LifeCycle.TestCase, result)
                else:
                    test_result.code = ResultCode.FAILED.value
                    for listener in self.get_listeners():
                        result = copy.copy(test_result)
                        listener.__failed__(LifeCycle.TestCase, result)
        self.state_machine.test().is_completed = True

    def __done__(self):
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
