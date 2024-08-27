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
from ohos.parser.constants import parse_product_info

__all__ = ["CTestParser"]

_CTEST_START_TEST_RUN_TAG = "Framework inited."
_CTEST_END_TEST_RUN_TAG = "Framework finished."
_CTEST_SUITE_TEST_RUN_TAG = "Start to run test suite:"
_CTEST_SUITE_TIME_RUN_TAG = "Run test suite "
_CTEST_SETUP_TAG = "setup"
_CTEST_RUN_TAG = "-----------------------"


LOG = platform_logger("CTestParser")


@Plugin(type=Plugin.PARSER, id=ParserType.ctest_lite)
class CTestParser(IParser):
    last_line = ""
    pattern = r"(\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}\.\d{3}) "

    def __init__(self):
        self.state_machine = StateRecorder()
        self.suites_name = ""
        self.listeners = []
        self.product_info = {}
        self.is_params = False
        self.result_lines = []

    def get_suite_name(self):
        return self.suites_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        if not self.state_machine.suites_is_started():
            self.state_machine.trace_logs.extend(lines)
        for line in lines:
            self.parse(line)

    def __done__(self):
        suites = self.state_machine.get_suites()
        suites.is_completed = True

        for listener in self.get_listeners():
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name)
        self.state_machine.current_suites = None

    @staticmethod
    def _is_ctest_start_test_run(line):
        return True if line.endswith(_CTEST_START_TEST_RUN_TAG) else False

    @staticmethod
    def _is_ctest_end_test_run(line):
        return True if line.endswith(_CTEST_END_TEST_RUN_TAG) else False

    @staticmethod
    def _is_ctest_run(line):
        return re.match(r"[\s\S]*(Tests)[\s\S]*(Failures)[\s\S]*(Ignored)[\s\S]*", line)

    def _is_ctest_suite_test_run(self, line):
        return re.match("{}{}".format(self.pattern, _CTEST_SUITE_TEST_RUN_TAG),
                        line)

    def is_ctest_suite_time_run(self, line):
        return re.match("{}{}".format(self.pattern, _CTEST_SUITE_TIME_RUN_TAG),
                        line)

    def _process_ctest_suite_test_run_line(self, line):
        _, message_index = re.match(
            "{}{}".format(self.pattern, _CTEST_SUITE_TEST_RUN_TAG),
            line).span()
        self.handle_suite_started_tag(line[message_index:].strip())

    @staticmethod
    def _is_execute_result_line(line):
        return re.match(
            r"(.*" + "\\.c:" + "\\d+:.*:(PASS|FAIL|OK|IGNORE"")\\.*)",
            line.strip())

    @staticmethod
    def _is_result_line(line):
        return line.find("PASS") != -1 or line.find("FAIL") != -1 or line.find(
            "IGNORE") != -1

    def parse(self, line):
        parse_product_info(line, self.is_params, self.product_info)

        if self.state_machine.suites_is_started() or \
                self._is_ctest_start_test_run(line):
            try:
                test_matcher = re.match(r".*(\d+ Tests).+", line)
                failed_matcher = \
                    re.match(r".*(Failures).*", line)
                ignore_matcher = \
                    re.match(r".*(Ignored).*", line)
                if (test_matcher or failed_matcher or ignore_matcher) and \
                        not self._is_ctest_run(line):
                    if test_matcher:
                        self.result_lines.append(test_matcher.group(1))
                    if failed_matcher:
                        self.result_lines.append(failed_matcher.group(1))
                    if ignore_matcher:
                        self.result_lines.append(ignore_matcher.group(1))
                        line = " ".join(self.result_lines)
                        self.result_lines.clear()
                if self._is_ctest_start_test_run(line):
                    self.handle_suites_started_tag()
                elif self._is_ctest_end_test_run(line):
                    self.process_suites_ended_tag()
                elif self._is_ctest_run(line):
                    self.handle_suite_ended_tag(line)
                elif self._is_ctest_suite_test_run(line) and \
                        not self.state_machine.suite_is_running():
                    self._process_ctest_suite_test_run_line(line)
                elif self.is_ctest_suite_time_run(line) and \
                        not self.state_machine.suite_is_running():
                    self.handle_suite_started_tag(line)
                elif self._is_result_line(line) and \
                        self.state_machine.suite_is_running():
                    if line.find(":") != -1 and line.count(
                            ":") >= 3 and self._is_execute_result_line(line):
                        self.handle_one_test_tag(line.strip(), False)
                    else:
                        self.handle_one_test_tag(line.strip(), True)
            except AttributeError as _:
                LOG.error("Parsing log: %s failed" % (line.strip()),
                          error_no="00405")
            self.last_line = line

    def parse_error_test_description(self, message):
        end_time = re.match(self.pattern, message).group().strip()
        start_time = re.match(self.pattern,
                              self.last_line.strip()).group().strip()
        start_timestamp = int(time.mktime(
            time.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            start_time.split(".")[-1])
        end_timestamp = int(time.mktime(
            time.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            end_time.split(".")[-1])
        run_time = end_timestamp - start_timestamp
        status_dict = {"PASS": ResultCode.PASSED, "FAIL": ResultCode.FAILED,
                       "IGNORE": ResultCode.SKIPPED}
        status = ""
        if message.find("PASS") != -1:
            status = "PASS"
        elif message.find("FAIL") != -1:
            status = "FAIL"
        elif message.find("IGNORE") != -1:
            status = "IGNORE"
        status = status_dict.get(status)
        details = ("", "", status, run_time)
        return details

    def parse_test_description(self, message):

        test_class = message.split(".c:")[0].split(" ")[-1].split("/")[-1]
        message_index = message.index(".c:")
        end_time = re.match(self.pattern, message).group().strip()
        start_time = re.match(self.pattern,
                              self.last_line.strip()).group().strip()
        start_timestamp = int(time.mktime(
            time.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            start_time.split(".")[-1])
        end_timestamp = int(time.mktime(
            time.strptime(end_time, "%Y-%m-%d %H:%M:%S.%f"))) * 1000 + int(
            end_time.split(".")[-1])
        run_time = end_timestamp - start_timestamp
        message_list = message[message_index + 3:].split(":")
        test_name, status = message_list[1].strip(), message_list[2].strip()
        status_dict = {"PASS": ResultCode.PASSED, "FAIL": ResultCode.FAILED,
                       "IGNORE": ResultCode.SKIPPED}
        status = status_dict.get(status)
        details = (test_class, test_name, status, run_time)
        return details

    def handle_one_test_tag(self, message, is_error):
        if is_error:
            test_class, test_name, status, run_time = \
                self.parse_error_test_description(message)
        else:
            test_class, test_name, status, run_time = \
                self.parse_test_description(message)
        test_result = self.state_machine.test(reset=True)
        test_result.test_class = self.state_machine.suite().suite_name
        test_result.test_name = test_name
        test_result.run_time = run_time
        self.state_machine.running_test_index += 1
        test_result.current = self.state_machine.running_test_index
        test_result.code = status.value
        self.state_machine.suite().run_time += run_time
        for listener in self.get_listeners():
            test_result = copy.copy(test_result)
            listener.__started__(LifeCycle.TestCase, test_result)

        test_suite = self.state_machine.suite()
        test_suites = self.state_machine.get_suites()

        found_unexpected_test = False

        if found_unexpected_test or ResultCode.FAILED == status:
            if "FAIL:" in message and not message.endswith("FAIL:"):
                test_result.stacktrace = message[
                                         message.rindex("FAIL:") + len(
                                             "FAIL:"):]
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__failed__(LifeCycle.TestCase, result)
        elif ResultCode.SKIPPED == status:
            for listener in self.get_listeners():
                result = copy.copy(test_result)
                listener.__failed__(LifeCycle.TestCase, result)

        self.state_machine.test().is_completed = True
        test_suite.test_num += 1
        test_suites.test_num += 1

        for listener in self.get_listeners():
            result = copy.copy(test_result)
            listener.__ended__(LifeCycle.TestCase, result)

    def handle_suites_started_tag(self):
        self.state_machine.get_suites(reset=True)
        test_suites = self.state_machine.get_suites()
        test_suites.suites_name = self.suites_name
        test_suites.test_num = 0
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suites)
            listener.__started__(LifeCycle.TestSuites, suite_report)

    def handle_suite_started_tag(self, message):
        if re.match("{}{}".format(self.pattern, _CTEST_SUITE_TIME_RUN_TAG),
                    message.strip()):
            message = self.state_machine.suite().suite_name
        self.state_machine.suite(reset=True)
        test_suite = self.state_machine.suite()
        test_suite.suite_name = message
        test_suite.test_num = 0
        for listener in self.get_listeners():
            suite_report = copy.copy(test_suite)
            listener.__started__(LifeCycle.TestSuite, suite_report)

    def handle_suite_ended_tag(self, line):
        suite_result = self.state_machine.suite()
        suites = self.state_machine.get_suites()
        suite_result.run_time = suite_result.run_time
        suites.run_time += suite_result.run_time
        suite_result.is_completed = True

        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)
        self.state_machine.running_test_index = 0

    def process_suites_ended_tag(self):
        suites = self.state_machine.get_suites()
        suites.is_completed = True

        for listener in self.get_listeners():
            listener.__ended__(LifeCycle.TestSuites, test_result=suites,
                               suites_name=suites.suites_name)

    def append_test_output(self, message):
        if self.state_machine.test().stacktrace:
            self.state_machine.test().stacktrace = "{}\r\n".format(
                self.state_machine.test().stacktrace)
        self.state_machine.test().stacktrace = "{}{}".format(
            self.state_machine.test().stacktrace, message)
