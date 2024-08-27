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

import os
import time
from xml.etree import ElementTree

from _core.constants import CaseResult
from _core.constants import HostDrivenTestType
from _core.constants import ModeType
from _core.constants import DeviceTestType
from _core.context.center import Context
from _core.context.handler import get_case_result
from _core.logger import platform_logger
from _core.report.reporter_helper import DataHelper
from _core.report.reporter_helper import ReportConstant
from _core.utils import check_mode
from _core.utils import get_filename_extension

LOG = platform_logger("Upload")

MAX_VISIBLE_LENGTH = 256

__all__ = ["Uploader"]


class Uploader:

    @classmethod
    def is_enable(cls):
        if Context.session().upload_address:
            return True
        return False

    @classmethod
    def get_session(cls):
        return Context.session()

    @classmethod
    def upload_task_result(cls, task, error_message=""):
        if not Uploader.is_enable():
            return
        task_name = cls.get_session().task_name
        if not task_name:
            LOG.info("No need upload summary report")
            return

        summary_data_report = os.path.join(task.config.report_path,
                                           ReportConstant.summary_data_report)
        if not os.path.exists(summary_data_report):
            Uploader.upload_unavailable_result(str(error_message) or "summary report not exists",
                                               task.config.report_path)
            return

        task_element = ElementTree.parse(summary_data_report).getroot()
        start_time, end_time = Uploader._get_time(task_element)
        task_result = Uploader._get_task_result(task_element)
        error_msg = ""
        for child in task_element:
            if child.get(ReportConstant.message, ""):
                error_msg = "{}{}".format(
                    error_msg, "%s;" % child.get(ReportConstant.message))
        if error_msg:
            error_msg = error_msg[:-1]
        report = Uploader._get_report_path(
            task.config.report_path, ReportConstant.summary_vision_report)
        Uploader.upload_case_result(
            (task_name, task_result, error_msg, start_time, end_time, report))

    @classmethod
    def upload_module_result(cls, exec_message):
        proxy = cls.get_session().proxy
        if proxy is None:
            return
        result_file = exec_message.get_result()
        request = exec_message.get_request()
        test_name = request.root.source.test_name
        if not result_file or not os.path.exists(result_file):
            LOG.error("%s result not exists", test_name, error_no="00200")
            return

        if check_mode(ModeType.controller):
            cls.get_session().task_name = test_name

        test_type = request.root.source.test_type
        LOG.info("Need upload result: %s, test type: %s" %
                 (result_file, test_type))
        upload_params = cls._get_upload_params(result_file, request)
        if not upload_params:
            LOG.error("%s no test case result to upload" % result_file,
                      error_no="00201")
            return
        LOG.info("Need upload %s case" % len(upload_params))
        upload_suite = []
        for upload_param in upload_params:
            case_id, result, error, start, end, report_path, result_content = upload_param
            case = {"caseid": case_id, "result": result, "error": error,
                    "start": start, "end": end, "report": report_path,
                    "result_content": result_content}
            LOG.info("Case info: %s", case)
            upload_suite.append(case)

        if check_mode(ModeType.controller):
            case = {"caseid": test_name, "result": "Finish", "error": "",
                    "start": "", "end": "",
                    "report": ""}
            upload_suite.append(case)
        proxy.upload_batch(upload_suite)

        if check_mode(ModeType.controller):
            cls.get_session().task_name = ""

    @classmethod
    def upload_unavailable_result(cls, error_msg, case_id="", report_path=""):
        current_time = int(time.time() * 1000)
        if case_id == "":
            case_id = cls.get_session().task_name
        Uploader.upload_case_result(
            (case_id, CaseResult.unavailable, error_msg, current_time, current_time, report_path))

    @classmethod
    def upload_case_result(cls, upload_param):
        proxy = cls.get_session().proxy
        if not Uploader.is_enable() or proxy is None:
            return
        LOG.debug("Upload case result")
        case_id, result, error, start_time, end_time, report_path = \
            upload_param
        if error and len(error) > MAX_VISIBLE_LENGTH:
            error = "%s..." % error[:MAX_VISIBLE_LENGTH]
        LOG.info(
            "Get upload params: %s, %s, %s, %s, %s, %s" % (
                case_id, result, error, start_time, end_time, report_path))
        proxy.upload_result(case_id, result, error, start_time, end_time, report_path)

    @classmethod
    def upload_report_end(cls):
        proxy = cls.get_session().proxy
        if proxy is None:
            return
        LOG.info("Upload report end")
        proxy.report_end()

    @classmethod
    def _get_time(cls, testsuite_element):
        start_time = testsuite_element.get(ReportConstant.start_time, "")
        end_time = testsuite_element.get(ReportConstant.end_time, "")
        try:
            if start_time and end_time:
                start_time = int(time.mktime(time.strptime(
                    start_time, ReportConstant.time_format)) * 1000)
                end_time = int(time.mktime(time.strptime(
                    end_time, ReportConstant.time_format)) * 1000)
            else:
                timestamp = str(testsuite_element.get(
                    ReportConstant.time_stamp, "")).replace("T", " ")
                cost_time = testsuite_element.get(ReportConstant.time, "")
                if timestamp and cost_time:
                    try:
                        end_time = int(time.mktime(time.strptime(
                            timestamp, ReportConstant.time_format)) * 1000)
                    except ArithmeticError as error:
                        LOG.error("Get time error {}".format(error))
                        end_time = int(time.time() * 1000)
                    except ValueError as error:
                        LOG.error("Get time error {}".format(error))
                        end_time = int(time.mktime(time.strptime(
                            timestamp.split(".")[0], ReportConstant.time_format)) * 1000)
                    start_time = int(end_time - float(cost_time) * 1000)
                else:
                    current_time = int(time.time() * 1000)
                    start_time, end_time = current_time, current_time
        except ArithmeticError as error:
            LOG.error("Get time error {}".format(error))
            current_time = int(time.time() * 1000)
            start_time, end_time = current_time, current_time
        return start_time, end_time

    @classmethod
    def _get_task_result(cls, task_element):
        failures = int(task_element.get(ReportConstant.failures, 0))
        errors = int(task_element.get(ReportConstant.errors, 0))
        disabled = int(task_element.get(ReportConstant.disabled, 0))
        unavailable = int(task_element.get(ReportConstant.unavailable, 0))
        if disabled > 0:
            task_result = "Blocked"
        elif errors > 0 or failures > 0:
            task_result = "Failed"
        elif unavailable > 0:
            task_result = "Unavailable"
        else:
            task_result = "Passed"
        return task_result

    @classmethod
    def _get_report_path(cls, base_path, report=""):
        """拼接报告路径
        base_path: str, 报告基础路径
        report   : str, 报告相对路径
        """
        report_path = os.path.join(base_path, report)
        return report_path if report and os.path.exists(report_path) else base_path

    @classmethod
    def _get_upload_params(cls, result_file, request):
        upload_params = []
        report_path = result_file
        testsuites_element = DataHelper.parse_data_report(report_path)
        start_time, end_time = Uploader._get_time(testsuites_element)
        test_type = request.get_test_type()
        test_type_list = [HostDrivenTestType.device_test, HostDrivenTestType.windows_test,
                          DeviceTestType.stability_test, DeviceTestType.ux_test, DeviceTestType.ark_web_test]
        if test_type in test_type_list:
            for ele_testsuite in testsuites_element:
                if len(ele_testsuite) == 0:
                    LOG.error(f"No testcase in result file: {result_file}")

                ele_testcase = ele_testsuite[0]
                case_id = ele_testcase.get(ReportConstant.name, "")
                case_result, error = get_case_result(ele_testcase)
                if error and len(error) > MAX_VISIBLE_LENGTH:
                    error = "{}...".format(error[:MAX_VISIBLE_LENGTH])
                report = Uploader._get_report_path(
                    request.config.report_path, ele_testcase.get(ReportConstant.report, ""))
                result_content = ele_testcase.get(ReportConstant.result_content)
                upload_params.append(
                    (case_id, case_result, error, start_time, end_time, report, result_content,))
        else:
            for testsuite_element in testsuites_element:
                if check_mode(ModeType.developer):
                    module_name = str(get_filename_extension(
                        report_path)[0]).split(".")[0]
                else:
                    module_name = testsuite_element.get(ReportConstant.name,
                                                        "none")
                for ele_testcase in testsuite_element:
                    case_id = Uploader._get_case_id(ele_testcase, module_name)
                    case_result, error = get_case_result(ele_testcase)
                    if case_result == "Ignored":
                        LOG.info(
                            "Get upload params: {} result is ignored".format(case_id))
                        continue
                    error = ele_testcase.get(ReportConstant.message, "")
                    if error and len(error) > MAX_VISIBLE_LENGTH:
                        error = "{}...".format(error[:MAX_VISIBLE_LENGTH])
                    report = Uploader._get_report_path(
                        request.config.report_path,
                        ele_testcase.get(ReportConstant.report, ""))
                    result_content = ele_testcase.get(ReportConstant.result_content)
                    upload_params.append(
                        (case_id, case_result, error, start_time, end_time, report, result_content,))
        return upload_params

    @classmethod
    def _get_case_id(cls, case_element, package_name):
        class_name = case_element.get(ReportConstant.class_name, "none")
        method_name = case_element.get(ReportConstant.name, "none")
        case_id = "{}#{}#{}#{}".format(cls.get_session().task_name, package_name,
                                       class_name, method_name)
        return case_id
