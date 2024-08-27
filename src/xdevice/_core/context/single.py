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

from threading import RLock

__all__ = ["SingleType"]


class SingleType(type):
    _lock = RLock()

    def __call__(cls, *args, **kwargs):
        with SingleType._lock:
            if not hasattr(cls, "_instance"):
                cls._instance = super(SingleType, cls).__call__(*args, **kwargs)
        return getattr(cls, "_instance")
