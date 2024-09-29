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
import json
import os
import platform
import time
from ast import literal_eval
from dataclasses import dataclass
from xml.etree import ElementTree

from _core.logger import platform_logger
from _core.report.encrypt import check_pub_key_exist
from _core.report.encrypt import do_rsa_encrypt
from _core.exception import ParamError
from _core.constants import FilePermission

LOG = platform_logger("ReporterHelper")


@dataclass
class ReportConstant:
    # report name constants
    summary_data_report = "summary_report.xml"
    summary_vision_report = "summary_report.html"
    details_vision_report = "details_report.html"
    failures_vision_report = "failures_report.html"
    passes_vision_report = "passes_report.html"
    ignores_vision_report = "ignores_report.html"
    task_info_record = "task_info.record"
    summary_ini = "summary.ini"
    summary_report_hash = "summary_report.hash"
    title_name = "title_name"
    summary_title = "Summary Report"
    details_title = "Details Report"
    failures_title = "Failures Report"
    passes_title = "Passes Report"
    ignores_title = "Ignores Report"
    task_run_log = "task_log.log"
    module_run_log = "module_run.log"

    # exec_info constants
    platform = "platform"
    test_type = "test_type"
    device_name = "device_name"
    host_info = "host_info"
    test_time = "test_time"
    log_path = "log_path"
    log_path_title = "Log Path"
    execute_time = "execute_time"
    device_label = "device_label"

    # summary constants
    product_info = "productinfo"
    product_info_ = "product_info"
    modules = "modules"
    run_modules = "runmodules"
    run_modules_ = "run_modules"
    name = "name"
    time = "time"
    total = "total"
    tests = "tests"
    passed = "passed"
    errors = "errors"
    disabled = "disabled"
    failures = "failures"
    blocked = "blocked"
    ignored = "ignored"
    completed = "completed"
    unavailable = "unavailable"
    not_run = "notrun"
    message = "message"
    report = "report"
    repeat = "repeat"
    round = "round"
    devices = "devices"
    result_content = "result_content"

    # case result constants
    module_name = "modulename"
    module_name_ = "module_name"
    result = "result"
    result_kind = "result_kind"
    status = "status"
    run = "run"
    true = "true"
    false = "false"
    skip = "skip"
    disable = "disable"
    class_name = "classname"
    level = "level"
    empty_name = "-"

    # time constants
    time_stamp = "timestamp"
    start_time = "starttime"
    end_time = "endtime"
    time_format = "%Y-%m-%d %H:%M:%S"

    # xml tag constants
    test_suites = "testsuites"
    test_suite = "testsuite"
    test_case = "testcase"

    # report title constants
    failed = "failed"
    error = "error"
    color_normal = "color-normal"
    color_failed = "color-failed"
    color_blocked = "color-blocked"
    color_ignored = "color-ignored"
    color_unavailable = "color-unavailable"

    # 新报告模板依赖的资源文件
    new_template_sources = [
        {
            "file": "static/css/element-plus@2.3.4_index.css",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.css"
        },
        {
            "file": "static/element-plus@2.3.4_index.full.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.full.js"
        },
        {
            "file": "static/element-plus_icons-vue@2.0.10_index.iife.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus-icons-vue/2.0.10/index.iife.min.js"
        },
        {
            "file": "static/EventEmitter.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/EventEmitter/5.2.8/EventEmitter.js"
        },
        {
            "file": "static/vue@3.2.41_global.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/vue/3.2.41/vue.global.min.js"
        }
    ]


class DataHelper:
    LINE_BREAK = "\n"
    LINE_BREAK_INDENT = "\n  "
    INDENT = "  "
    DATA_REPORT_SUFFIX = ".xml"

    def __init__(self):
        pass

    @staticmethod
    def parse_data_report(data_report):
        if "<" not in data_report and os.path.exists(data_report):
            with open(data_report, 'r', encoding='UTF-8', errors="ignore") as \
                    file_content:
                data_str = file_content.read()
        else:
            data_str = data_report

        for char_index in range(32):
            if char_index in [10, 13]:  # chr(10): LF, chr(13): CR
                continue
            data_str = data_str.replace(chr(char_index), "")
        try:
            return ElementTree.fromstring(data_str)
        except SyntaxError as error:
            LOG.error("%s %s", data_report, error.args)
            return ElementTree.Element("empty")

    @staticmethod
    def set_element_attributes(element, element_attributes):
        for key, value in element_attributes.items():
            element.set(key, str(value))

    @classmethod
    def initial_element(cls, tag, tail, text):
        element = ElementTree.Element(tag)
        element.tail = tail
        element.text = text
        return element

    def initial_suites_element(self):
        return self.initial_element(ReportConstant.test_suites,
                                    self.LINE_BREAK, self.LINE_BREAK_INDENT)

    def initial_suite_element(self):
        return self.initial_element(ReportConstant.test_suite,
                                    self.LINE_BREAK_INDENT,
                                    self.LINE_BREAK_INDENT + self.INDENT)

    def initial_case_element(self):
        return self.initial_element(ReportConstant.test_case,
                                    self.LINE_BREAK_INDENT + self.INDENT, "")

    @classmethod
    def update_suite_result(cls, suite, case):
        update_time = round(float(suite.get(
            ReportConstant.time, 0)) + float(
            case.get(ReportConstant.time, 0)), 3)
        suite.set(ReportConstant.time, str(update_time))
        update_tests = str(int(suite.get(ReportConstant.tests, 0))+1)
        suite.set(ReportConstant.tests, update_tests)
        if case.findall('failure'):
            update_failures = str(int(suite.get(ReportConstant.failures, 0))+1)
            suite.set(ReportConstant.failures, update_failures)

    @classmethod
    def get_summary_result(cls, report_path, file_name, key=None, **kwargs):
        reverse = kwargs.get("reverse", False)
        file_prefix = kwargs.get("file_prefix", None)
        data_reports = cls._get_data_reports(report_path, file_prefix)
        if not data_reports:
            return None
        if key:
            data_reports.sort(key=key, reverse=reverse)
        summary_result = None
        need_update_attributes = [ReportConstant.tests, ReportConstant.errors,
                                  ReportConstant.failures,
                                  ReportConstant.disabled,
                                  ReportConstant.unavailable]
        for data_report in data_reports:
            data_report_element = cls.parse_data_report(data_report)
            if not list(data_report_element):
                continue
            if not summary_result:
                summary_result = data_report_element
                continue
            if not summary_result or not data_report_element:
                continue
            for data_suite in data_report_element:
                for summary_suite in summary_result:
                    if data_suite.get("name", None) == \
                            summary_suite.get("name", None):
                        for data_case in data_suite:
                            for summary_case in summary_suite:
                                if data_case.get("name", None) == \
                                        summary_case.get("name", None):
                                    break
                            else:
                                summary_suite.append(data_case)
                                DataHelper.update_suite_result(summary_result,
                                                               data_case)
                                DataHelper.update_suite_result(summary_suite,
                                                               data_case)
                        break
                else:
                    summary_result.append(data_suite)
                    DataHelper._update_attributes(summary_result, data_suite,
                                                  need_update_attributes)
        if summary_result:
            cls.generate_report(summary_result, file_name)
        return summary_result

    @classmethod
    def _get_data_reports(cls, report_path, file_prefix=None):
        if not os.path.isdir(report_path):
            return []
        data_reports = []
        for root, _, files in os.walk(report_path):
            for file_name in files:
                if not file_name.endswith(cls.DATA_REPORT_SUFFIX):
                    continue
                if file_prefix and not file_name.startswith(file_prefix):
                    continue
                data_reports.append(os.path.join(root, file_name))
        return data_reports

    @classmethod
    def _update_attributes(cls, summary_element, data_element,
                           need_update_attributes):
        for attribute in need_update_attributes:
            updated_value = int(summary_element.get(attribute, 0)) + \
                            int(data_element.get(attribute, 0))
            summary_element.set(attribute, str(updated_value))
        # update time
        updated_time = round(float(summary_element.get(
            ReportConstant.time, 0)) + float(
            data_element.get(ReportConstant.time, 0)), 3)
        summary_element.set(ReportConstant.time, str(updated_time))

    @staticmethod
    def generate_report(element, file_name):
        if check_pub_key_exist():
            plain_text = DataHelper.to_string(element)
            try:
                cipher_text = do_rsa_encrypt(plain_text)
            except ParamError as error:
                LOG.error(error, error_no=error.error_no)
                cipher_text = b""
            if platform.system() == "Windows":
                flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_BINARY
            else:
                flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            file_name_open = os.open(file_name, flags, FilePermission.mode_755)
            with os.fdopen(file_name_open, "wb") as file_handler:
                file_handler.write(cipher_text)
                file_handler.flush()
        else:
            tree = ElementTree.ElementTree(element)
            tree.write(file_name, encoding="UTF-8", xml_declaration=True,
                       short_empty_elements=True)
        LOG.info("Generate data report: %s", file_name)

    @staticmethod
    def to_string(element):
        return str(
            ElementTree.tostring(element, encoding='UTF-8', method='xml'),
            encoding="UTF-8")


@dataclass
class ExecInfo:
    keys = [ReportConstant.platform, ReportConstant.test_type,
            ReportConstant.device_name, ReportConstant.host_info,
            ReportConstant.test_time, ReportConstant.execute_time,
            ReportConstant.device_label]
    test_type = ""
    device_name = ""
    host_info = ""
    test_time = ""
    log_path = ""
    platform = ""
    execute_time = ""
    product_info = dict()
    device_label = ""
    repeat = 1


class Result:

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.blocked = 0
        self.ignored = 0
        self.unavailable = 0

    def get_total(self):
        return self.total

    def get_passed(self):
        return self.passed


class Suite:
    keys = [ReportConstant.module_name_, ReportConstant.name,
            ReportConstant.time, ReportConstant.total, ReportConstant.passed,
            ReportConstant.failed, ReportConstant.blocked, ReportConstant.ignored]
    module_name = ReportConstant.empty_name
    name = ""
    time = ""
    report = ""

    def __init__(self):
        self.message = ""
        self.result = Result()
        self.cases = []  # need initial to create new object

    def get_cases(self):
        return self.cases

    def set_cases(self, element):
        if not element:
            LOG.debug("%s has no testcase",
                      element.get(ReportConstant.name, ""))
            return

        # get case context and add to self.cases
        for child in element:
            case = Case()
            case.module_name = self.module_name
            for key, value in child.items():
                setattr(case, key, value)
            if len(child) > 0:
                if not getattr(case, ReportConstant.result, "") or \
                        getattr(case, ReportConstant.result, "") == ReportConstant.completed:
                    setattr(case, ReportConstant.result, ReportConstant.false)
                message = child[0].get(ReportConstant.message, "")
                if child[0].text and message != child[0].text:
                    message = "%s\n%s" % (message, child[0].text)
                setattr(case, ReportConstant.message, message)
            self.cases.append(case)
        self.cases.sort(key=lambda x: (
            x.is_failed(), x.is_blocked(), x.is_unavailable(), x.is_passed()),
                        reverse=True)


class Case:
    module_name = ReportConstant.empty_name
    name = ReportConstant.empty_name
    classname = ReportConstant.empty_name
    status = ""
    result = ""
    message = ""
    time = ""
    report = ""

    def is_passed(self):
        if self.result == ReportConstant.true and \
                (self.status == ReportConstant.run or self.status == ""):
            return True
        if self.result == "" and self.status == ReportConstant.run and \
                self.message == "":
            return True
        return False

    def is_failed(self):
        return self.result == ReportConstant.false and \
               (self.status == ReportConstant.run or self.status == "")

    def is_blocked(self):
        return self.status in [ReportConstant.blocked, ReportConstant.disable,
                               ReportConstant.error]

    def is_unavailable(self):
        return self.status in [ReportConstant.unavailable]

    def is_ignored(self):
        return self.status in [ReportConstant.skip, ReportConstant.not_run]

    def is_completed(self):
        return self.result == ReportConstant.completed

    def get_result(self):
        if self.is_failed():
            return ReportConstant.failed
        if self.is_blocked():
            return ReportConstant.blocked
        if self.is_unavailable():
            return ReportConstant.unavailable
        if self.is_ignored():
            return ReportConstant.ignored
        return ReportConstant.passed


# ******************** 使用旧报告模板的代码 BEGIN ********************
@dataclass
class ColorType:
    keys = [ReportConstant.failed, ReportConstant.blocked,
            ReportConstant.ignored, ReportConstant.unavailable]
    failed = ReportConstant.color_normal
    blocked = ReportConstant.color_normal
    ignored = ReportConstant.color_normal
    unavailable = ReportConstant.color_normal


class Summary:
    keys = [ReportConstant.modules, ReportConstant.total,
            ReportConstant.passed, ReportConstant.failed,
            ReportConstant.blocked, ReportConstant.unavailable,
            ReportConstant.ignored, ReportConstant.run_modules_]

    def __init__(self):
        self.result = Result()
        self.modules = None
        self.run_modules = 0

    def get_result(self):
        return self.result

    def get_modules(self):
        return self.modules


class VisionHelper:
    PLACE_HOLDER = "&nbsp;"
    MAX_LENGTH = 50

    def __init__(self):
        from xdevice import Variables
        self.summary_element = None
        self.device_logs = None
        self.report_path = ""
        self.template_name = os.path.join(Variables.res_dir, "template",
                                          "report.html")

    def parse_element_data(self, summary_element, report_path, task_info):
        self.summary_element = summary_element
        exec_info = self._set_exec_info(report_path, task_info)
        suites = self._set_suites_info()
        if exec_info.test_type == "SSTS":
            suites.sort(key=lambda x: x.module_name, reverse=True)
        summary = self._set_summary_info()
        return exec_info, summary, suites

    def _set_exec_info(self, report_path, task_info):
        exec_info = ExecInfo()
        exec_info.platform = getattr(task_info, ReportConstant.platform,
                                     "None")
        exec_info.test_type = getattr(task_info, ReportConstant.test_type,
                                      "Test")
        exec_info.device_name = getattr(task_info, ReportConstant.device_name,
                                        "None")
        exec_info.host_info = platform.platform()
        start_time = self.summary_element.get(ReportConstant.start_time, "")
        if not start_time:
            start_time = self.summary_element.get("start_time", "")
        end_time = self.summary_element.get(ReportConstant.end_time, "")
        if not end_time:
            end_time = self.summary_element.get("end_time", "")
        exec_info.test_time = "%s/ %s" % (start_time, end_time)
        start_time = time.mktime(time.strptime(
            start_time, ReportConstant.time_format))
        end_time = time.mktime(time.strptime(
            end_time, ReportConstant.time_format))
        exec_info.execute_time = self.get_execute_time(round(
            end_time - start_time, 3))
        exec_info.device_label = getattr(task_info,
                                         ReportConstant.device_label,
                                         "None")
        exec_info.log_path = os.path.abspath(os.path.join(report_path, "log"))

        try:
            product_info = self.summary_element.get(
                ReportConstant.product_info, "")
            if product_info:
                exec_info.product_info = literal_eval(str(product_info))
        except SyntaxError as error:
            LOG.error("Summary report error: %s", error.args)
        return exec_info

    @classmethod
    def get_execute_time(cls, second_time):
        hour, day = 0, 0
        second, minute = second_time % 60, second_time // 60
        if minute > 0:
            minute, hour = minute % 60, minute // 60
        if hour > 0:
            hour, day = hour % 24, hour // 24
        execute_time = "{}sec".format(str(int(second)))
        if minute > 0:
            execute_time = "{}min {}".format(str(int(minute)), execute_time)
        if hour > 0:
            execute_time = "{}hour {}".format(str(int(hour)), execute_time)
        if day > 0:
            execute_time = "{}day {}".format(str(int(day)), execute_time)
        return execute_time

    def _set_summary_info(self):
        summary = Summary()
        summary.modules = self.summary_element.get(
            ReportConstant.modules, 0)
        summary.run_modules = self.summary_element.get(
            ReportConstant.run_modules, 0)
        summary.result.total = int(self.summary_element.get(
            ReportConstant.tests, 0))
        summary.result.failed = int(
            self.summary_element.get(ReportConstant.failures, 0))
        summary.result.blocked = int(
            self.summary_element.get(ReportConstant.errors, 0)) + \
                                 int(self.summary_element.get(ReportConstant.disabled, 0))
        summary.result.ignored = int(
            self.summary_element.get(ReportConstant.ignored, 0))
        summary.result.unavailable = int(
            self.summary_element.get(ReportConstant.unavailable, 0))
        summary.result.passed = summary.result.total - summary.result.failed \
                                - summary.result.blocked - summary.result.ignored
        return summary

    def _set_suites_info(self):
        suites = []
        for child in self.summary_element:
            suite = Suite()
            suite.module_name = child.get(ReportConstant.module_name,
                                          ReportConstant.empty_name)
            suite.name = child.get(ReportConstant.name, "")
            suite.message = child.get(ReportConstant.message, "")
            suite.report = child.get(ReportConstant.report, "")
            suite.result.total = int(child.get(ReportConstant.tests)) if \
                child.get(ReportConstant.tests) else 0
            suite.result.failed = int(child.get(ReportConstant.failures)) if \
                child.get(ReportConstant.failures) else 0
            suite.result.unavailable = int(child.get(
                ReportConstant.unavailable)) if child.get(
                ReportConstant.unavailable) else 0
            errors = int(child.get(ReportConstant.errors)) if child.get(
                ReportConstant.errors) else 0
            disabled = int(child.get(ReportConstant.disabled)) if child.get(
                ReportConstant.disabled) else 0
            suite.result.ignored = int(child.get(ReportConstant.ignored)) if \
                child.get(ReportConstant.ignored) else 0
            suite.result.blocked = errors + disabled
            suite.result.passed = suite.result.total - suite.result.failed - \
                                  suite.result.blocked - suite.result.ignored
            suite.time = child.get(ReportConstant.time, "")
            suite.set_cases(child)
            suites.append(suite)
        suites.sort(key=lambda x: (x.result.failed, x.result.blocked,
                                   x.result.unavailable), reverse=True)
        return suites

    def render_data(self, title_name, parsed_data,
                    render_target=ReportConstant.summary_vision_report, devices=None):
        exec_info, summary, suites = parsed_data
        if not os.path.exists(self.template_name):
            LOG.error("Template file not exists, {}".format(self.template_name))
            return ""
        with open(self.template_name) as file:
            file_context = file.read()
            file_context = self._render_key("", ReportConstant.title_name,
                                            title_name, file_context)
            file_context = self._render_exec_info(file_context, exec_info)
            file_context = self._render_summary(file_context, summary)
            if devices is not None and len(devices) != 0:
                file_context = self._render_product_info(file_context, devices)
                file_context = self._render_devices(file_context, devices)
            if render_target == ReportConstant.summary_vision_report:
                file_context = self._render_suites(file_context, suites)
            elif render_target == ReportConstant.details_vision_report:
                file_context = self._render_cases(file_context, suites)
            elif render_target == ReportConstant.failures_vision_report:
                file_context = self._render_failure_cases(file_context, suites)
            elif render_target == ReportConstant.passes_vision_report:
                file_context = self._render_pass_cases(file_context, suites)
            elif render_target == ReportConstant.ignores_vision_report:
                file_context = self._render_ignore_cases(file_context, suites)
            else:
                LOG.error("Unsupported vision report type: {}".format(render_target))
            return file_context

    @classmethod
    def _render_devices(cls, file_context, devices):
        """render devices"""
        table_body_content = ""
        keys = ["index", "sn", "model", "type", "platform", "version", "others"]
        for index, device in enumerate(devices, 1):
            tds = []
            for key in keys:
                value = device.get(key, "")
                if key == "index":
                    td_content = index
                elif key == "others":
                    if len(value) == 0:
                        td_content = f"""<div style="display: flex;">
                            <div class="ellipsis">{value}</div>
                        </div>"""
                    else:
                        td_content = f"""<div style="display: flex;">
                            <div class="ellipsis">{value}</div>
                            <div class="operate" onclick="showDialog('dialog{index}')"></div>
                        </div>"""
                else:
                    td_content = value
                tds.append("<td class='normal device-{}'>{}</td>".format(key, td_content))
            table_body_content += "<tr>\n" + "\n  ".join(tds) + "\n</tr>"

        render_result = """<table class="devices">
  <thead>
    <tr>
      <th class="normal device-index">#</th>
      <th class="normal device-sn">SN</th>
      <th class="normal device-model">Model</th>
      <th class="normal device-type">Type</th>
      <th class="normal device-platform">Platform</th>
      <th class="normal device-version">Version</th>
      <th class="normal device-others">Others</th>
    </tr>
  </thead>
  <tbody>
    {}
  </tbody>
</table>""".format(table_body_content)
        replace_str = "<!--{devices.context}-->"
        return file_context.replace(replace_str, render_result)

    @classmethod
    def _render_key(cls, prefix, key, new_str, update_context):
        old_str = "<!--{%s%s}-->" % (prefix, key)
        return update_context.replace(old_str, new_str)

    def _render_exec_info(self, file_context, exec_info):
        prefix = "exec_info."
        for key in ExecInfo.keys:
            value = self._get_hidden_style_value(getattr(
                exec_info, key, "None"))
            file_context = self._render_key(prefix, key, value, file_context)
        replace_str = "<!--{exec_info.task_log}-->"
        file_context = file_context.replace(replace_str, self._get_task_log())
        return file_context

    @staticmethod
    def _render_product_info(file_context, devices):
        """Construct product info context and render it to file context"""
        render_result = ""
        for index, device in enumerate(devices, 1):
            others = device.get("others", "")
            if len(others) == 0:
                continue
            tmp, count = "", 0
            tbody_content = ""
            for k, v in others.items():
                tmp += f'<td class="key">{k}:</td>\n<td class="value">{v}</td>\n'
                count += 1
                if count == 2:
                    tbody_content += "<tr>" + tmp + "<tr>\n"
                    tmp, count = "", 0
            if tmp != "":
                tbody_content += "<tr>" + tmp + "<tr>\n"
            render_dialog = f"""<div id="dialog{index}" , class="el-dialog">
                <div style="margin: 15% auto; width: 60%;">
                    <div class="el-dialog__header">
                        <button class="el-dialog__close" onclick="hideDialog()">关闭</button>
                    </div>
                    <div class="el-dialog__body">
                        <table class="el-dialog__table">
                            <tbody>
                                {tbody_content}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            """
            render_result += render_dialog
        replace_str = "<!--{devices.dialogs}-->"
        return file_context.replace(replace_str, render_result)

    def _get_exec_info_td(self, key, value, row_start):
        if not value:
            value = self.PLACE_HOLDER
        if key == ReportConstant.log_path_title and row_start:
            exec_info_td = \
                "  <td class='normal first'>%s:</td>\n" \
                "  <td class='normal second' colspan='3'>%s</td>\n" % \
                (key, value)
            return exec_info_td
        value = self._get_hidden_style_value(value)
        if row_start:
            exec_info_td = "  <td class='normal first'>%s:</td>\n" \
                           "  <td class='normal second'>%s</td>\n" % \
                           (key, value)
        else:
            exec_info_td = "  <td class='normal third'>%s:</td>\n" \
                           "  <td class='normal fourth'>%s</td>\n" % \
                           (key, value)
        return exec_info_td

    def _get_hidden_style_value(self, value):
        if len(value) <= self.MAX_LENGTH:
            return value
        return "<div class='hidden' title='%s'>%s</div>" % (value, value)

    def _render_summary(self, file_context, summary):
        file_context = self._render_data_object(file_context, summary,
                                                "summary.")

        # render color type
        color_type = ColorType()
        if summary.result.failed != 0:
            color_type.failed = ReportConstant.color_failed
        if summary.result.blocked != 0:
            color_type.blocked = ReportConstant.color_blocked
        if summary.result.ignored != 0:
            color_type.ignored = ReportConstant.color_ignored
        if summary.result.unavailable != 0:
            color_type.unavailable = ReportConstant.color_unavailable
        return self._render_data_object(file_context, color_type,
                                        "color_type.")

    def _render_data_object(self, file_context, data_object, prefix,
                            default=None):
        """Construct data object context and render it to file context"""
        if default is None:
            default = self.PLACE_HOLDER
        update_context = file_context
        for key in getattr(data_object, "keys", []):
            if hasattr(Result(), key) and hasattr(
                    data_object, ReportConstant.result):
                result = getattr(data_object, ReportConstant.result, Result())
                new_str = str(getattr(result, key, default))
            else:
                new_str = str(getattr(data_object, key, default))
            update_context = self._render_key(prefix, key, new_str,
                                              update_context)
        return update_context

    def _render_suites(self, file_context, suites):
        """Construct suites context and render it to file context
        suite record sample:
            <table class="suites">
            <tr>
                <td class='tasklog'>TaskLog:</td>
                <td class='normal' colspan='8' style="border-bottom: 1px #E8F0FD solid;">
                    <a href='log/task_log.log'>task_log.log</a>
                </td>
            </tr>
            <tr>
                <th class="normal module">Module</th>
                <th class="normal testsuite">Testsuite</th>
                <th class="normal time">Time(sec)</th>
                <th class="normal total">Total Tests</th>
                <th class="normal passed">Passed</th>
                <th class="normal failed">Failed</th>
                <th class="normal blocked">Blocked</th>
                <th class="normal ignored">Ignored</th>
                <th class="normal operate">Operate</th>
            </tr>
            <tr [class="background-color"]>
                <td class="normal module">{suite.module_name}</td>
                <td class='normal testsuite'>
                  <a href='{suite.report}'>{suite.name}</a> or {suite.name}
                </td>
                <td class="normal time">{suite.time}</td>
                <td class="normal total">{suite.result.total}</td>
                <td class="normal passed">{suite.result.passed}</td>
                <td class="normal failed">{suite.result.failed}</td>
                <td class="normal blocked">{suite.result.blocked}</td>
                <td class="normal ignored">{suite.result.ignored}</td>
                <td class="normal operate">
                  <a href="details_report.html#{suite.name}" or
                          "failures_report.html#{suite.name}">
                  <div class="operate"></div></a>
                </td>
            </tr>
            ...
            </table>
        """
        replace_str = "<!--{suites.context}-->"

        suites_context = "<table class='suites'>\n"
        suites_context += self._get_suites_title()
        for index, suite in enumerate(suites):
            # construct suite context
            suite_name = getattr(suite, "name", self.PLACE_HOLDER)
            suite_context = "<tr>\n  " if index % 2 == 0 else \
                "<tr class='background-color'>\n  "
            for key in Suite.keys:
                if hasattr(Result(), key):
                    result = getattr(suite, ReportConstant.result, Result())
                    text = getattr(result, key, self.PLACE_HOLDER)
                else:
                    text = getattr(suite, key, self.PLACE_HOLDER)
                if key == ReportConstant.name:
                    report = getattr(suite, ReportConstant.report, self.PLACE_HOLDER)
                    temp = "<td class='normal testsuite'>{}</td>\n  ".format(
                        "<a href='{}'>{}</a>".format(report, text) if report else text)
                else:
                    temp = self._add_suite_td_context(key, text)
                suite_context = "{}{}".format(suite_context, temp)
            if suite.result.total == 0:
                href = "%s#%s" % (
                    ReportConstant.failures_vision_report, suite_name)
            else:
                href = "%s#%s" % (
                    ReportConstant.details_vision_report, suite_name)
            suite_context = "{}{}".format(
                suite_context,
                "<td class='normal operate'><a href='%s'><div class='operate'>"
                "</div></a></td>\n</tr>\n" % href)
            # add suite context to suites context
            suites_context = "{}{}".format(suites_context, suite_context)

        suites_context = "%s</table>\n" % suites_context
        return file_context.replace(replace_str, suites_context)

    def _get_task_log(self):
        logs = [f for f in os.listdir(os.path.join(self.report_path, 'log')) if f.startswith('task_log.log')]
        link = ["<a href='log/{task_log}'>{task_log}</a>".format(task_log=file_name) for file_name in logs]
        return ' '.join(link)

    def _get_testsuite_device_log(self, module_name, suite_name):
        log_index, log_name = 0, 'device_log'
        hilog_index, hilog_name = 0, 'device_hilog'
        logs = []
        for r in self._get_device_logs():
            if (r.startswith(log_name) or r.startswith(hilog_name)) \
                    and ((module_name and module_name in r) or suite_name in r):
                logs.append(r)
        if not logs:
            return ''
        link = []
        for name in sorted(logs):
            display_name = ''
            if name.startswith(log_name):
                display_name = log_name
                if log_index != 0:
                    display_name = log_name + str(log_index)
                log_index += 1
            if name.startswith(hilog_name):
                display_name = hilog_name
                if hilog_index != 0:
                    display_name = hilog_name + str(hilog_index)
                hilog_index += 1
            link.append("<a href='{}'>{}</a>".format(os.path.join('log', name), display_name))
        ele = "<tr>\n" \
              "  <td class='devicelog' style='border-bottom: 1px #E8F0FD solid;'>DeviceLog:</td>\n" \
              "  <td class='normal' colspan='6' style='border-bottom: 1px #E8F0FD solid;'>\n" \
              "    {}\n" \
              "  </td>\n" \
              "</tr>".format(' | '.join(link))
        return ele

    def _get_testcase_device_log(self, case_name):
        log_name, hilog_name = 'device_log', 'device_hilog'
        logs = [r for r in self._get_device_logs()
                if case_name in r and (log_name in r or hilog_name in r) and r.endswith('.log')]
        if not logs:
            return '-'
        link = []
        for name in sorted(logs):
            display_name = ''
            if log_name in name:
                display_name = log_name
            if hilog_name in name:
                display_name = hilog_name
            link.append("<a href='{}'>{}</a>".format(os.path.join('log', name), display_name))
        return '<br>'.join(link)

    def _get_device_logs(self):
        if self.device_logs is not None:
            return self.device_logs
        result = []
        pth = os.path.join(self.report_path, 'log')
        for top, _, nondirs in os.walk(pth):
            for filename in nondirs:
                if filename.startswith('device_log') or filename.startswith('device_hilog'):
                    result.append(os.path.join(top, filename).replace(pth, '')[1:])
        self.device_logs = result
        return result

    @classmethod
    def _get_suites_title(cls):
        suites_title = "<tr>\n" \
                       "  <th class='normal module'>Module</th>\n" \
                       "  <th class='normal testsuite'>Testsuite</th>\n" \
                       "  <th class='normal time'>Time(sec)</th>\n" \
                       "  <th class='normal total'>Tests</th>\n" \
                       "  <th class='normal passed'>Passed</th>\n" \
                       "  <th class='normal failed'>Failed</th>\n" \
                       "  <th class='normal blocked'>Blocked</th>\n" \
                       "  <th class='normal ignored'>Ignored</th>\n" \
                       "  <th class='normal operate'>Operate</th>\n" \
                       "</tr>\n"
        return suites_title

    @staticmethod
    def _add_suite_td_context(style, text):
        if style == ReportConstant.name:
            style = "test-suite"
        td_style_class = "normal %s" % style
        return "<td class='%s'>%s</td>\n  " % (td_style_class, str(text))

    def _render_cases(self, file_context, suites):
        """Construct cases context and render it to file context
        case table sample:
            <table class="test-suite">
            <tr>
                <th class="title" colspan="4" id="{suite.name}">
                    <span class="title">{suite.name}&nbsp;&nbsp;</span>
                    <a href="summary_report.html#summary">
                    <span class="return"></span></a>
                </th>
            </tr>
            <tr>
                <td class='devicelog' style='border-bottom: 1px #E8F0FD solid;'>DeviceLog:</td>
                <td class='normal' colspan='5' style='border-bottom: 1px #E8F0FD solid;'>
                    <a href='log/device_log_xx.log'>device_log</a> | <a href='log/device_hilog_xx.log'>device_hilog</a>
                </td>
            </tr>
            <tr>
                <th class="normal module">Module</th>
                <th class="normal testsuite">Testsuite</th>
                <th class="normal test">Testcase</th>
                <th class="normal time">Time(sec)</th>
                <th class="normal status">
                  <div class="circle-normal circle-white"></div>
                </th>
                <th class="normal result">Result</th>
                <th class='normal logs'>Logs</th>
            </tr>
            <tr [class="background-color"]>
                <td class="normal module">{case.module_name}</td>
                <td class="normal testsuite">{case.classname}</td>
                <td class="normal test">
                  <a href='{case.report}'>{case.name}</a> or {case.name}
                </td>
                <td class="normal time">{case.time}</td>
                <td class="normal status"><div class="circle-normal
                    circle-{case.result/status}"></div></td>
                <td class="normal result">
                    [<a href="failures_report.html#{suite.name}.{case.name}">]
                    {case.result/status}[</a>]
                </td>
                <td class='normal logs'>-</td>
            </tr>
            ...
            </table>
            ...
        """
        replace_str = "<!--{cases.context}-->"
        cases_context = ""
        for suite in suites:
            # construct case context
            module_name = suite.cases[0].module_name if suite.cases else ""
            suite_name = getattr(suite, "name", self.PLACE_HOLDER)
            case_context = "<table class='test-suite'>\n"
            case_context += self._get_case_title(module_name, suite_name)
            for index, case in enumerate(suite.cases):
                case_context += self._get_case_td_context(index, case, suite_name)
            case_context += "\n</table>\n"
            cases_context += case_context
        return file_context.replace(replace_str, cases_context)

    def _get_case_td_context(self, index, case, suite_name):
        result = case.get_result()
        rendered_result = result
        if result != ReportConstant.passed and \
                result != ReportConstant.ignored:
            rendered_result = "<a href='%s#%s.%s'>%s</a>" % \
                              (ReportConstant.failures_vision_report,
                               suite_name, case.name, result)
        if result == ReportConstant.passed:
            rendered_result = "<a href='{}#{}.{}'>{}</a>".format(
                ReportConstant.passes_vision_report, suite_name, case.name, result)

        if result == ReportConstant.ignored:
            rendered_result = "<a href='{}#{}.{}'>{}</a>".format(
                ReportConstant.ignores_vision_report, suite_name, case.name, result)

        report = case.report
        test_name = "<a href='{}'>{}</a>".format(report, case.name) if report else case.name
        case_td_context = "<tr>\n" if index % 2 == 0 else \
            "<tr class='background-color'>\n"
        case_td_context = "{}{}".format(
            case_td_context,
            "  <td class='normal module'>%s</td>\n"
            "  <td class='normal testsuite'>%s</td>\n"
            "  <td class='normal test'>%s</td>\n"
            "  <td class='normal time'>%s</td>\n"
            "  <td class='normal status'>\n"
            "    <div class='circle-normal circle-%s'></div>\n"
            "  </td>\n"
            "  <td class='normal result'>%s</td>\n"
            "  <td class='normal logs'>%s</td>\n"
            "</tr>\n" % (case.module_name, case.classname, test_name,
                         case.time, result, rendered_result, self._get_testcase_device_log(case.name)))
        return case_td_context

    def _get_case_title(self, module_name, suite_name):
        case_title = \
            "<tr>\n" \
            "  <th class='title' colspan='4' id='%s'>\n" \
            "    <span class='title'>%s&nbsp;&nbsp;</span>\n" \
            "    <a href='%s#summary'>\n" \
            "    <span class='return'></span></a>\n" \
            "  </th>\n" \
            "</tr>\n" \
            "%s\n" \
            "<tr>\n" \
            "  <th class='normal module'>Module</th>\n" \
            "  <th class='normal testsuite'>Testsuite</th>\n" \
            "  <th class='normal test'>Testcase</th>\n" \
            "  <th class='normal time'>Time(sec)</th>\n" \
            "  <th class='normal status'><div class='circle-normal " \
            "circle-white'></div></th>\n" \
            "  <th class='normal result'>Result</th>\n" \
            "  <th class='normal logs'>Logs</th>\n" \
            "</tr>\n" % (suite_name, suite_name,
                         ReportConstant.summary_vision_report,
                         self._get_testsuite_device_log(module_name, suite_name))
        return case_title

    def _render_failure_cases(self, file_context, suites):
        """Construct failure cases context and render it to file context
        failure case table sample:
            <table class="failure-test">
            <tr>
                <th class="title" colspan="4" id="{suite.name}">
                    <span class="title">{suite.name}&nbsp;&nbsp;</span>
                    <a href="details_report.html#{suite.name}" or
                            "summary_report.html#summary">
                    <span class="return"></span></a>
                </th>
            </tr>
            <tr>
                <th class="normal test">Test</th>
                <th class="normal status"><div class="circle-normal
                circle-white"></div></th>
                <th class="normal result">Result</th>
                <th class="normal details">Details</th>
            </tr>
            <tr [class="background-color"]>
                <td class="normal test" id="{suite.name}">
                    {suite.module_name}#{suite.name}</td>
                or
                <td class="normal test" id="{suite.name}.{case.name}">
                    {case.module_name}#{case.classname}#{case.name}</td>
                <td class="normal status"><div class="circle-normal
                    circle-{case.result/status}"></div></td>
                <td class="normal result">{case.result/status}</td>
                <td class="normal details">{case.message}</td>
            </tr>
            ...
            </table>
            ...
        """
        replace_str = "<!--{failures.context}-->"
        failure_cases_context = ""
        for suite in suites:
            if suite.result.total == (
                    suite.result.passed + suite.result.ignored) and \
                    suite.result.unavailable == 0:
                continue

            # construct failure cases context for failure suite
            suite_name = getattr(suite, "name", self.PLACE_HOLDER)
            case_context = "<table class='failure-test'>\n"
            case_context = \
                "{}{}".format(case_context, self._get_failure_case_title(
                    suite_name, suite.result.total))
            if suite.result.total == 0:
                case_context = "{}{}".format(
                    case_context, self._get_failure_case_td_context(
                        0, suite, suite_name, ReportConstant.unavailable))
            else:
                skipped_num = 0
                for index, case in enumerate(suite.cases):
                    result = case.get_result()
                    if result == ReportConstant.passed or \
                            result == ReportConstant.ignored:
                        skipped_num += 1
                        continue
                    case_context = "{}{}".format(
                        case_context, self._get_failure_case_td_context(
                            index - skipped_num, case, suite_name, result))

            case_context = "%s</table>\n" % case_context

            # add case context to cases context
            failure_cases_context = \
                "{}{}".format(failure_cases_context, case_context)
        return file_context.replace(replace_str, failure_cases_context)

    def _render_pass_cases(self, file_context, suites):
        """construct pass cases context and render it to file context
        failure case table sample:
            <table class="pass-test">
            <tr>
                <th class="title" colspan="4" id="{suite.name}">
                    <span class="title">{suite.name}&nbsp;&nbsp;</span>
                    <a href="details_report.html#{suite.name}" or
                            "summary_report.html#summary">
                    <span class="return"></span></a>
                </th>
            </tr>
            <tr>
                <th class="normal test">Test</th>
                <th class="normal status"><div class="circle-normal
                circle-white"></div></th>
                <th class="normal result">Result</th>
                <th class="normal details">Details</th>
            </tr>
            <tr [class="background-color"]>
                <td class="normal test" id="{suite.name}">
                    {suite.module_name}#{suite.name}</td>
                or
                <td class="normal test" id="{suite.name}.{case.name}">
                    {case.module_name}#{case.classname}#{case.name}</td>
                <td class="normal status"><div class="circle-normal
                    circle-{case.result/status}"></div></td>
                <td class="normal result">{case.result/status}</td>
                <td class="normal details">{case.message}</td>
            </tr>
            ...
            </table>
            ...
        """
        file_context = file_context.replace("failure-test", "pass-test")
        replace_str = "<!--{failures.context}-->"
        pass_cases_context = ""
        for suite in suites:
            if (suite.result.total > 0 and suite.result.total == (
                    suite.result.failed + suite.result.ignored + suite.result.blocked)) or \
                    suite.result.unavailable != 0:
                continue

            # construct pass cases context for pass suite
            suite_name = getattr(suite, "name", self.PLACE_HOLDER)
            case_context = "<table class='pass-test'>\n"
            case_context = \
                "{}{}".format(case_context, self._get_failure_case_title(
                    suite_name, suite.result.total))
            skipped_num = 0
            for index, case in enumerate(suite.cases):
                result = case.get_result()
                if result == ReportConstant.failed or \
                        result == ReportConstant.ignored or result == ReportConstant.blocked:
                    skipped_num += 1
                    continue
                case_context = "{}{}".format(
                    case_context, self._get_pass_case_td_context(
                        index - skipped_num, case, suite_name, result))

            case_context = "{}</table>\n".format(case_context)

            # add case context to cases context
            pass_cases_context = \
                "{}{}".format(pass_cases_context, case_context)
        return file_context.replace(replace_str, pass_cases_context)

    def _render_ignore_cases(self, file_context, suites):
        file_context = file_context.replace("failure-test", "ignore-test")
        replace_str = "<!--{failures.context}-->"
        ignore_cases_context = ""
        for suite in suites:
            if (suite.result.total > 0 and suite.result.total == (
                    suite.result.failed + suite.result.ignored + suite.result.blocked)) or \
                    suite.result.unavailable != 0:
                continue

            # construct pass cases context for pass suite
            suite_name = getattr(suite, "name", self.PLACE_HOLDER)
            case_context = "<table class='ignore-test'>\n"
            case_context = \
                "{}{}".format(case_context, self._get_failure_case_title(
                    suite_name, suite.result.total))
            skipped_num = 0
            for index, case in enumerate(suite.cases):
                result = case.get_result()
                if result == ReportConstant.failed or \
                        result == ReportConstant.passed or result == ReportConstant.blocked:
                    skipped_num += 1
                    continue
                case_context = "{}{}".format(
                    case_context, self._get_ignore_case_td_context(
                        index - skipped_num, case, suite_name, result))

            case_context = "{}</table>\n".format(case_context)

            # add case context to cases context
            ignore_cases_context = "{}{}".format(ignore_cases_context, case_context)
        return file_context.replace(replace_str, ignore_cases_context)

    @classmethod
    def _get_pass_case_td_context(cls, index, case, suite_name, result):
        pass_case_td_context = "<tr>\n" if index % 2 == 0 else \
            "<tr class='background-color'>\n"
        test_context = "{}#{}#{}".format(case.module_name, case.classname, case.name)
        href_id = "{}.{}".format(suite_name, case.name)

        detail_data = "-"
        if hasattr(case, "normal_screen_urls"):
            detail_data += "Screenshot: {}<br>".format(
                cls._get_screenshot_url_context(case.normal_screen_urls))

        pass_case_td_context += "  <td class='normal test' id='{}'>{}</td>\n" \
                                "  <td class='normal status'>\n" \
                                "    <div class='circle-normal circle-{}'></div>\n" \
                                "  </td>\n" \
                                "  <td class='normal result'>{}</td>\n" \
                                "  <td class='normal details'>\n" \
                                "   {}\n" \
                                "  </td>\n" \
                                "</tr>\n".format(href_id, test_context, result, result, detail_data)
        return pass_case_td_context

    @classmethod
    def _get_ignore_case_td_context(cls, index, case, suite_name, result):
        ignore_case_td_context = "<tr>\n" if index % 2 == 0 else \
            "<tr class='background-color'>\n"
        test_context = "{}#{}#{}".format(case.module_name, case.classname, case.name)
        href_id = "{}.{}".format(suite_name, case.name)

        result_info = {}
        if hasattr(case, "result_info") and case.result_info:
            result_info = json.loads(case.result_info)
        detail_data = ""
        actual_info = result_info.get("actual", "")
        if actual_info:
            detail_data += "actual:&nbsp;{}<br>".format(actual_info)
        except_info = result_info.get("except", "")
        if except_info:
            detail_data += "except:&nbsp;{}<br>".format(except_info)
        filter_info = result_info.get("filter", "")
        if filter_info:
            detail_data += "filter:&nbsp;{}<br>".format(filter_info)
        if not detail_data:
            detail_data = "-"

        ignore_case_td_context += "  <td class='normal test' id='{}'>{}</td>\n" \
                                  "  <td class='normal status'>\n" \
                                  "    <div class='circle-normal circle-{}'></div></td>\n" \
                                  "  <td class='normal result'>{}</td>\n" \
                                  "  <td class='normal details'>\n" \
                                  "    {}\n" \
                                  "  </td>\n" \
                                  "</tr>\n".format(
            href_id, test_context, result, result, detail_data)
        return ignore_case_td_context

    @classmethod
    def _get_screenshot_url_context(cls, url):
        context = ""
        if not url:
            return ""
        paths = cls._find_png_file_path(url)
        for path in paths:
            context += "<br><a href='{0}'>{1}</a>".format(path, path)
        return context

    @classmethod
    def _find_png_file_path(cls, url):
        if not url:
            return []
        last_index = url.rfind("\\")
        if last_index < 0:
            return []
        start_str = url[0:last_index]
        end_str = url[last_index + 1:len(url)]
        if not os.path.exists(start_str):
            return []
        paths = []
        for file in os.listdir(start_str):
            if end_str in file:
                whole_path = os.path.join(start_str, file)
                l_index = whole_path.rfind("screenshot")
                relative_path = whole_path[l_index:]
                paths.append(relative_path)
        return paths

    @classmethod
    def _get_failure_case_td_context(cls, index, case, suite_name, result):
        failure_case_td_context = "<tr>\n" if index % 2 == 0 else \
            "<tr class='background-color'>\n"
        if result == ReportConstant.unavailable:
            test_context = "{}#{}".format(case.module_name, case.name)
            href_id = suite_name
        else:
            test_context = "{}#{}#{}".format(case.module_name, case.classname, case.name)
            href_id = "{}.{}".format(suite_name, case.name)
        details_context = case.message

        detail_data = ""
        if hasattr(case, "normal_screen_urls"):
            detail_data += "Screenshot: {}<br>".format(
                cls._get_screenshot_url_context(case.normal_screen_urls))
        if hasattr(case, "failure_screen_urls"):
            detail_data += "Screenshot_On_Failure: {}<br>".format(
                cls._get_screenshot_url_context(case.failure_screen_urls))

        if details_context:
            detail_data += str(details_context).replace("<", "&lt;"). \
                replace(">", "&gt;").replace("\\r\\n", "<br>"). \
                replace("\\n", "<br>").replace("\n", "<br>"). \
                replace(" ", "&nbsp;")

        failure_case_td_context += "  <td class='normal test' id='{}'>{}</td>\n" \
                                   "  <td class='normal status'>" \
                                   "    <div class='circle-normal circle-{}'></div>" \
                                   "  </td>\n" \
                                   "  <td class='normal result'>{}</td>\n" \
                                   "  <td class='normal details'>\n" \
                                   "    {}" \
                                   "  </td>\n" \
                                   "</tr>\n".format(href_id, test_context, result, result, detail_data)
        return failure_case_td_context

    @classmethod
    def _get_failure_case_title(cls, suite_name, total):
        if total == 0:
            href = "%s#summary" % ReportConstant.summary_vision_report
        else:
            href = "%s#%s" % (ReportConstant.details_vision_report, suite_name)
        failure_case_title = \
            "<tr>\n" \
            "  <th class='title' colspan='4' id='%s'>\n" \
            "    <span class='title'>%s&nbsp;&nbsp;</span>\n" \
            "    <a href='%s'>\n" \
            "    <span class='return'></span></a>\n" \
            "  </th>\n" \
            "</tr>\n" \
            "<tr>\n" \
            "  <th class='normal test'>Test</th>\n" \
            "  <th class='normal status'><div class='circle-normal " \
            "circle-white'></div></th>\n" \
            "  <th class='normal result'>Result</th>\n" \
            "  <th class='normal details'>Details</th>\n" \
            "</tr>\n" % (suite_name, suite_name, href)
        return failure_case_title

    @staticmethod
    def generate_report(summary_vision_path, report_context):
        if platform.system() == "Windows":
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_BINARY
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        vision_file_open = os.open(summary_vision_path, flags,
                                   FilePermission.mode_755)
        vision_file = os.fdopen(vision_file_open, "wb")
        if check_pub_key_exist():
            try:
                cipher_text = do_rsa_encrypt(report_context)
            except ParamError as error:
                LOG.error(error, error_no=error.error_no)
                cipher_text = b""
            vision_file.write(cipher_text)
        else:
            vision_file.write(bytes(report_context, "utf-8", "ignore"))
        vision_file.flush()
        vision_file.close()
        LOG.info("Generate vision report: file:///%s", summary_vision_path.replace("\\", "/"))
# ******************** 使用旧报告模板的代码 END ********************
