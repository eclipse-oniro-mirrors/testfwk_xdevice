#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2022 Huawei Device Co., Ltd.
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
from enum import Enum

from ohos.constants import Constant
from ohos.utils import parse_line_key_value


def parse_product_info(line, is_params, product_info):
    if Constant.PRODUCT_PARAMS_START in line:
        is_params = True
    elif Constant.PRODUCT_PARAMS_END in line:
        is_params = False
    if is_params:
        # line output: 2023-11-13 15:51:23.453 OsFullName = xx
        line = "".join(line.split(" ")[2:])
        product_info.update(parse_line_key_value(line))


class StatusCodes(Enum):
    FAILURE = -2
    START = 1
    ERROR = -1
    SUCCESS = 0
    IN_PROGRESS = 2
    IGNORE = -3
    BLOCKED = 3

