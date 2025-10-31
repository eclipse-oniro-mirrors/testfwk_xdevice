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

from ohos.constants import ParserType
from ohos.parser import *

__all__ = ["VulkanTestParser"]

LOG = platform_logger("VulkanParser")

@Plugin(type=Plugin.PARSER, id=ParserType.vulkan_test)
class VulkanTestParser(IParser):

    def __init__(self):
        self.cache = list()

    def __process__(self, lines):
        for line in lines:
            line = str(line).strip().rstrip("\r")
            self.cache.append(line)
            if len(self.cache) < 100:
                continue
            self._print_cache_line()

    def __done__(self):
        self._print_cache_line()


    def _print_cache_line(self):
        for line in self.cache:
            LOG.debug(line)
        self.cache.clear()

    def mark_test_as_blocked(self, test):
        pass