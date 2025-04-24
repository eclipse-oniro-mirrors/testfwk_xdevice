#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) Huawei Device Co., Ltd. 2025. All right reserved.
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
from typing import Dict, List, Union
from xml.etree import ElementTree

from _core.constants import Cluster, ConfigConst
from _core.error import ErrorMessage
from xdevice import platform_logger
from ..models import TaskInfo
from ..runner import Runner

LOG = platform_logger("Worker")


def new_element(tag: str, attrib: dict = None, text: str = None):
    """
    tag   : element's tag
    attrib: element's attribute
    text  : element's text
    """
    if attrib is None:
        attrib = {}
    ele = ElementTree.Element(tag, attrib)
    ele.text = text
    return ele


def element_tostring(element: ElementTree.Element):
    return ElementTree.tostring(element).decode()


class UserConfig:

    def __init__(self, devices: List[Dict[str, Union[int, str]]], testcase_dir: str, resource_dir: str, **kwargs):
        """
        devices: test devices
        testcase_dir: testcase's path
        resource_dir: resource's path
        """
        self.devices = devices
        self.testcase_dir = testcase_dir
        self.resource_dir = resource_dir
        self.kwargs = kwargs

        self._cfg_root = None

    def _get_config(self, tag: str, clear: bool = True):
        """获取配置节点，获取失败则新建"""
        element = self._cfg_root.find(tag)
        if element is not None:
            if clear:
                element.clear()
        else:
            element = new_element(tag)
            self._cfg_root.append(element)
        return element

    def _get_devices(self):

        def inner_add(_label, _device):
            if _label not in devices.keys():
                devices[_label] = []
            devices.get(_label).append(_device)

        devices = {}
        for dev in self.devices:
            sn = dev.get("sn")
            if not sn:
                continue
            device = {
                "ip": "127.0.0.1",
                "port": "8710",
                "sn": sn
            }
            inner_add("ohos", device)
        return devices

    @staticmethod
    def _build_device(label, devices):
        """build default device"""
        usb_type = {"ohos": "usb-hdc"}
        attrib = {"type": usb_type.get(label, ""), "label": label}
        ele_device = new_element("device", attrib=attrib)
        for dev in devices:
            ele_info = new_element("info", attrib=dev)
            ele_device.append(ele_info)
        return ele_device

    def _set_root(self):
        """优先读取测试工程里的配置文件作为模板，否则使用这里代码设定的配置项"""
        config_path = os.path.join(self._get_project_path(), "config", "user_config.xml")
        if os.path.exists(config_path):
            try:
                root = ElementTree.parse(config_path).getroot()
                if root.find("taskargs") is not None:
                    self._cfg_root = root
                    return
            except ElementTree.ParseError as e:
                LOG.error(e)
        self._cfg_root = new_element("user_config")

    def _set_environment(self):
        environment = self._get_config("environment")
        for label, devices in self._get_devices().items():
            ele_device = self._build_device(label, devices)
            environment.append(ele_device)

    def _set_testcases(self):
        ele_dir = new_element(ConfigConst.tag_dir, text=self.testcase_dir)
        testcases = self._get_config("testcases")
        testcases.append(ele_dir)

    def _set_resource(self):
        ele_dir = new_element(ConfigConst.tag_dir, text=self.resource_dir)
        resource = self._get_config("resource")
        resource.append(ele_dir)

    def _set_device_log(self):
        device_log = self._get_config("devicelog", clear=False)
        config = {
            ConfigConst.tag_enable: "ON",
            ConfigConst.tag_loglevel: "INFO",
            ConfigConst.tag_dir: ""
        }
        for tag, text in config.items():
            if device_log.find(tag) is None:
                device_log.append(new_element(tag, text=text))

    def _set_log_level(self):
        log_level = self._get_config(ConfigConst.tag_loglevel)
        log_level.text = "DEBUG"

    def _get_project_path(self):
        case_dir = self.testcase_dir
        return os.path.dirname(case_dir) if case_dir.endswith("testcases") else case_dir

    def generation(self):
        self._set_root()
        self._set_environment()
        self._set_testcases()
        self._set_resource()
        self._set_device_log()
        self._set_log_level()
        return "".join([line.strip() for line in element_tostring(self._cfg_root).split("\n")])


class WorkerRunner(Runner):

    def __init__(self, task_info: dict):
        super().__init__(TaskInfo(**task_info))

        self.report_path = os.path.join(Cluster.report_root_path, self.task_id, self.task_info.block_id)

    def run(self):
        os.makedirs(self.report_path, exist_ok=True)
        try:
            devices = self.task_info.devices
            if not devices:
                raise Exception(ErrorMessage.Cluster.Code_0104034)
            self.prepare_project()
            testcase_path = os.path.join(self.project_path, "testcases")
            if not os.path.exists(testcase_path):
                testcase_path = self.project_path
            resource_path = os.path.join(self.project_path, "resource")
            if not os.path.exists(resource_path):
                resource_path = self.project_path
            case_list = ";".join(self.case_names)
            env_cfg = UserConfig(devices, testcase_path, resource_path).generation()
            command = f"run -l {case_list} -env {env_cfg} -rp {self.report_path}"
            LOG.info(f"run command: {command}")
            from xdevice.__main__ import main_process
            main_process(command)
        except Exception as e:
            LOG.error(e)
            self.mark_cases_error(self.case_names, str(e))
