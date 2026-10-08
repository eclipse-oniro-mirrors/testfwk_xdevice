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

import html
import os
from xml.etree import ElementTree
from _core.logger import platform_logger
from _core.config.config_manager import UserConfigManager

LOG = platform_logger("CustomSummaryReporter")

PRIO_SCHED_REPORT_NAME = "prio_sched_suites_report.html"
TLE_REPORT_NAME = "tle_suites_report.html"


def _get_html_template(title, table_headers, table_rows_html, empty_message="暂无数据"):
    headers_html = "".join([f"<th>{h}</th>" for h in table_headers])
    if not table_rows_html:
        content_html = f"<tr><td colspan='{len(table_headers)}' class='empty-tip'>{empty_message}</td></tr>"
    else:
        content_html = table_rows_html

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            margin: 30px;
            background-color: #f4f6f9;
            color: #333333;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: #ffffff;
            padding: 24px 32px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }}
        h2 {{
            color: #1a365d;
            margin-top: 0;
            padding-bottom: 12px;
            border-bottom: 2px solid #3182ce;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 18px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background-color: #edf2f7;
            font-weight: 600;
            color: #2d3748;
        }}
        tr:hover {{
            background-color: #f7fafc;
        }}
        .empty-tip {{
            text-align: center;
            color: #718096;
            padding: 24px;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>{title}</h2>
        <table>
            <thead>
                <tr>
                    {headers_html}
                </tr>
            </thead>
            <tbody>
                {content_html}
            </tbody>
        </table>
    </div>
</body>
</html>
"""


def parse_execution_times_from_reports(report_path):
    """
    Parse module execution times (in seconds) from result XML files in report_path/result.
    """
    execution_times = {}
    result_dir = os.path.join(report_path, "result")
    if not os.path.isdir(result_dir):
        return execution_times

    for file_name in os.listdir(result_dir):
        if not file_name.endswith(".xml"):
            continue
        xml_file = os.path.join(result_dir, file_name)
        try:
            tree = ElementTree.parse(xml_file)
            root = tree.getroot()
            name_attr = (root.get("name") or "").strip()
            module_name = file_name[:-4] if name_attr in ("", "AllTests") else name_attr
            raw_time = root.get("time", "0")
            try:
                module_time = float(raw_time)
            except (ValueError, TypeError):
                module_time = 0.0
            execution_times[module_name] = round(module_time, 2)
        except Exception as e:
            LOG.debug("Error parsing xml %s for time: %s" % (xml_file, e))

    return execution_times


def generate_prio_sched_suites_report(report_path, whitelist_suites, suite_execution_times):
    """
    Generate prio_sched_suites_report.html.
    Columns (exact 5 columns in order):
    1. 白名单排位
    2. 测试套名称
    3. 白名单配置时长
    4. 实际执行时长
    5. 执行时长排位
    Displayed in order of whitelist ranking.
    Unexecuted suites show NULL for actual time and are excluded from ranking.
    """
    if not whitelist_suites:
        return ""

    headers = ["白名单排位", "测试套名称", "白名单配置时长", "实际执行时长", "执行时长排位"]

    # 1. Gather all suites with their actual times (None means not executed)
    suite_data = []
    for rank, (name, config_time) in enumerate(whitelist_suites, 1):
        actual_time = suite_execution_times.get(name)
        suite_data.append({
            "whitelist_rank": rank,
            "name": name,
            "config_time": config_time,
            "actual_time": actual_time,
            "exec_rank": None
        })

    # 2. Compute execution time ranking (descending: longest duration is rank 1),
    #    only executed suites participate in ranking
    executed_suites = [item for item in suite_data if item["actual_time"] is not None]
    sorted_by_duration = sorted(executed_suites, key=lambda x: x["actual_time"], reverse=True)
    for exec_rank, item in enumerate(sorted_by_duration, 1):
        item["exec_rank"] = exec_rank

    # 3. Format table rows in whitelist order
    rows_html_list = []
    for item in suite_data:
        if item["actual_time"] is None:
            actual_str = "NULL"
        elif isinstance(item["actual_time"], float):
            actual_str = f"{item['actual_time']}s"
        else:
            actual_str = f"{item['actual_time']}"
        config_str = f"{item['config_time']}s" if isinstance(item['config_time'], (int, float)) else f"{item['config_time']}"
        exec_rank_str = "NULL" if item["exec_rank"] is None else str(item["exec_rank"])
        row_html = (
            f"<tr>"
            f"<td>{item['whitelist_rank']}</td>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td>{config_str}</td>"
            f"<td>{actual_str}</td>"
            f"<td>{exec_rank_str}</td>"
            f"</tr>"
        )
        rows_html_list.append(row_html)

    html_content = _get_html_template(
        title="白名单执行情况汇总报告",
        table_headers=headers,
        table_rows_html="\n                ".join(rows_html_list)
    )

    out_file = os.path.join(report_path, PRIO_SCHED_REPORT_NAME)
    os.makedirs(report_path, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    LOG.info("Generated prio sched suites report: %s", out_file)
    return out_file


def generate_tle_suites_report(report_path, time_threshold, whitelist_names, suite_execution_times):
    """
    Generate tle_suites_report.html.
    Columns (exact 2 columns):
    1. 测试套名称
    2. 执行时长
    Lists non-whitelist suites exceeding time_threshold, sorted descending by actual execution time.
    """
    if time_threshold is None or time_threshold <= 0:
        return ""

    headers = ["测试套名称", "执行时长"]
    whitelist_set = set(whitelist_names or [])

    overtime_suites = []
    for name, actual_time in suite_execution_times.items():
        if name in whitelist_set:
            continue
        if actual_time > time_threshold:
            overtime_suites.append({"name": name, "actual_time": actual_time})

    # Sort descending by actual execution time
    overtime_suites.sort(key=lambda x: x["actual_time"], reverse=True)

    rows_html_list = []
    for item in overtime_suites:
        actual_str = f"{item['actual_time']}s" if isinstance(item['actual_time'], float) else f"{item['actual_time']}"
        row_html = (
            f"<tr>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td>{actual_str}</td>"
            f"</tr>"
        )
        rows_html_list.append(row_html)

    html_content = _get_html_template(
        title="超时测试套执行汇总报告",
        table_headers=headers,
        table_rows_html="\n                ".join(rows_html_list),
        empty_message="无超时（非白名单）测试套件"
    )

    out_file = os.path.join(report_path, TLE_REPORT_NAME)
    os.makedirs(report_path, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    LOG.info("Generated TLE suites report: %s", out_file)
    return out_file


def generate_all_custom_summary_reports(report_path, suite_dir="", suite_execution_times=None):
    """
    Load configurations and generate independent summary reports accordingly.
    - If prio_sched_suites.json is valid: generate prio_sched_suites_report.html.
    - If sched_config.json (time_threshold) is valid: generate tle_suites_report.html.
    - If either is missing/invalid: do not generate that report.
    - Original test reports remain completely untouched.
    """
    if not report_path:
        return

    # Merge execution times from parameters, Scheduler.suite_execution_times, and XML reports
    merged_times = {}
    parsed_xml_times = parse_execution_times_from_reports(report_path)
    merged_times.update(parsed_xml_times)

    try:
        from _core.executor.scheduler import Scheduler
        if hasattr(Scheduler, "suite_execution_times") and Scheduler.suite_execution_times:
            merged_times.update(Scheduler.suite_execution_times)
    except Exception as e:
        LOG.debug("Scheduler suite_execution_times not available: %s" % e)

    if suite_execution_times:
        merged_times.update(suite_execution_times)

    whitelist_suites = UserConfigManager.load_prio_sched_suites(suite_dir)
    time_threshold = UserConfigManager.load_sched_config(suite_dir)

    # 1. Whitelist report
    if whitelist_suites:
        generate_prio_sched_suites_report(report_path, whitelist_suites, merged_times)
    else:
        LOG.debug("prio_sched_suites.json is missing or invalid; skipping %s", PRIO_SCHED_REPORT_NAME)

    # 2. TLE report
    if time_threshold is not None and time_threshold > 0:
        whitelist_names = [s[0] for s in whitelist_suites] if whitelist_suites else []
        generate_tle_suites_report(report_path, time_threshold, whitelist_names, merged_times)
    else:
        LOG.debug("sched_config.json is missing or invalid; skipping %s", TLE_REPORT_NAME)
