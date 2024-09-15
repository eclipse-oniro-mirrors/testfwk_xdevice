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

__all__ = ["OHYaraTestParser"]

LOG = platform_logger("OHYaraTestParser")


@Plugin(type=Plugin.PARSER, id=CommonParserType.oh_yara)
class OHYaraTestParser(IParser):
    last_line = ""
    pattern = r"(\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}\.\d{3}) "

    def __init__(self):
        self.state_machine = StateRecorder()
        self.suites_name = ""
        self.vul_items = None
        self.listeners = []

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        self.parse(lines)

    def __done__(self):
        pass

    def parse(self, lines):
        for line in lines:
            if line:
                self.handle_suites_started_tag()
                self.handle_suite_started_tag()
                self.handle_one_test_tag(line)
                self.handle_suite_ended_tag()
                self.handle_suites_ended_tag()

    def handle_suites_started_tag(self):
        self.state_machine.get_suites(reset=True)
        test_suites = self.state_machine.get_suites()
        test_suites.suites_name = self.suites_name
        test_suites.test_num = len(self.vul_items)
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suites)
            listener.__started__(LifeCycle.TestSuites, suite_report)

    def handle_suites_ended_tag(self):
        suites = self.state_machine.get_suites()
        suites.is_completed = True
        for listener in self.get_listeners():
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name)

    def handle_one_test_tag(self, message):
        status_dict = {"pass": ResultCode.PASSED, "fail": ResultCode.FAILED,
                       "block": ResultCode.BLOCKED}
        message = message.strip().split("|")
        test_name = message[0]
        status = status_dict.get(message[3])
        trace = message[6] if message[3] else ""
        run_time = 0
        test_suite = self.state_machine.suite()
        test_result = self.state_machine.test(reset=True)
        test_result.test_class = test_suite.suite_name
        test_result.test_name = test_name
        test_result.run_time = run_time
        test_result.code = status.value
        test_result.stacktrace = trace
        test_result.current = self.state_machine.running_test_index + 1
        self.state_machine.suite().run_time += run_time
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

        test_suites = self.state_machine.get_suites()
        self.state_machine.test().is_completed = True
        test_suites.test_num += 1
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)
        self.state_machine.running_test_index += 1

    def handle_suite_started_tag(self):
        self.state_machine.suite(reset=True)
        self.state_machine.running_test_index = 0
        test_suite = self.state_machine.suite()
        test_suite.suite_name = self.suites_name
        test_suite.test_num = 1
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suite)
            listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_ended_tag(self):
        suite_result = self.state_machine.suite()
        suites = self.state_machine.get_suites()
        suite_result.run_time = suite_result.run_time
        suites.run_time += suite_result.run_time
        suite_result.is_completed = True
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)
