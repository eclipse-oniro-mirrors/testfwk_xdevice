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

from ohos.constants import Constant

__all__ = ["parse_line_key_value", "parse_strings_key_value"]


def parse_line_key_value(line):
    """parse line which should format as 'key = value'"""
    param = {}
    if "=" in line:
        arr = line.split("=")
        if len(arr) == 2:
            param.setdefault(arr[0].strip(), arr[1].strip())
    return param


def parse_strings_key_value(in_str):
    """parse string which should format as 'key = value'"""
    is_param, params = False, {}
    for line in in_str.split("\n"):
        if Constant.PRODUCT_PARAMS_START in line:
            is_param = True
        elif Constant.PRODUCT_PARAMS_END in line:
            is_param = False
        if is_param:
            params.update(parse_line_key_value(line))
    return params
