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
import json
import os
from xml.etree import ElementTree
from _core.logger import platform_logger
from _core.executor.source import load_prio_sched_modules

LOG = platform_logger("CustomSummaryReporter")

PRIO_SCHED_REPORT_NAME = "prio_sched_modules.html"
PRIO_SCHED_REPORT_LINK = "details/" + PRIO_SCHED_REPORT_NAME
_DATA_JS_PREFIX = "window.reportData = "
_LEGACY_REPORT_NAME = "summary_report.html"
_LEGACY_EXTENDED_REPORT_MARKER = "<!--{exec_info.extended_report_row}-->"
_LEGACY_EXTENDED_REPORT_ROW = (
    "        <tr>\n"
    "            <td class=\"normal first\">Extended Reports:</td>\n"
    "            <td class=\"normal second\" colspan=\"3\">"
    "<a href='{link}' target='_blank'>{name}</a></td>\n"
    "        </tr>"
)


def _update_summary_data_js(report_path, relative_link):
    """
    Inject the extended report link into static/data.js (summary page data)
    so the Extended Reports entry is shown only when the report exists.
    """
    data_js = os.path.join(report_path, "static", "data.js")
    if not os.path.isfile(data_js):
        LOG.debug("data.js not found; skip extended report link injection")
        return
    try:
        with open(data_js, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.startswith(_DATA_JS_PREFIX):
            LOG.debug("data.js has unexpected format; skip link injection")
            return
        data = json.loads(content[len(_DATA_JS_PREFIX):])
        exec_info = data.get("exec_info")
        if not isinstance(exec_info, dict):
            LOG.debug("exec_info missing in data.js; skip link injection")
            return
        exec_info["extended_report"] = relative_link
        new_content = json.dumps(data, separators=(",", ":"))
        with open(data_js, "w", encoding="utf-8") as f:
            f.write(_DATA_JS_PREFIX + new_content)
        LOG.debug("Injected extended report link into data.js: %s", relative_link)
    except Exception as e:
        LOG.warning("Failed to inject extended report link into data.js: %s" % e)


def _update_legacy_summary_report(report_path):
    """
    Replace the extended report marker in the legacy (fallback) summary
    report with the report link row. No-op for the new vue report (the
    marker only exists when the legacy template was rendered).
    """
    summary_report = os.path.join(report_path, _LEGACY_REPORT_NAME)
    if not os.path.isfile(summary_report):
        LOG.debug("legacy summary report not found; skip link injection")
        return
    try:
        with open(summary_report, "r", encoding="utf-8") as f:
            content = f.read()
        if _LEGACY_EXTENDED_REPORT_MARKER not in content:
            return
        row_html = _LEGACY_EXTENDED_REPORT_ROW.format(
            link=PRIO_SCHED_REPORT_LINK, name=PRIO_SCHED_REPORT_NAME)
        content = content.replace(_LEGACY_EXTENDED_REPORT_MARKER, row_html)
        with open(summary_report, "w", encoding="utf-8") as f:
            f.write(content)
        LOG.debug("Injected extended report link into legacy summary report")
    except Exception as e:
        LOG.warning("Failed to inject extended report link into "
                    "legacy summary report: %s" % e)


def _get_html_template(title, table_headers, table_rows_html, empty_message="None"):
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


def generate_prio_sched_modules_report(report_path, long_task_modules,
                                      suite_execution_times, time_threshold=None):
    """
    Generate prio_sched_modules.html (combined long-task-first dispatch report).
    Table 1: Whitelist Module Dispatch Details (5 columns, dispatch order)
    Table 2: Time Limit Exceeded Modules (2 columns, time descending, appended below)
    """
    if not long_task_modules:
        return ""

    headers = ["Dispatch Order", "Module", "Estimated Time(s)", "Actual Time(s)", "Time Order (Desc)"]

    # 1. Gather all modules with their actual times (None means not executed)
    module_data = []
    for rank, (name, config_time) in enumerate(long_task_modules, 1):
        actual_time = suite_execution_times.get(name)
        module_data.append({
            "dispatch_rank": rank,
            "name": name,
            "config_time": config_time,
            "actual_time": actual_time,
            "exec_rank": None
        })

    # 2. Compute execution time ranking (descending: longest duration is rank 1),
    #    only executed modules participate in ranking
    executed_modules = [item for item in module_data if item["actual_time"] is not None]
    sorted_by_duration = sorted(executed_modules, key=lambda x: x["actual_time"], reverse=True)
    for exec_rank, item in enumerate(sorted_by_duration, 1):
        item["exec_rank"] = exec_rank

    # 3. Format table rows in dispatch order
    rows_html_list = []
    for item in module_data:
        if item["actual_time"] is None:
            actual_str = "NULL"
        elif isinstance(item["actual_time"], float):
            actual_str = f"{item['actual_time']}"
        else:
            actual_str = f"{item['actual_time']}"
        config_str = f"{item['config_time']}" if isinstance(item['config_time'], (int, float)) else f"{item['config_time']}"
        exec_rank_str = "NULL" if item["exec_rank"] is None else str(item["exec_rank"])
        row_html = (
            f"<tr>"
            f"<td>{item['dispatch_rank']}</td>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td>{config_str}</td>"
            f"<td>{actual_str}</td>"
            f"<td>{exec_rank_str}</td>"
            f"</tr>"
        )
        rows_html_list.append(row_html)

    # Build TLE table HTML (appended below the dispatch details table)
    tle_headers = ["Module", "Time(s)"]
    long_task_set = set(name for name, _ in long_task_modules)
    overtime_modules = []
    for name, actual_time in suite_execution_times.items():
        if name in long_task_set:
            continue
        if time_threshold and actual_time > time_threshold:
            overtime_modules.append({"name": name, "actual_time": actual_time})
    overtime_modules.sort(key=lambda x: x["actual_time"], reverse=True)

    tle_rows = []
    for item in overtime_modules:
        tle_rows.append(
            f"<tr><td>{html.escape(str(item['name']))}</td>"
            f"<td>{item['actual_time']}</td></tr>"
        )
    tle_rows_html = "\n                ".join(tle_rows)

    # Build combined HTML: two tables in one page
    table1_headers_html = "".join([f"<th>{h}</th>" for h in headers])
    table2_headers_html = "".join([f"<th>{h}</th>" for h in tle_headers])
    table1_rows = "\n                ".join(rows_html_list)
    table2_rows = tle_rows_html if tle_rows_html else f"<tr><td colspan='2' class='empty-tip'>None</td></tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Whitelist Module Dispatch Details</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; margin: 30px; background-color: #f4f6f9; color: #333333; }}
        .container {{ max-width: 1000px; margin: 0 auto; background-color: #ffffff; padding: 24px 32px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08); }}
        h2 {{ color: #1a365d; margin-top: 0; padding-bottom: 12px; border-bottom: 2px solid #3182ce; }}
        h3 {{ color: #1a365d; margin-top: 32px; padding-bottom: 10px; border-bottom: 1px solid #cbd5e0; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 18px; }}
        th, td {{ padding: 12px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background-color: #edf2f7; font-weight: 600; color: #2d3748; }}
        tr:hover {{ background-color: #f7fafc; }}
        .empty-tip {{ text-align: center; color: #718096; padding: 24px; font-style: italic; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Whitelist Module Dispatch Details</h2>
        <table>
            <thead><tr>{table1_headers_html}</tr></thead>
            <tbody>
                {table1_rows}
            </tbody>
        </table>
        <h3>Time Limit Exceeded Modules</h3>
        <table>
            <thead><tr>{table2_headers_html}</tr></thead>
            <tbody>
                {table2_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

    details_dir = os.path.join(report_path, "details")
    os.makedirs(details_dir, exist_ok=True)
    out_file = os.path.join(details_dir, PRIO_SCHED_REPORT_NAME)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    LOG.info("Generated prio sched modules report: %s", out_file)

    # link the report from the summary page (Extended Reports entry)
    _update_summary_data_js(report_path, PRIO_SCHED_REPORT_LINK)
    _update_legacy_summary_report(report_path)
    return out_file



def generate_all_custom_summary_reports(report_path, suite_dir="",
                                       suite_execution_times=None):
    """
    Generate independent summary reports for the long-task-first scheduling
    policy. Only called when the active policy implements IReportablePolicy.

    - Long-task set: modules in prio_sched_modules.json with duration >=
      time_threshold (from user_config.xml <taskargs>), sorted by duration
      descending → prio_sched_modules_report.html (report order = dispatch order).
    - TLE report: modules NOT in the long-task set whose actual time exceeds
      time_threshold, sorted descending → tle_modules_report.html.
    - If either configuration is missing/invalid, that report is not generated.
    - Original test reports remain completely untouched.
    """
    if not report_path:
        return

    from xdevice import Variables
    time_threshold = Variables.config.get_time_threshold()
    if time_threshold is None:
        LOG.debug("time_threshold not configured; skipping both reports")
        return

    # Merge execution times: XML (original report's pure execution time)
    # takes priority; in-memory wall-clock and caller params serve as fallback
    # for scenarios where XML is unavailable (e.g. subprocess, retry)
    merged_times = {}

    try:
        from _core.context.center import Context
        scheduler = Context.get_scheduler()
        if scheduler and getattr(scheduler, "suite_execution_times", None):
            merged_times.update(scheduler.suite_execution_times)
    except Exception as e:
        LOG.debug("Scheduler suite_execution_times not available: %s" % e)

    if suite_execution_times:
        merged_times.update(suite_execution_times)

    # XML times override: align with the original report's counting
    # (pure module execution time, excluding kit setup / install overhead)
    parsed_xml_times = parse_execution_times_from_reports(report_path)
    merged_times.update(parsed_xml_times)

    # Load all configured modules with durations
    all_modules = load_prio_sched_modules(suite_dir)

    # Long-task set: duration >= threshold, sorted by duration descending
    # (this order matches the actual dispatch order of LongTaskFirstPolicy)
    long_task_modules = [
        (name, duration) for name, duration in all_modules.items()
        if isinstance(duration, int) and duration >= time_threshold
    ]

    # Generate combined report (dispatch details + TLE in one file)
    if long_task_modules:
        generate_prio_sched_modules_report(report_path, long_task_modules,
                                          merged_times, time_threshold)
    else:
        LOG.debug("No long-task modules (duration >= %ds); skipping %s",
                  time_threshold, PRIO_SCHED_REPORT_NAME)
