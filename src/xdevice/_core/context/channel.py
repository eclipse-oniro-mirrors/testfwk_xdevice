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

from _core.context.single import SingleType

__all__ = ["CommandQueue"]


class CommandQueue(metaclass=SingleType):
    __instance = None
    _queue = []

    @classmethod
    def append(cls, command):
        cls._queue.append(command)

    @classmethod
    def pop(cls, index=-1):
        return cls._queue.pop(index)

    @classmethod
    def get_last(cls):
        return cls._queue[-1]

    @classmethod
    def get(cls, index: int):
        return cls._queue[index]

    @classmethod
    def update(cls, index, command):
        cls._queue[index] = command

    @classmethod
    def list_history(cls):
        for command_info in cls._queue[:-1]:
            yield command_info

    @classmethod
    def size(cls):
        return len(cls._queue)

    @classmethod
    def is_empty(cls):
        return cls.size() == 0
