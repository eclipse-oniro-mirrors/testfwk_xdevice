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

__all__ = ["CppTestParser", "CppTestListParser"]

_INFORMATIONAL_MARKER = "[----------]"
_START_TEST_RUN_MARKER = "[==========] Running"
_TEST_RUN_MARKER = "[==========]"
_GTEST_DRYRUN_MARKER = "Running main() "
_START_TEST_MARKER = "[ RUN      ]"
_OK_TEST_MARKER = "[       OK ]"
_SKIPPED_TEST_MARKER = "[  SKIPPED ]"
_FAILED_TEST_MARKER = "[  FAILED  ]"
_ALT_OK_MARKER = "[    OK    ]"
_TIMEOUT_MARKER = "[ TIMEOUT  ]"
_SIGNAL_CORE_DUMPED = r'Signal \d+ \(core dumped\)'


LOG = platform_logger("CppTestParser")


@Plugin(type=Plugin.PARSER, id=CommonParserType.cpptest)
class CppTestParser(IParser):
    def __init__(self):
        self.state_machine = StateRecorder()
        self.suite_name = ""
        self.listeners = []
        self.product_info = {}
        self.is_params = False
        self.result_data = ""
        self.start_time = get_cst_time()
        self.suite_start_time = get_cst_time()

    def get_suite_name(self):
        return self.suite_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        if not self.state_machine.suites_is_started():
            self.state_machine.trace_logs.extend(lines)
        for line in lines:
            line = str(line).strip().rstrip("\r")
            LOG.debug(line)
            self.parse(line)

    def __done__(self):
        suite_result = self.state_machine.get_suites()
        if not suite_result.suites_name:
            return
        for listener in self.get_listeners():
            suites = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name,
                               product_info=suites.product_info)
        self.state_machine.current_suites = None

    def parse(self, line):
        if self.state_machine.suites_is_started() or line.startswith(
                _TEST_RUN_MARKER):
            if line.startswith(_START_TEST_RUN_MARKER):
                message = line[len(_TEST_RUN_MARKER):].strip()
                self.handle_suites_started_tag(message)
            elif line.startswith(_INFORMATIONAL_MARKER):
                pattern = r"(.*) (\(\d+ ms total\))"
                message = line[len(_INFORMATIONAL_MARKER):].strip()
                if re.match(pattern, line.strip()):
                    self.handle_suite_ended_tag(message)
                elif re.match(r'(\d+) tests? from (.*)', message):
                    self.handle_suite_started_tag(message)
            elif line.startswith(_TEST_RUN_MARKER):
                if not self.state_machine.suites_is_running():
                    return
                message = line[len(_TEST_RUN_MARKER):].strip()
                self.handle_suites_ended_tag(message)
            elif line.startswith(_START_TEST_MARKER):
                # Individual test started
                message = line[len(_START_TEST_MARKER):].strip()
                self.handle_test_started_tag(message)
            else:
                self.process_test(line)

    def process_test(self, line):
        if _SKIPPED_TEST_MARKER in line:
            message = line[line.index(_SKIPPED_TEST_MARKER) + len(
                _SKIPPED_TEST_MARKER):].strip()
            if not self.state_machine.test_is_running():
                LOG.error(
                    "Found {} without {} before, wrong GTest log format".
                        format(line, _START_TEST_MARKER))
                return
            self.handle_test_ended_tag(message, ResultCode.SKIPPED)
        elif _OK_TEST_MARKER in line:
            message = line[line.index(_OK_TEST_MARKER) + len(
                _OK_TEST_MARKER):].strip()
            if not self.state_machine.test_is_running():
                LOG.error(
                    "Found {} without {} before, wrong GTest log format".
                        format(line, _START_TEST_MARKER))
                return
            self.handle_test_ended_tag(message, ResultCode.PASSED)
        elif _ALT_OK_MARKER in line:
            message = line[line.index(_ALT_OK_MARKER) + len(
                _ALT_OK_MARKER):].strip()
            self.fake_run_marker(message)
            self.handle_test_ended_tag(message, ResultCode.PASSED)
        elif _FAILED_TEST_MARKER in line:
            message = line[line.index(_FAILED_TEST_MARKER) + len(
                _FAILED_TEST_MARKER):].strip()
            if not self.state_machine.suite_is_running():
                return
            if not self.state_machine.test_is_running():
                self.fake_run_marker(message)
            self.handle_test_ended_tag(message, ResultCode.FAILED)
        elif _TIMEOUT_MARKER in line:
            message = line[line.index(_TIMEOUT_MARKER) + len(
                _TIMEOUT_MARKER):].strip()
            self.fake_run_marker(message)
            self.handle_test_ended_tag(message, ResultCode.FAILED)
        elif self.state_machine.test_is_running():
            self.append_test_output(line)

    def handle_test_suite_failed(self, error_msg):
        error_msg = "Unknown error" if error_msg is None else error_msg
        LOG.info("Test run failed: {}".format(error_msg))
        if self.state_machine.test_is_running():
            self.state_machine.test().is_completed = True
            for listener in self.get_listeners():
                test_result = copy.copy(self.currentTestResult)
                listener.__failed__(LifeCycle.TestCase, test_result)
                listener.__ended__(LifeCycle.TestCase, test_result)
        self.state_machine.suite().stacktrace = error_msg
        self.state_machine.suite().is_completed = True
        for listener in self.get_listeners():
            suite_result = copy.copy(self.currentSuiteResult)
            listener.__failed__(LifeCycle.TestSuite, suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite_result)

    def handle_test_started_tag(self, message):
        test_class, test_name, _ = self.parse_test_description(
            message)
        test_result = self.state_machine.test(reset=True)
        test_result.test_class = test_class
        test_result.test_name = test_name
        self.start_time = get_cst_time()
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

    @classmethod
    def parse_test_description(cls, message):
        run_time = 0
        matcher = re.match(r'(.*) \((\d+) ms\)', message)
        if matcher:
            test_class, test_name = matcher.group(1).rsplit(".", 1)
            run_time = int(matcher.group(2))
        else:
            test_class, test_name = message.rsplit(".", 1)
        return test_class, test_name, run_time

    def handle_test_ended_tag(self, message, test_status):
        test_class, test_name, run_time = self.parse_test_description(
            message)
        test_result = self.state_machine.test()
        test_result.run_time = get_delta_time_ms(self.start_time)
        if test_result.run_time == 0 or test_result.run_time < run_time:
            test_result.run_time = run_time
        test_result.code = test_status.value
        test_result.current = self.state_machine.running_test_index + 1
        if not test_result.is_running():
            LOG.error(
                "Test has no start tag when trying to end test: %s", message)
            return
        found_unexpected_test = False
        if test_result.test_class != test_class:
            LOG.error(
                "Expected class: {} but got:{} ".format(test_result.test_class,
                                                        test_class))
            found_unexpected_test = True
        if test_result.test_name != test_name:
            LOG.error(
                "Expected test: {} but got: {}".format(test_result.test_name,
                                                       test_name))
            found_unexpected_test = True

        if found_unexpected_test or ResultCode.FAILED == test_status:
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__failed__(LifeCycle.TestCase, result)
        elif ResultCode.SKIPPED == test_status:
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__skipped__(LifeCycle.TestCase, result)

        self.state_machine.test().is_completed = True
        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)
        self.state_machine.running_test_index += 1

    def fake_run_marker(self, message):
        fake_marker = re.compile(" +").split(message)
        self.handle_test_started_tag(fake_marker)

    def handle_suites_started_tag(self, message):
        self.state_machine.get_suites(reset=True)
        matcher = re.match(r'Running (\d+) tests? from .*', message)
        expected_test_num = int(matcher.group(1)) if matcher else -1
        if expected_test_num >= 0:
            test_suites = self.state_machine.get_suites()
            test_suites.suites_name = self.get_suite_name()
            test_suites.test_num = expected_test_num
            test_suites.product_info = self.product_info
            for listener in self.get_listeners():
                suite_report = copy.copy(test_suites)
                listener.__started__(LifeCycle.TestSuites, suite_report)

    def handle_suite_started_tag(self, message):
        self.state_machine.suite(reset=True)
        matcher = re.match(r'(\d+) tests? from (.*)', message)
        expected_test_num = int(matcher.group(1)) if matcher else -1
        if expected_test_num >= 0:
            test_suite = self.state_machine.suite()
            test_suite.suite_name = matcher.group(2)
            test_suite.test_num = expected_test_num
            self.suite_start_time = get_cst_time()
            for listener in self.get_listeners():
                suite_report = copy.copy(test_suite)
                listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_ended_tag(self, message):
        self.state_machine.running_test_index = 0
        suite_result = self.state_machine.suite()
        suite_result.run_time = get_delta_time_ms(self.suite_start_time)
        matcher = re.match(r'.*\((\d+) ms total\)', message)
        if matcher and suite_result.run_time == 0:
            suite_result.run_time = int(matcher.group(1))
        suite_result.is_completed = True
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def handle_suites_ended_tag(self, message):
        suites = self.state_machine.get_suites()
        matcher = re.match(r'.*\((\d+) ms total\)', message)
        if matcher:
            suites.run_time = int(matcher.group(1))
        suites.is_completed = True
        for listener in self.get_listeners():
            copy_suites = copy.copy(suites)
            listener.__ended__(LifeCycle.TestSuites, test_result=copy_suites,
                               suites_name=suites.suites_name,
                               product_info=suites.product_info,
                               suite_report=True)

    def append_test_output(self, message):
        test_result = self.state_machine.test()
        if test_result.stacktrace:
            test_result.stacktrace += "\r\n"
        test_result.stacktrace += message
        if re.match(_SIGNAL_CORE_DUMPED, message):
            # 构造临时字符串，复用test_ended里的方法
            temp = f'{test_result.test_class}.{test_result.test_name} (0 ms)'
            self.handle_test_ended_tag(temp, ResultCode.BLOCKED)
            self.handle_suite_ended_tag('')

    @staticmethod
    def handle_test_run_failed(error_msg):
        if not error_msg:
            error_msg = "Unknown error"
        if not check_pub_key_exist():
            LOG.debug("Error msg:%s" % error_msg)

    def mark_test_as_blocked(self, test):
        if not self.state_machine.current_suite and not test.class_name:
            return
        suites_result = self.state_machine.get_suites(reset=True)
        suites_result.suites_name = self.get_suite_name()
        suite_name = self.state_machine.current_suite.suite_name if \
            self.state_machine.current_suite else None
        suite_result = self.state_machine.suite(reset=True)
        test_result = self.state_machine.test(reset=True)
        suite_result.suite_name = suite_name or test.class_name
        suite_result.suite_num = 1
        test_result.test_class = test.class_name
        test_result.test_name = test.test_name
        test_result.stacktrace = "error_msg: run crashed"
        test_result.num_tests = 1
        test_result.run_time = 0
        test_result.code = ResultCode.BLOCKED.value
        for listener in self.get_listeners():
            suite_report = copy.copy(suites_result)
            listener.__started__(LifeCycle.TestSuites, suite_report)
        for listener in self.get_listeners():
            suite_report = copy.copy(suite_result)
            listener.__started__(LifeCycle.TestSuite, suite_report)
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, test_result)
        for listener in self.get_listeners():
            suite_report = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite_report,
                               is_clear=True)
        self.__done__()


@Plugin(type=Plugin.PARSER, id=CommonParserType.cpptest_list)
class CppTestListParser(IParser):
    def __init__(self):
        self.last_test_class_name = None
        self.tests = []
        self.result_data = ""
        self.suites = dict()

    def __process__(self, lines):
        for line in lines:
            if line.endswith("\r") or line.endswith("\n"):
                line = str(line).replace("\r", "").replace("\n", "")
            line = line.rstrip()
            self.result_data = "{}{}\n".format(self.result_data, line)
            self.parse(line)

    def __done__(self):
        LOG.debug("CPPTestListParser data:")
        LOG.debug(self.result_data)
        self.result_data = ""

    def parse(self, line):
        class_matcher = re.match('^([a-zA-Z]+.*)\\.$', line)
        method_matcher = re.match('\s+([a-zA-Z_]+\S*)(.*)?(\s+.*)?$', line)
        if class_matcher:
            self.last_test_class_name = class_matcher.group(1)
            if self.last_test_class_name not in self.suites:
                self.suites.setdefault(self.last_test_class_name, [])
        elif method_matcher:
            if not self.last_test_class_name:
                LOG.error("Parsed new test case name %s but no test class name"
                          " has been set" % line)
            else:
                test_name = method_matcher.group(1)
                if test_name not in self.suites.get(self.last_test_class_name, []):
                    test = TestDescription(self.last_test_class_name,
                                           test_name)
                    self.tests.append(test)
                    self.suites.get(self.last_test_class_name, []).append(test_name)
                else:
                    LOG.debug("[{}.{}] has already collect it, skip it.".format(
                        self.last_test_class_name, test_name))
        else:
            if not check_pub_key_exist():
                LOG.debug("Line ignored: %s" % line)
