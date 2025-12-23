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
#

from xdevice import UserConfigManager
from xdevice import platform_logger
from xdevice import get_local_ip

__all__ = ["OHOSUserConfigManager"]
LOG = platform_logger("OHOSConfigManager")


class OHOSUserConfigManager(UserConfigManager):

    def __init__(self, config_file="", env=""):
        super().__init__(config_file, env)

    def get_com_device(self, target_name):
        devices = []

        for node in self.config_content.findall(target_name):
            if node.attrib["type"] != "com":
                continue

            device = [node.attrib]

            # get remote device
            data_dic = {}
            for sub in node:
                if sub.text is not None and sub.tag != "serial":
                    data_dic[sub.tag] = sub.text
            if data_dic:
                if data_dic.get("ip", "") == get_local_ip():
                    data_dic["ip"] = "127.0.0.1"
                device.append(data_dic)
                devices.append(device)
                continue

            # get local device
            for serial in node.findall("serial"):
                data_dic = {}
                for sub in serial:
                    if sub.text is None:
                        data_dic[sub.tag] = ""
                    else:
                        data_dic[sub.tag] = sub.text
                device.append(data_dic)
            devices.append(device)
        return devices

    def get_devices(self, target_name):
        devices = [env for env in self.environment if env.get("label") == "ohos"]
        if devices:
            return devices

        device_list = {}
        for node in self.config_content.findall(target_name):
            data_dic = {}
            skip_rule = [node.attrib["type"] != "usb-hdc"]
            if all(skip_rule):
                continue
            data_dic["usb_type"] = node.attrib["type"]
            for sub in node:
                if sub.text is None:
                    data_dic[sub.tag] = ""
                else:
                    data_dic[sub.tag] = sub.text
            if not data_dic.get("ip", "") or data_dic.get("ip", "") == get_local_ip():
                data_dic["ip"] = "127.0.0.1"
            label = node.get("label", None)
            if label and label != "ohos":
                continue
            if data_dic["ip"] not in device_list:
                device_list[data_dic["ip"]] = data_dic
        return list(device_list.values())
