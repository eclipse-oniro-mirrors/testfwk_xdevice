#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2023 Huawei Device Co., Ltd.
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

import uuid
from dataclasses import dataclass
from _core.report.suite_reporter import ResultCode

__all__ = ["CaseResult", "SuiteResult", "SuitesResult", "StateRecorder"]


@dataclass
class CaseResult:
    index = ""
    code = ResultCode.FAILED.value
    test_name = None
    test_class = None
    stacktrace = ""
    run_time = 0
    is_completed = False
    num_tests = 0
    current = 0
    report = ""
    result_content = ""
    tests_result = []
    starttime = ""

    # hts参数
    normal_screen_urls = ""
    failure_screen_urls = ""

    def is_running(self):
        return self.test_name is not None and not self.is_completed


@dataclass
class SuiteResult:
    index = ""
    code = ResultCode.UNKNOWN.value
    suite_name = None
    test_num = 0
    stacktrace = ""
    run_time = 0
    is_completed = False
    is_started = False
    suite_num = 0
    report = ""


@dataclass
class SuitesResult:
    index = ""
    code = ResultCode.UNKNOWN.value
    suites_name = None
    test_num = 0
    stacktrace = ""
    run_time = 0
    is_completed = False
    product_info = {}


@dataclass
class StateRecorder:
    current_suite = None
    current_suites = None
    current_test = None
    trace_logs = []
    running_test_index = 0

    def is_started(self):
        return self.current_suite is not None

    def suites_is_started(self):
        return self.current_suites is not None

    def suite_is_running(self):
        suite = self.current_suite
        return suite is not None and suite.suite_name is not None and \
            not suite.is_completed

    def suites_is_running(self):
        suites = self.current_suites
        return suites is not None and suites.suites_name is not None and \
            not suites.is_completed

    def test_is_running(self):
        test = self.current_test
        return test is not None and test.is_running()

    def suite(self, reset=False):
        if reset or not self.current_suite:
            self.current_suite = SuiteResult()
            self.current_suite.index = uuid.uuid4().hex
        return self.current_suite

    def get_suites(self, reset=False):
        if reset or not self.current_suites:
            self.current_suites = SuitesResult()
            self.current_suites.index = uuid.uuid4().hex
        return self.current_suites

    def test(self, reset=False, test_index=None):
        if reset or not self.current_test:
            self.current_test = CaseResult()
            if test_index:
                self.current_test.index = test_index
            else:
                self.current_test.index = uuid.uuid4().hex
        return self.current_test
