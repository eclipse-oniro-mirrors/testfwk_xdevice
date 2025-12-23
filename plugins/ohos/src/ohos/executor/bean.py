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

from xdevice import SuiteResult
from xdevice import CaseResult

__all__ = ["StackCaseResult", "StackStateRecorder"]


class StackCaseResult(CaseResult):
    parent_index = ""


class StackStateRecorder:

    def __init__(self):
        self.current_suite_list = []
        self.current_test = None
        self.trace_logs = []
        self.running_test_index = 0

    def suite(self, reset=False):
        if reset or not self.current_suite_list:
            suite = SuiteResult()
            suite.index = uuid.uuid4().hex
            self.current_suite_list.append(suite)
        return self.current_suite_list[len(self.current_suite_list) - 1]

    def test(self, reset=False, test_index=None):
        if reset or not self.current_test:
            self.current_test = CaseResult()
            if test_index:
                self.current_test.index = test_index
            else:
                self.current_test.index = uuid.uuid4().hex
        return self.current_test

    def add_cur_suite(self, suite):
        self.current_suite_list.append(suite)

    def is_suite_empty(self):
        return len(self.current_suite_list) == 0

    def pop_last_suite(self):
        if self.current_suite_list:
            return self.current_suite_list.pop()
        return None

