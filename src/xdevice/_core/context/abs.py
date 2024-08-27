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

from abc import ABC
from abc import abstractmethod

from _core.context.life_stage import StageEvent
from _core.context.life_stage import ILifeStageListener
from _core.context.result import ExecuteFinished
from _core.error import ErrorMessage
from _core.exception import ParamError
from _core.interface import IScheduler
from _core.logger import platform_logger

LOG = platform_logger("Abs")

__all__ = ["Sub"]


class Sub(IScheduler, ABC):
    _is_need_auto_retry = False
    _is_running = True
    _repeat_index = 1

    def exec_command(self, command, options):
        if command != "run":
            raise ParamError(ErrorMessage.Common.Code_0101012.format(command))
        exec_type = options.exectype
        if exec_type in self._exec_type_():
            self._exec_task(options)
        else:
            LOG.error(ErrorMessage.Common.Code_0101013.format(exec_type))

    def _register(self):
        from _core.context.service import ContextImpl
        from _core.context.service import ActiveState
        ContextImpl().update_state(ActiveState(self))
        if not ContextImpl().read_attr("xDevice"):
            ContextImpl().write_attr("xDevice", True)

    def _exec_task(self, options):
        """
        Directly allocates a device and execute a device test.
        """
        task = None
        self.remove_life_stage_listener()
        self._register()
        try:
            Sub._is_running = True
            self._on_task_prepare_(options)
            task = self.__discover__(options.__dict__)
            self.__execute__(task)
        except (ParamError, ValueError, TypeError, SyntaxError,
                AttributeError) as exception:
            LOG.exception(exception, exc_info=False)
            self._on_task_error_(task, exception)
        finally:
            self._on_task_finished_()
            Sub._is_running = False

    @classmethod
    @abstractmethod
    def __max_command_size__(cls) -> int:
        pass

    @classmethod
    def terminate_cmd_exec(cls):
        cls._is_running = False
        result = cls._call_terminate()
        if result:
            return result
        return None

    @classmethod
    def is_executing(cls):
        return cls._is_running

    @classmethod
    @abstractmethod
    def _exec_type_(cls) -> list:
        pass

    def _on_task_prepare_(self, options):
        pass

    def _on_task_finished_(self):
        pass

    def _on_task_error_(self, task, exception: Exception):
        pass

    def _on_execute_finished_(self, task, result: ExecuteFinished):
        pass

    @abstractmethod
    def _do_execute_(self, task):
        pass

    @classmethod
    @abstractmethod
    def _call_terminate(cls):
        pass

    @classmethod
    @abstractmethod
    def _reset_environment(cls, environment="", config_file=""):
        pass

    @abstractmethod
    def generate_task_report(self, task):
        pass

    @classmethod
    def is_need_auto_retry(cls):
        return cls._is_need_auto_retry

    @classmethod
    def set_need_auto_retry(cls, is_need: bool):
        cls._is_need_auto_retry = is_need

    @classmethod
    def get_repeat_index(cls):
        return cls._repeat_index

    @classmethod
    def set_repeat_index(cls, value: int):
        cls._repeat_index = value

    @classmethod
    @abstractmethod
    def notify_stage(cls, stage_event: StageEvent):
        pass

    @classmethod
    @abstractmethod
    def add_life_stage_listener(cls, listener: ILifeStageListener):
        pass

    @classmethod
    @abstractmethod
    def remove_life_stage_listener(cls):
        pass
