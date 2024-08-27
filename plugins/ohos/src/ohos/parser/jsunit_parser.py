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

__all__ = ["JSUnitParser"]


_START_JSUNIT_RUN_MARKER = "[start] start run suites"
_START_JSUNIT_SUITE_RUN_MARKER = "[suite start]"
_START_JSUNIT_SUITE_END_MARKER = "[suite end]"
_END_JSUNIT_RUN_MARKER = "[end] run suites end"
_PASS_JSUNIT_MARKER = "[pass]"
_FAIL_JSUNIT_MARKER = "[fail]"
_ERROR_JSUNIT_MARKER = "[error]"
_ACE_LOG_MARKER = [" a0c0d0", " a03d00"]


LOG = platform_logger("JSUnitParser")


@Plugin(type=Plugin.PARSER, id=CommonParserType.jsunit)
class JSUnitParser(IParser):
    last_line = ""
    pattern = r"(\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}\.\d{3}) "

    def __init__(self):
        self.state_machine = StateRecorder()
        self.suites_name = ""
        self.listeners = []
        self.expect_tests_dict = dict()
        self.marked_suite_set = set()
        self.exclude_list = list()
        self.ace_log_marker = ""

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
        if (self.state_machine.suites_is_started() or line.find(
                _START_JSUNIT_RUN_MARKER) != -1) and \
                self._is_match_marker(line):
            if line.find(_START_JSUNIT_RUN_MARKER) != -1:
                self.handle_suites_started_tag()
            elif line.endswith(_END_JSUNIT_RUN_MARKER):
                self.handle_suites_ended_tag()
            elif line.find(_START_JSUNIT_SUITE_RUN_MARKER) != -1:
                self.handle_suite_started_tag(line.strip())
            elif line.endswith(_START_JSUNIT_SUITE_END_MARKER):
                self.handle_suite_ended_tag()
            elif _PASS_JSUNIT_MARKER in line or _FAIL_JSUNIT_MARKER \
                    in line or _ERROR_JSUNIT_MARKER in line:
                self.handle_one_test_tag(line.strip())
            self.last_line = line

    def parse_test_description(self, message):
        pattern = r".*\[(pass|fail|error)\]"
        year = time.strftime("%Y")
        filter_message = message
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
        match = re.match(pattern, filter_message)
        _, status_end_index = match.span()
        if " ;" in filter_message:
            test_name = filter_message[status_end_index:
                                       str(filter_message).find(" ;")]
        else:
            test_name = filter_message[status_end_index:]
        status_dict = {"pass": ResultCode.PASSED, "fail": ResultCode.FAILED,
                       "ignore": ResultCode.SKIPPED,
                       "error": ResultCode.FAILED}
        status = status_dict.get(match.group(1))
        return test_name.strip(), status, run_time

    def handle_suites_started_tag(self):
        self.state_machine.get_suites(reset=True)
        test_suites = self.state_machine.get_suites()
        test_suites.suites_name = self.suites_name
        test_suites.test_num = 0
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suites)
            listener.__started__(LifeCycle.TestSuites, suite_report)

    def handle_suites_ended_tag(self):
        self._mark_all_test_case()
        suites = self.state_machine.get_suites()
        suites.is_completed = True

        for listener in self.get_listeners():
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name)

    def handle_one_test_tag(self, message):
        test_name, status, run_time = \
            self.parse_test_description(message)
        test_suite = self.state_machine.suite()
        if self.exclude_list:
            qualified_name = "{}#{}".format(test_suite.suite_name, test_name)
            if qualified_name in self.exclude_list:
                LOG.debug("{} will be discard!".format(qualified_name))
                test_suite.test_num -= 1
                return
        test_result = self.state_machine.test(reset=True)
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
        if not hasattr(test_suite, "total_cases"):
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
        self.state_machine.running_test_index = 0
        test_suite = self.state_machine.suite()
        if "total cases:" in message:
            m_result = re.match(r".*\[suite start](.+), total cases: (\d+)",
                                message)
            if m_result:
                expect_test_num = m_result.group(2)
                test_suite.suite_name = m_result.group(1)
                test_suite.test_num = int(expect_test_num)
                setattr(test_suite, "total_cases", True)

        else:
            if re.match(r".*\[suite start].*", message):
                _, index = re.match(r".*\[suite start]", message).span()
                if message[index:]:
                    test_suite.suite_name = message[index:]
                else:
                    test_suite.suite_name = self.suite_name
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
        self._mark_test_case(suite_result, self.get_listeners())
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def append_test_output(self, message):
        if self.state_machine.test().stacktrace:
            self.state_machine.test().stacktrace = \
                "%s\r\n" % self.state_machine.test().stacktrace
        self.state_machine.test().stacktrace = \
            ''.join((self.state_machine.test().stacktrace, message))

    def _mark_test_case(self, suite, listeners):
        if not self.expect_tests_dict:
            return
        tests_list = []
        for listener in listeners:
            if listener.__class__.__name__ == "ReportListener":
                tests_list.extend(listener.tests.values())
                break
        test_name_list = []
        for item_test in tests_list:
            test_name_list.append(item_test.test_name)
        self.marked_suite_set.add(suite.suite_name)
        test_in_cur = self.expect_tests_dict.get(suite.suite_name, [])
        for test in test_in_cur:
            if "{}#{}".format(suite.suite_name, test.test_name) \
                    in self.exclude_list:
                suite.test_num -= 1
                continue
            if test.test_name not in test_name_list:
                self._mock_test_case_life_cycle(listeners, test)

    def _mock_test_case_life_cycle(self, listeners, test):
        test_result = self.state_machine.test(reset=True)
        test_result.test_class = test.class_name
        test_result.test_name = test.test_name
        test_result.stacktrace = "error_msg: mark blocked"
        test_result.num_tests = 1
        test_result.run_time = 0
        test_result.current = self.state_machine.running_test_index + 1
        test_result.code = ResultCode.BLOCKED.value
        test_result = copy.copy(test_result)
        for listener in listeners:
            listener.__started__(LifeCycle.TestCase, test_result)
        test_result = copy.copy(test_result)
        for listener in listeners:
            listener.__ended__(LifeCycle.TestCase, test_result)
        self.state_machine.running_test_index += 1

    def _mark_all_test_case(self):
        if not self.expect_tests_dict:
            return
        all_suite_set = set(self.expect_tests_dict.keys())
        un_suite_set = all_suite_set.difference(self.marked_suite_set)
        for un_suite_name in un_suite_set:
            test_list = self.expect_tests_dict.get(un_suite_name, [])

            self.state_machine.suite(reset=True)
            self.state_machine.running_test_index = 0
            test_suite = self.state_machine.suite()
            test_suite.suite_name = un_suite_name
            test_suite.test_num = len(test_list)
            for listener in self.get_listeners():
                suite_report = copy.copy(test_suite)
                listener.__started__(LifeCycle.TestSuite, suite_report)

            for test in test_list:
                if "{}#{}".format(test_suite.suite_name, test.test_name) \
                        in self.exclude_list:
                    test_suite.test_num -= 1
                    continue
                self._mock_test_case_life_cycle(self.get_listeners(), test)

            test_suite.is_completed = True
            for listener in self.get_listeners():
                suite = copy.copy(test_suite)
                listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def _is_match_marker(self, line):
        if self.ace_log_marker:
            return line.lower().find(self.ace_log_marker) != -1
        else:
            for mark_str in _ACE_LOG_MARKER:
                if line.lower().find(mark_str) != -1:
                    self.ace_log_marker = mark_str
                    return True
            return False
