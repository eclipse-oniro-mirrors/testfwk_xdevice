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

from _core.logger import platform_logger
from _core.environment.manager_env import DeviceSelectionOption
from _core.constants import DeviceLabelType
from _core.constants import ConfigConst
from _core.utils import is_config_str

LOG = platform_logger("OptionUtil")


def find_device_options(environment_config, options, test_source):
    devices_option = []
    index = 1
    for device_dict in environment_config:
        label = device_dict.get("label", "")
        required_manager = device_dict.get("type", "device")
        required_manager = \
            required_manager if required_manager else "device"
        if not label:
            continue
        device_option = DeviceSelectionOption(options, label, test_source)
        device_dict.pop("type", None)
        device_dict.pop("label", None)
        device_option.required_manager = required_manager
        device_option.extend_value = device_dict
        device_option.source_file = \
            test_source.config_file or test_source.source_string
        if hasattr(device_option, "env_index"):
            device_option.env_index = index
        index += 1
        devices_option.append(device_option)
    return devices_option


def calculate_device_options(device_options, environment_config,
                             options, test_source):
    # calculate difference
    diff_value = len(environment_config) - len(device_options)
    if device_options and diff_value == 0:
        return device_options

    else:
        diff_value = diff_value if diff_value else 1
        if str(test_source.source_file).endswith(".bin"):
            device_option = DeviceSelectionOption(
                options, DeviceLabelType.ipcamera, test_source)
        else:
            device_option = DeviceSelectionOption(
                options, None, test_source)

        device_option.source_file = \
            test_source.source_file or test_source.source_string
        device_option.required_manager = "device"
        for device_dict in environment_config:
            label = device_dict.get("label", None)
            if label is None or label == '':
                import copy
                dst_option = copy.deepcopy(device_option)
                dst_option.extend_value = device_dict
                device_options.append(dst_option)
        if not environment_config:
            device_options.extend([device_option] * diff_value)
        LOG.debug("Assign device options and it's length is %s"
                  % len(device_options))
    return device_options


def get_device_options(options, test_source):
    device_options = []
    config_file = test_source.config_file
    environment_config = []
    from _core.testkit.json_parser import JsonParser
    if test_source.source_string and is_config_str(
            test_source.source_string):
        json_config = JsonParser(test_source.source_string)
        environment_config = json_config.get_environment()
        device_options = find_device_options(
            environment_config, options, test_source)
    elif config_file and os.path.exists(config_file):
        json_config = JsonParser(test_source.config_file)
        environment_config = json_config.get_environment()
        device_options = find_device_options(
            environment_config, options, test_source)

    device_options = calculate_device_options(
        device_options, environment_config, options, test_source)

    if ConfigConst.component_mapper in options.keys():
        required_component = options.get(ConfigConst.component_mapper). \
            get(test_source.module_name, None)
        for device_option in device_options:
            device_option.required_component = required_component
    return device_options
