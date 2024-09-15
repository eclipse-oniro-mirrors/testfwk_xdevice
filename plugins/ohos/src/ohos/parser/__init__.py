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
import copy
import re
import threading
import time
import json
from enum import Enum

from xdevice import LifeCycle
from xdevice import IParser
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import check_pub_key_exist
from xdevice import StateRecorder
from xdevice import TestDescription
from xdevice import ResultCode
from xdevice import CommonParserType
from xdevice import get_cst_time
from xdevice import get_delta_time_ms