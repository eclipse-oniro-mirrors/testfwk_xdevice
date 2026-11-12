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

from _core.executor.policy import ISchedulingPolicy
from _core.executor.policy import IReportablePolicy
from _core.executor.policy import register_policy
from _core.logger import platform_logger

LOG = platform_logger("LongTaskFirstPolicy")


@register_policy("long_task_first")
class LongTaskFirstPolicy(ISchedulingPolicy, IReportablePolicy):
    """Long-task-first scheduling policy (LPT: Longest Processing Time first).

    Sorts test drivers whose duration >= time_threshold to the front of the
    queue in descending duration order; remaining drivers stay FIFO. Threshold
    comes from user_config.xml <taskargs><time_threshold>.
    """

    @staticmethod
    def _get_duration(test_driver):
        source = getattr(test_driver[1], "source", None) if len(test_driver) > 1 else None
        return getattr(source, "duration", 0) if source else 0

    def sort_test_drivers(self, test_drivers):
        from xdevice import Variables
        threshold = Variables.config.get_time_threshold()
        if threshold is None:
            LOG.warning(
                "time_threshold not configured in user_config.xml; "
                "falling back to FIFO ordering")
            return test_drivers

        long_tasks = []
        fifo_tasks = []
        for driver in test_drivers:
            if self._get_duration(driver) >= threshold:
                long_tasks.append(driver)
            else:
                fifo_tasks.append(driver)

        long_tasks.sort(key=self._get_duration, reverse=True)
        return long_tasks + fifo_tasks

    def generate_reports(self, report_path, task=None):
        from _core.report.custom_summary_reporter import (
            generate_all_custom_summary_reports)
        suite_dir = getattr(
            getattr(task, "config", None), "testcases_path", "")
        generate_all_custom_summary_reports(report_path, suite_dir=suite_dir)
