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
from abc import ABC
from abc import abstractmethod
from xml.etree import ElementTree

from _core.constants import LifeStage
from _core.report.reporter_helper import ReportConstant
from _core.logger import platform_logger
from _core.testkit.json_parser import JsonParser

LOG = platform_logger("LifeStage")


class StageEvent(ABC):
    def __init__(self):
        self._event_type: str = self._stage_name()
        self._data = dict()

    @abstractmethod
    def _covert_data(self):
        pass

    def get_data(self):
        if not self._data:
            self._data.update(self._get_data())
        return self._data

    def _get_data(self):
        data = self._covert_data()
        data.update({"type": self._event_type})
        return data

    @abstractmethod
    def _stage_name(self) -> str:
        pass


class TaskStart(StageEvent):

    def __init__(self, action: str):
        super().__init__()
        self.action: str = action

    def _stage_name(self) -> str:
        return LifeStage.task_start

    def _covert_data(self) -> dict:
        from xdevice import Variables
        data = {
            "id": Variables.task_id,
            "name": Variables.task_name,
            "command": self.action,
        }
        return data


class TaskEnd(StageEvent):

    def __init__(self, report_path, unavailable, error_msg):
        super().__init__()
        self._report_path: str = report_path
        self._unavailable: int = unavailable
        self._error_msg = error_msg

    def _stage_name(self) -> str:
        return LifeStage.task_end

    def _covert_data(self):
        from xdevice import Variables
        summary_data_report = os.path.join(self._report_path, ReportConstant.summary_data_report)
        if not os.path.exists(summary_data_report):
            LOG.error("Call lifecycle error, summary report {} not exists".format(self._report_path))
            passed = failures = blocked = 0
            unavailable = self._unavailable
        else:
            task_element = ElementTree.parse(summary_data_report).getroot()
            total_tests = int(task_element.get(ReportConstant.tests, 0))
            failures = int(task_element.get(ReportConstant.failures, 0))
            blocked = int(task_element.get(ReportConstant.disabled, 0))
            ignored = int(task_element.get(ReportConstant.ignored, 0))
            unavailable = int(task_element.get(ReportConstant.unavailable, 0))
            passed = total_tests - failures - blocked - ignored

        data = {
            "id": Variables.task_id,
            "name": Variables.task_name,
            "passed": passed,
            "failures": failures,
            "blocked": blocked,
            "unavailable": unavailable,
            "error": self._error_msg,
        }
        return data


class CaseStart(StageEvent):

    def __init__(self, case_name, driver):
        super().__init__()
        self._case_name = case_name
        self.driver = driver
        self.driver_name = ""
        self.device_options = dict()
        self._get_device_options()

    def _get_device_options(self):
        case_json = self.driver[1].source
        json_config = None
        try:
            if case_json.config_file:
                json_config = JsonParser(case_json.config_file)
            # To be compatible with old code
            elif case_json.source_string and (
                    # Importing is_config_str() in _core.util will cause circular import error
                    "{" in case_json.source_string and "}" in case_json.source_string
            ):
                json_config = JsonParser(case_json.source_string)
            else:
                LOG.warning('No json config file or the json config file is empty!')
        except Exception as e:
            LOG.error(f'Error loading json config file because {e}')
        if json_config:
            self.device_options = json_config.get_environment()
            self.driver_name = json_config.get_driver_type()

    def _stage_name(self) -> str:
        return LifeStage.case_start

    def _covert_data(self) -> dict:
        from xdevice import Variables
        data = {
            "id": Variables.task_id,
            "driver": self.driver_name,
            "devices": self.device_options,
            "name": self._case_name
        }
        return data


class CaseEnd(StageEvent):

    def __init__(self, case_name, case_result, error_msg=""):
        super().__init__()
        self._case_name = case_name
        self._case_result = case_result
        self._error_msg = error_msg

    def _stage_name(self) -> str:
        return LifeStage.case_end

    def _covert_data(self) -> dict:
        from xdevice import Variables
        data = {
            "id": Variables.task_id,
            "name": self._case_name,
            "case_result": self._case_result,
            "error_msg": self._error_msg,
        }
        return data


class ILifeStageListener(ABC):
    __slots__ = ()

    @abstractmethod
    def __on_event__(self, stage_event: StageEvent):
        pass
