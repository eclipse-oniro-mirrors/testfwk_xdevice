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

from dataclasses import dataclass

from _core.context.life_stage import StageEvent

__all__ = ["UploadParams", "SessionInfo", "Connector", "Binder"]


@dataclass
class UploadParams:
    upload_address: str = ""
    task_type: str = ""
    task_name: str = ""
    mode: str = ""  # 当前模式
    proxy = None  # 外部网络
    device_labels = []


@dataclass
class SessionInfo:
    upload_address: str = ""
    task_type: str = ""
    task_name: str = ""
    mode: str = ""  # 当前模式
    proxy = None  # 外部网络
    device_labels = []


class Connector:  # 插件间通信

    def __init__(self, info: SessionInfo):
        self._session_info = info

    def connect(self):
        from _core.context.service import ContextImpl
        if self._session_info:
            ContextImpl().update_session_info(self._session_info)


class Binder:

    @staticmethod
    def is_executing():
        from _core.context.center import Context
        return Context.is_executing()

    @staticmethod
    def session():
        from _core.context.center import Context
        return Context.session()

    @staticmethod
    def notify_stage(stage_event: StageEvent):
        from _core.context.center import Context
        if Context.get_scheduler():
            Context.get_scheduler().notify_stage(stage_event)
