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
from _core.report.reporter_helper import ReportConstant
from _core.report.reporter_helper import DataHelper


class RepeatHelper:

    def __init__(self, report_path):
        self.data_helper = DataHelper()
        self.report_path = report_path

    def __generate_repeat_xml__(self, summary_data_path):
        from xdevice import Scheduler
        if Scheduler.repeat_index == 0:
            return
        root_tree = self.data_helper.parse_data_report(summary_data_path)
        modules = dict()
        name_set = set()
        for suite in root_tree:
            module_name = suite.attrib.get(ReportConstant.module_name, "")
            if not module_name:
                continue
            name_set.add(module_name)
            name_in_suite = suite.attrib.get(ReportConstant.name, "")
            uuid = "{}#{}".format(module_name, name_in_suite)
            total = int(suite.attrib.get(ReportConstant.tests, 0))
            if total == 0:
                continue
            if uuid not in modules.keys():
                modules[uuid] = suite
                continue
            self._update_suite(modules, suite, uuid)

        root_tree = self._update_root_tree(modules, root_tree)
        root_tree.attrib.update({ReportConstant.modules: str(len(name_set))})
        root_tree.attrib.update({ReportConstant.run_modules: str(len(name_set))})
        file_name = r"{}\repeated.xml".format(self.report_path)
        self.data_helper.generate_report(root_tree, file_name)

    @classmethod
    def _update_root_tree(cls, modules, root_tree):
        for item in root_tree.findall(ReportConstant.test_suite):
            root_tree.remove(item)
        need_update_attributes = \
            [ReportConstant.tests, ReportConstant.ignored,
             ReportConstant.failures, ReportConstant.disabled,
             ReportConstant.errors]
        root_tree.attrib.update({ReportConstant.tests: "0"})
        root_tree.attrib.update({ReportConstant.unavailable: "0"})
        for _, test_suite in modules.items():
            for update_attribute in need_update_attributes:
                value = int(test_suite.attrib.get(update_attribute, 0))
                value = int(root_tree.attrib.get(update_attribute, 0)) + value
                root_tree.attrib.update({update_attribute: str(value)})
            root_tree.append(test_suite)
        return root_tree

    def _update_suite(self, modules, suite, uuid):

        for testcase in suite:
            name = testcase.attrib.get(ReportConstant.name, "")
            class_name = testcase.attrib.get(ReportConstant.class_name, "")
            pattern = ".//{}[@{}='{}'][@{}='{}']".format(
                ReportConstant.test_case, ReportConstant.class_name, class_name,
                ReportConstant.name, name)
            matched_case = modules[uuid].find(pattern)
            if matched_case is None:
                modules[uuid].append(testcase)
                tests = int(
                    modules[uuid].attrib.get(ReportConstant.tests, 0)) + 1
                modules[uuid].attrib[ReportConstant.tests] = str(tests)
                status = self._need_update_status(testcase)
                if status:
                    value = int(modules[uuid].attrib.get(
                        ReportConstant.status, 0)) + 1
                    modules[uuid].attrib[status] = str(value)
                continue
            if testcase.attrib.get(ReportConstant.result,
                                   ReportConstant.false) == ReportConstant.true:
                modules[uuid].remove(matched_case)
                modules[uuid].append(testcase)
                status = self._need_update_status(testcase)
                if status:
                    value = int(modules[uuid].attrib.get(
                        ReportConstant.status, 0)) - 1
                    modules[uuid].attrib[status] = str(value)

    @classmethod
    def _need_update_status(cls, testcase):
        status = testcase.attrib.get(ReportConstant.status, "")
        result = testcase.attrib.get(ReportConstant.result, "")
        if result == ReportConstant.true:
            return ""
        if status == ReportConstant.run:
            return ReportConstant.failures
        elif status == ReportConstant.skip:
            return ReportConstant.ignored
        else:
            return ReportConstant.disabled
