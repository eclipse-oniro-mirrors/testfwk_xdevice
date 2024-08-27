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

from _core.context.single import SingleType
from _core.context.proxy import SessionInfo
from _core.context.abs import Sub

__all__ = ["ActiveState", "ContextImpl"]


class ActiveState:

    def __init__(self, scheduler: Sub or None = None):
        self._active = scheduler

    def is_running(self) -> bool:
        if self._active:
            return self._active.is_executing()
        return False

    def get_active_scheduler(self) -> Sub:
        return self._active


class ContextImpl(metaclass=SingleType):
    def __init__(self):
        self._lock = RLock()
        self._session_info: SessionInfo = SessionInfo()
        self._state: ActiveState = ActiveState()
        self._global_attr = dict()

    def get_session_info(self) -> SessionInfo:
        return self._session_info

    def update_session_info(self, info: SessionInfo):
        self._session_info = info

    def update_state(self, state: ActiveState):
        with self._lock:
            self._state = state

    def get_active_state(self):
        with self._lock:
            return self._state

    def write_attr(self, key, value):
        self._global_attr.update({key: value})

    def has_attr(self, key):
        return key in self._global_attr.keys()

    def read_attr(self, key):
        if key in self._global_attr.keys():
            return self._global_attr.get(key)
        return None

    def remove_attr(self, key):
        if key in self._global_attr.keys():
            self._global_attr.pop(key)
        return None
