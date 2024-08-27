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
from ohos.parser.constants import StatusCodes

__all__ = ["JunitParser"]

LOG = platform_logger("JunitParser")


class Prefixes(Enum):
    STATUS = "INSTRUMENTATION_STATUS: "
    STATUS_CODE = "INSTRUMENTATION_STATUS_CODE: "
    STATUS_FAILED = "INSTRUMENTATION_FAILED: "
    CODE = "INSTRUMENTATION_CODE: "
    RESULT = "INSTRUMENTATION_RESULT: "
    TIME_REPORT = "Time: "


@Plugin(type=Plugin.PARSER, id=CommonParserType.junit)
class JunitParser(IParser):
    def __init__(self):
        self.state_machine = StateRecorder()
        self.suite_name = ""
        self.listeners = []
        self.current_key = None
        self.current_value = None
        self.start_time = get_cst_time()
        self.test_time = 0
        self.test_run_finished = False

    def get_suite_name(self):
        return self.suite_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        for line in lines:
            if not check_pub_key_exist():
                LOG.debug(line)
            self.parse(line)

    def __done__(self):
        suite_result = self.state_machine.suite()
        suite_result.run_time = self.test_time
        suite_result.is_completed = True
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite,
                               suite_report=True)
        self.state_machine.current_suite = None

    def parse(self, line):
        if line.startswith(Prefixes.STATUS_CODE.value):
            self.submit_current_key_value()
            self.parse_status_code(line)
        elif line.startswith(Prefixes.STATUS.value):
            self.submit_current_key_value()
            self.parse_key(line, len(Prefixes.STATUS.value))
        elif line.startswith(Prefixes.RESULT.value):
            self.test_run_finished = True
        elif line.startswith(Prefixes.STATUS_FAILED.value) or \
                line.startswith(Prefixes.CODE.value):
            self.submit_current_key_value()
            self.test_run_finished = True
        elif line.startswith(Prefixes.TIME_REPORT.value):
            self.parse_time(line)
        else:
            if self.current_key == "stack" and self.current_value:
                self.current_value = self.current_value + r"\r\n"
                self.current_value = self.current_value + line
            elif line:
                pass

    def parse_key(self, line, key_start_pos):
        key_value = line[key_start_pos:].split("=", 1)
        if len(key_value) == 2:
            self.current_key = key_value[0]
            self.current_value = key_value[1]

    def parse_time(self, line):
        message = line[len(Prefixes.TIME_REPORT.value):]
        self.test_time = float(message.replace(",", "")) * 1000

    @staticmethod
    def check_legality(name):
        if not name or name == "null":
            return False
        return True

    def parse_status_code(self, line):
        value = line[len(Prefixes.STATUS_CODE.value):]
        test_info = self.state_machine.test()
        test_info.code = int(value)
        if test_info.code != StatusCodes.IN_PROGRESS:
            if self.check_legality(test_info.test_class) and \
                    self.check_legality(test_info.test_name):
                self.report_result(test_info)
                self.clear_current_test_info()

    def clear_current_test_info(self):
        self.state_machine.current_test = None

    def submit_current_key_value(self):
        if self.current_key and self.current_value:
            status_value = self.current_value
            test_info = self.state_machine.test()
            if self.current_key == "class":
                test_info.test_class = status_value
            elif self.current_key == "test":
                test_info.test_name = status_value
            elif self.current_key == "numtests":
                test_info.num_tests = int(status_value)
            elif self.current_key == "Error":
                self.handle_test_run_failed(status_value)
            elif self.current_key == "stack":
                test_info.stacktrace = status_value
            elif self.current_key == "stream":
                pass
            self.current_key = None
            self.current_value = None

    def report_result(self, test_info):
        if not test_info.test_name or not test_info.test_class:
            LOG.info("Invalid instrumentation status bundle")
            return
        test_info.is_completed = True
        self.report_test_run_started(test_info)
        if test_info.code == StatusCodes.START.value:
            self.start_time = get_cst_time()
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                listener.__started__(LifeCycle.TestCase, result)
        elif test_info.code == StatusCodes.FAILURE.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                result.code = ResultCode.FAILED.value
                listener.__ended__(LifeCycle.TestCase, result)
        elif test_info.code == StatusCodes.ERROR.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                result.code = ResultCode.FAILED.value
                listener.__ended__(LifeCycle.TestCase, result)
        elif test_info.code == StatusCodes.SUCCESS.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                result.code = ResultCode.PASSED.value
                listener.__ended__(LifeCycle.TestCase, result)
        elif test_info.code == StatusCodes.IGNORE.value:
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                result.code = ResultCode.SKIPPED.value
                listener.__skipped__(LifeCycle.TestCase, result)
        elif test_info.code == StatusCodes.BLOCKED.value:
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                result.code = ResultCode.BLOCKED.value
                listener.__ended__(LifeCycle.TestCase, result)

        self.output_stack_trace(test_info)

    @classmethod
    def output_stack_trace(cls, test_info):
        if check_pub_key_exist():
            return
        if test_info.stacktrace:
            stack_lines = test_info.stacktrace.split(r"\r\n")
            LOG.error("Stacktrace information is:")
            for line in stack_lines:
                line.strip()
                if line:
                    LOG.error(line)

    def report_test_run_started(self, test_result):
        test_suite = self.state_machine.suite()
        if not self.state_machine.suite().is_started:
            if not test_suite.test_num or not test_suite.suite_name:
                test_suite.suite_name = self.get_suite_name()
                test_suite.test_num = test_result.num_tests
                for listener in self.get_listeners():
                    suite_report = copy.copy(test_suite)
                    listener.__started__(LifeCycle.TestSuite, suite_report)

    @staticmethod
    def handle_test_run_failed(error_msg):
        if not error_msg:
            error_msg = "Unknown error"
        if not check_pub_key_exist():
            LOG.debug("Error msg:%s" % error_msg)

    def mark_test_as_failed(self, test):
        test_info = self.state_machine.test()
        if test_info:
            test_info.test_class = test.class_name
            test_info.test_name = test.test_name
            test_info.code = StatusCodes.START.value
            self.report_result(test_info)
            test_info.code = StatusCodes.FAILURE.value
            self.report_result(test_info)
            self.__done__()

    def mark_test_as_blocked(self, test):
        test_info = self.state_machine.test()
        if test_info:
            test_info.test_class = test.class_name
            test_info.test_name = test.test_name
            test_info.num_tests = 1
            test_info.run_time = 0
            test_info.code = StatusCodes.START.value
            self.report_result(test_info)
            test_info.code = StatusCodes.BLOCKED.value
            self.report_result(test_info)
            self.__done__()