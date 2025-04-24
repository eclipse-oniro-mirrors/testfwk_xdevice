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

import csv
import json
import os
import sys
import time

from xdevice import FilePermission
from xdevice import platform_logger
from xdevice import ExecInfo
from xdevice import ReportConstant
from xdevice import ResultReporter

LOG = platform_logger("ReportMain")


def __get_report_path():
    args = sys.argv
    if args is None or len(args) < 2:
        report_path = input("enter path >>> ")
    else:
        report_path = args[1]
    LOG.info(f"report path: {report_path}")
    if not os.path.exists(report_path):
        LOG.error("report path does not exist")
        return None
    return report_path


def main_report():
    report_path = __get_report_path()
    if report_path is None:
        return
    # 删除旧报告文件
    for filename in os.listdir(report_path):
        if filename in [ReportConstant.details_vision_report, ReportConstant.passes_vision_report,
                        ReportConstant.failures_vision_report]:
            os.remove(os.path.join(report_path, filename))
    start_time = time.strftime(ReportConstant.time_format, time.localtime())
    renew_report(report_path, start_time)


def renew_report(report_path: str, start_time: str):
    task_info = ExecInfo()
    task_info.platform = "None"
    task_info.test_type = "Test"
    task_info.device_name = "None"
    task_info.test_time = start_time
    result_report = ResultReporter()
    result_report.__generate_reports__(report_path, task_info=task_info)


def export_report():
    """export report to csv file"""
    report_path = __get_report_path()
    if report_path is None:
        return
    data_js = os.path.join(report_path, "static", "data.js")
    if not os.path.exists(data_js):
        LOG.error(f"file {data_js} does not exist")
        LOG.info("please check the report path or run command 'tool renew_report -rp xx' first")
        return
    export_csv = os.path.join(report_path, "export_report.csv")
    if os.path.exists(export_csv):
        os.remove(export_csv)
    try:
        with open(data_js, encoding="utf-8") as jsf:
            data = json.loads(jsf.read()[20:])
        modules_info = data.get("modules", [])
    except Exception as e:
        LOG.error(f"export report error, {e}")
        return

    attr_names = ["name", "time", "tests", "passed", "failed", "blocked",
                  "ignored", "unavailable", "passingrate", "error"]
    csv_fd = os.open(export_csv, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
    with os.fdopen(csv_fd, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
        # 写入表头
        writer.writerow(map(lambda n: n.capitalize(), attr_names))
        # 写入数据
        for module in modules_info:
            row = [module.get(name, "") for name in attr_names]
            writer.writerow(row)
    LOG.info(f"export path: {export_csv}")


if __name__ == "__main__":
    main_report()
