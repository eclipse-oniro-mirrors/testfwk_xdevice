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

from _core.logger import platform_logger
from _core.executor.source import TestDictSource

LOG = platform_logger("TDD")


class TSD:
    @classmethod
    def update_test_type_in_source(cls, key, value):
        LOG.debug("update test type dict in source")
        TestDictSource.test_type[key] = value

    @classmethod
    def update_ext_type_in_source(cls, key, value):
        LOG.debug("update ext type dict in source")
        TestDictSource.exe_type[key] = value

    @classmethod
    def clear_test_dict_source(cls):
        TestDictSource.clear()

    @classmethod
    def reset_test_dict_source(cls):
        TestDictSource.reset()
