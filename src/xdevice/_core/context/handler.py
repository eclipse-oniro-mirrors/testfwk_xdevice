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

import json
import os
import shutil
import time
from xml.etree import ElementTree

from _core.constants import CaseResult
from _core.constants import FilePermission
from _core.logger import platform_logger
from _core.report.reporter_helper import ReportConstant

__all__ = [
    "handle_repeat_result", "update_report_xml",
    "report_not_executed", "get_case_result"]

LOG = platform_logger("Context")


def handle_repeat_result(report_xml, report_path, round_folder=""):
    if not round_folder:
        return report_xml
    round_path = os.path.join(report_path, "result", round_folder)
    if not os.path.exists(round_path):
        os.makedirs(round_path)
    LOG.debug("move result file to round folder")
    target_path = os.path.join(round_path, os.path.basename(report_xml))
    shutil.move(report_xml, target_path)
    return target_path


def update_report_xml(report_xml, props):
    """update devices, start time, end time, etc. to the result file"""
    if not os.path.exists(report_xml) or not props:
        return
    try:
        root = ElementTree.parse(report_xml).getroot()
    except ElementTree.ParseError as e:
        LOG.error(f"parse result xml error! xml file {report_xml}")
        LOG.error(f"error message: {e}")
        return
    for k, v in props.items():
        if k == ReportConstant.devices:
            v = f"<![CDATA[{json.dumps(v, separators=(',', ':'))}]]>"
        root.set(k, v)
    result_fd = os.open(report_xml, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, FilePermission.mode_644)
    with os.fdopen(result_fd, mode="w", encoding="utf-8") as result_file:
        result_file.write(ElementTree.tostring(root).decode())


def report_not_executed(report_path, test_drivers, error_message, task=None):
    from _core.utils import check_result_report
    from _core.utils import get_repeat_round
    from _core.utils import get_sub_path

    repeat, repeat_round = 1, 1
    if task is not None:
        repeat = task.config.repeat

    for test_driver in test_drivers:
        _, test = test_driver
        module_name = test.source.module_name
        test_name = test.source.test_name
        repeat_round = get_repeat_round(test.unique_id)
        round_folder = f"round{repeat_round}" if repeat > 1 else ""

        # get report file
        if task and getattr(task.config, "testdict", ""):
            report_file = os.path.join(get_sub_path(test.source.source_file), "%s.xml" % test_name)
        else:
            report_file = os.path.join(report_path, "result", round_folder, "%s.xml" % module_name)

        # get report name
        report_name = test_name if not test_name.startswith("{") else "report"
        # here, normally create empty report and then upload result
        check_result_report(report_path, report_file, error_message, report_name, module_name,
                            result_kind=CaseResult.unavailable)

        update_props = {
            ReportConstant.start_time: time.strftime(ReportConstant.time_format, time.localtime()),
            ReportConstant.end_time: time.strftime(ReportConstant.time_format, time.localtime()),
            ReportConstant.repeat: str(repeat),
            ReportConstant.round: str(repeat_round),
            ReportConstant.test_type: test.source.test_type
        }
        update_report_xml(report_file, update_props)


def get_case_result(ele_case):
    error_msg = ele_case.get(ReportConstant.message, "")
    result_kind = ele_case.get(ReportConstant.result_kind, "")
    if result_kind != "":
        return result_kind, error_msg
    result = ele_case.get(ReportConstant.result, "")
    status = ele_case.get(ReportConstant.status, "")
    # 适配HCPTest的测试结果，其用例失败时，会在testcase下新建failure节点，存放错误信息
    if len(ele_case) > 0:
        error_msg = "\n\n".join([failure.get(ReportConstant.message, "") for failure in ele_case])
        return CaseResult.failed, error_msg
    if result == ReportConstant.false and (status == ReportConstant.run or status == ""):
        return CaseResult.failed, error_msg
    if status in [ReportConstant.blocked, ReportConstant.disable, ReportConstant.error]:
        return CaseResult.blocked, error_msg
    if status in [ReportConstant.skip, ReportConstant.not_run]:
        return CaseResult.ignored, error_msg
    if status in [ReportConstant.unavailable]:
        return CaseResult.unavailable, error_msg
    return CaseResult.passed, ""
