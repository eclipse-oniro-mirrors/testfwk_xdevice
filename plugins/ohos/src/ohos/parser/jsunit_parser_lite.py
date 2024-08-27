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

__all__ = ["JSUnitParserLite"]

_START_JSUNIT_RUN_MARKER = "[start] start run suites"
_START_JSUNIT_SUITE_RUN_MARKER = "[suite start]"
_START_JSUNIT_SUITE_END_MARKER = "[suite end]"
_END_JSUNIT_RUN_MARKER = "[end] run suites end"
_PASS_JSUNIT_MARKER = "[%s]" % "pass"
_FAIL_JSUNIT_MARKER = "[fail]"
_ACE_LOG_MARKER = "[Console Info]"

LOG = platform_logger("JSUnitParserLite")


@Plugin(type=Plugin.PARSER, id=ParserType.jsuit_test_lite)
class JSUnitParserLite(IParser):
    last_line = ""
    pattern = r"(\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}\.\d{3}) "

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
        if (self.state_machine.suites_is_started() or
            line.find(_START_JSUNIT_RUN_MARKER) != -1) and \
                line.find(_ACE_LOG_MARKER) != -1:
            if line.find(_START_JSUNIT_RUN_MARKER) != -1:
                self.handle_suites_started_tag()
            elif line.endswith(_END_JSUNIT_RUN_MARKER):
                self.handle_suites_ended_tag()
            elif line.find(_START_JSUNIT_SUITE_RUN_MARKER) != -1:
                self.handle_suite_started_tag(line.strip())
            elif line.endswith(_START_JSUNIT_SUITE_END_MARKER):
                self.handle_suite_ended_tag()
            elif _PASS_JSUNIT_MARKER in line or _FAIL_JSUNIT_MARKER \
                    in line:
                self.handle_one_test_tag(line.strip())
            self.last_line = line

    def parse_test_description(self, message):
        pattern = r"\[(pass|fail)\]"
        year = time.strftime("%Y")
        filter_message = message.split("[Console Info]")[1].strip()
        end_time = "%s-%s" % \
                   (year, re.match(self.pattern, message).group().strip())
        start_time = "%s-%s" % \
                     (year, re.match(self.pattern,
                                     self.last_line.strip()).group().strip())
        start_timestamp = int(time.mktime(
            time.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            start_time.split(".")[-1])
        end_timestamp = int(time.mktime(
            time.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            end_time.split(".")[-1])
        run_time = end_timestamp - start_timestamp
        _, status_end_index = re.match(pattern, filter_message).span()
        status = filter_message[:status_end_index]
        test_name = filter_message[status_end_index:]
        status_dict = {"pass": ResultCode.PASSED, "fail": ResultCode.FAILED,
                       "ignore": ResultCode.SKIPPED}
        status = status_dict.get(status[1:-1])
        return test_name, status, run_time

    def handle_suites_started_tag(self):
        self.state_machine.get_suites(reset=True)
        test_suites = self.state_machine.get_suites()
        test_suites.suites_name = self.suites_name
        test_suites.test_num = 0
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
        test_name, status, run_time = \
            self.parse_test_description(message)
        test_result = self.state_machine.test(reset=True)
        test_suite = self.state_machine.suite()
        test_result.test_class = test_suite.suite_name
        test_result.test_name = test_name
        test_result.run_time = run_time
        test_result.code = status.value
        test_result.current = self.state_machine.running_test_index + 1
        self.state_machine.suite().run_time += run_time
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

        test_suites = self.state_machine.get_suites()
        found_unexpected_test = False

        if found_unexpected_test or ResultCode.FAILED == status:
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__failed__(LifeCycle.TestCase, result)
        elif ResultCode.SKIPPED == status:
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__skipped__(LifeCycle.TestCase, result)

        self.state_machine.test().is_completed = True
        test_suite.test_num += 1
        test_suites.test_num += 1
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)
        self.state_machine.running_test_index += 1

    def fake_run_marker(self, message):
        fake_marker = re.compile(" +").split(message)
        self.processTestStartedTag(fake_marker)

    def handle_suite_started_tag(self, message):
        self.state_machine.suite(reset=True)
        test_suite = self.state_machine.suite()
        if re.match(r".*\[suite start\].*", message):
            _, index = re.match(r".*\[suite start\]", message).span()
        test_suite.suite_name = message[index:]
        test_suite.test_num = 0
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

    def append_test_output(self, message):
        if self.state_machine.test().stacktrace:
            self.state_machine.test().stacktrace = \
                "%s\r\n" % self.state_machine.test().stacktrace
        self.state_machine.test().stacktrace = \
            ''.join((self.state_machine.test().stacktrace, message))
