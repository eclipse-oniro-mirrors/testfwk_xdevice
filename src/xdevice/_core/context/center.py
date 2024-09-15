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

from _core.context.single import SingleType
from _core.context.service import ContextImpl
from _core.context.channel import CommandQueue

__all__ = ['Context']

LOG = platform_logger("Center")


class CompatibleSession:
    upload_address: str = ""
    task_type: str = ""
    task_name: str = ""
    mode: str = ""  # 当前模式
    proxy = None  # 外部网络
    device_labels = []


def check_params(param):
    attrs = ["upload_address", "task_type", "task_name", "mode", "device_labels"]
    session = None
    for attr in attrs:
        result = getattr(param, attr, None)
        if not result:
            continue
        session = CompatibleSession()
        session.upload_address = param.upload_address
        session.task_type = param.task_type
        session.task_name = param.task_name
        session.mode = param.mode
        session.proxy = param.proxy
        session.device_labels = param.device_labels
        break
    return session


class Context(metaclass=SingleType):
    _session = None

    @staticmethod
    def session():
        if Context._session:
            return Context._session
        from xdevice import Scheduler
        result = check_params(Scheduler)
        if result:
            Context._session = result
        else:
            Context._session = ContextImpl().get_session_info()
        return Context._session

    @staticmethod
    def command_queue():
        return CommandQueue()

    @staticmethod
    def is_executing():
        if not ContextImpl().has_attr("xDevice"):
            return True
        return ContextImpl().read_attr("xDevice")

    @staticmethod
    def set_execute_status(status: bool):
        ContextImpl().write_attr("xDevice", status)

    @staticmethod
    def is_task_executing():
        if Context.get_scheduler():
            return Context.get_scheduler().is_executing()
        return False

    @staticmethod
    def get_scheduler():
        if ContextImpl().get_active_state():
            scheduler = ContextImpl().get_active_state().get_active_scheduler()
            if scheduler:
                return scheduler
        LOG.warning("Scheduler  unloaded")
        return None

    @staticmethod
    def terminate_cmd_exec():
        ContextImpl().write_attr("xDevice", False)
        if Context.get_scheduler():
            return Context.get_scheduler().terminate_cmd_exec
        return None
