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

import queue
import time
import uuid
import copy
from abc import ABC
from abc import abstractmethod
from typing import Dict
from typing import List

from _core.error import ErrorMessage
from _core.exception import ExecuteTerminate
from _core.exception import LiteDeviceError
from _core.exception import DeviceError
from _core.context.abs import Sub
from _core.executor.concurrent import QueueMonitorThread
from _core.logger import platform_logger
from _core.constants import ModeType

from _core.utils import convert_mac
from _core.interface import LifeCycle
from _core.constants import ConfigConst
from _core.plugin import get_plugin
from _core.exception import ParamError
from _core.plugin import Plugin
from _core.constants import ListenerType
from _core.context.result import ExecuteFinished
from _core.constants import TestExecType
from _core.context.center import Context
from _core.context.handler import report_not_executed
from _core.context.life_stage import ILifeStageListener
from _core.context.life_stage import StageEvent

LOG = platform_logger("Impl")

__all__ = ["BaseScheduler"]


class BaseScheduler(Sub, ABC):
    _auto_retry = -1
    _queue_monitor_thread = None
    _channel = Context.command_queue()
    test_number = 0
    _stage_listeners: List[ILifeStageListener] = []

    @classmethod
    def add_life_stage_listener(cls, listener: ILifeStageListener):
        cls._stage_listeners.append(listener)

    @classmethod
    def notify_stage(cls, stage_event: StageEvent):
        for listener in cls._stage_listeners:
            listener.__on_event__(stage_event)

    @classmethod
    def remove_life_stage_listener(cls):
        cls._stage_listeners.clear()

    @classmethod
    def __max_command_size__(cls) -> int:
        return 50

    @classmethod
    def _start_auto_retry(cls):
        if not cls.is_need_auto_retry():
            cls._auto_retry = -1
            LOG.debug("No need auto retry")
            return
        if cls._auto_retry > 0:
            cls._auto_retry -= 1
            if cls._auto_retry == 0:
                cls._auto_retry = -1
            from _core.command.console import Console
            console = Console()
            console.command_parser("run --retry")

    @classmethod
    def _check_auto_retry(cls, options):
        if cls._auto_retry < 0 and \
                int(getattr(options, ConfigConst.auto_retry, 0)) > 0:
            value = int(getattr(options, ConfigConst.auto_retry, 0))
            cls._auto_retry = value if value <= 10 else 10

    @staticmethod
    def _get_actual_repeat(module_name, module_repeat_in_testfile, repeat) -> int:
        repeat_in_testfile = module_repeat_in_testfile.get(module_name)
        return repeat_in_testfile if repeat_in_testfile else repeat

    @staticmethod
    def _get_module_repeat_in_testfile(task) -> Dict[str, int]:
        module_repeat = {}
        testfile_config = getattr(task.config, "tf_suite", {})
        if testfile_config:
            for module_name, cfg in testfile_config.items():
                repeat = cfg.get(ConfigConst.repeat)
                if not repeat:
                    continue
                try:
                    report = int(repeat)
                    if report < 1:
                        repeat = 1
                    module_repeat.update({module_name: repeat})
                except ValueError:
                    pass
        return module_repeat

    def _repeat_test_drivers(self, task):
        # 方式1：获取run命令或配置文件里设置的repeat参数
        repeat = getattr(task.config, ConfigConst.repeat, 1)
        if repeat < 1:
            repeat = 1
        # 方式2：获取test-file.json文件里设置的repeat参数
        module_repeat_in_testfile = self._get_module_repeat_in_testfile(task)

        max_repeat = repeat
        if module_repeat_in_testfile:
            max_repeat = max(module_repeat_in_testfile.values())
        max_repeat = max(max_repeat, repeat)
        self.set_repeat_index(max_repeat)
        task.config.update({ConfigConst.repeat: max_repeat})

        repeat_drivers = []
        for index in range(1, max_repeat + 1):
            for test_driver in task.test_drivers:
                _, test = test_driver
                actual_repeat = self._get_actual_repeat(test.source.module_name, module_repeat_in_testfile, repeat)
                if index > actual_repeat:
                    continue
                cur_test_driver = test_driver if index == 1 else copy.deepcopy(test_driver)
                desc = cur_test_driver[1]
                desc.unique_id = "{}_{}".format(desc.unique_id, index)
                repeat_drivers.append(cur_test_driver)
        task.test_drivers = repeat_drivers

    def __execute__(self, task):
        if not self._channel.is_empty():
            task_id = str(uuid.uuid1()).split("-")[0]
            LOG.debug("Run command: {}".format(convert_mac(self._channel.get_last())))
            run_command = self._channel.pop()
            self._channel.append((task_id, run_command, task.config.report_path))
            if self._channel.size() > self.__max_command_size__():
                self._channel.pop(0)

        unavailable = 0
        err_msg = ""
        try:
            available, unavailable = self._check_task(task)
            if available == 0:
                return
            self._repeat_test_drivers(task)
            self.test_number = len(task.test_drivers)
            self._do_execute_(task)
        except (ParamError, ValueError, TypeError, SyntaxError, AttributeError,
                DeviceError, LiteDeviceError, ExecuteTerminate) as exception:
            error_no = getattr(exception, "error_no", "")
            err_msg = "%s[%s]" % (str(exception), error_no) if error_no else str(exception)
            error_no = error_no if error_no else "00000"
            LOG.exception(exception, exc_info=True, error_no=error_no)
        finally:
            task_info = self.generate_task_report(task)
            listeners = self.__create_listeners__(task)
            for listener in listeners:
                listener.__ended__(LifeCycle.TestTask, task_info,
                                   test_type=task_info.test_type, task=task)
            finished = ExecuteFinished(unavailable, err_msg)
            self._on_execute_finished_(task, finished)

    def run_in_loop(self, task, run_func, loop_finally=None):
        try:
            current_driver_threads = {}
            test_drivers = task.test_drivers
            message_queue = queue.Queue()
            # execute test drivers
            params = message_queue, test_drivers, current_driver_threads
            self._queue_monitor_thread = self._start_queue_monitor(*params)
            while test_drivers:
                if len(current_driver_threads) > self.max_driver_threads_size():
                    time.sleep(3)
                    continue
                # clear remaining test drivers when scheduler is terminated
                if not self.is_executing():
                    LOG.info("Clear test drivers")
                    self._clear_not_executed(task, test_drivers)
                    break
                # 处理监控线程
                # get test driver and device
                self._run(run_func, task, *params)
                self.peek_monitor(*params)
                test_drivers.pop(0)
            while True:
                if not self._queue_monitor_thread.is_alive():
                    break
                time.sleep(3)
        finally:
            if callable(loop_finally):
                loop_finally()

    def is_monitor_alive(self):
        return self._queue_monitor_thread and self._queue_monitor_thread.is_alive()

    def peek_monitor(self, message_queue, test_drivers, current_driver_threads):
        if self.is_monitor_alive():
            return
        self._start_queue_monitor(message_queue, test_drivers, current_driver_threads)

    @classmethod
    def _clear_not_executed(cls, task, test_drivers):
        if Context.session().mode != ModeType.decc:
            # clear all
            test_drivers.clear()
            return
        # The result is reported only in DECC mode, and also clear all.
        LOG.error("Case no run: task execution terminated!", error_no="00300")
        error_message = "Execute Terminate[00300]"
        report_not_executed(task.config.report_path, test_drivers, error_message)
        test_drivers.clear()

    def _run(self, run_func, task, message_queue, test_drivers, current_driver_threads):
        if callable(run_func):
            run_func(task, test_drivers, current_driver_threads, message_queue)

    @staticmethod
    def _start_queue_monitor(message_queue, test_drivers,
                             current_driver_threads):
        queue_monitor_thread = QueueMonitorThread(message_queue,
                                                  current_driver_threads,
                                                  test_drivers)
        queue_monitor_thread.daemon = True
        queue_monitor_thread.start()
        return queue_monitor_thread

    def _on_task_prepare_(self, options):
        self._check_auto_retry(options)

    def _on_task_finished_(self):
        from _core.context.log import RuntimeLogs
        self._start_auto_retry()
        RuntimeLogs.stop_task_logcat()
        RuntimeLogs.stop_encrypt_log()

    @classmethod
    def __create_listeners__(cls, task) -> list:
        listeners = []
        # append log listeners
        log_listeners = get_plugin(Plugin.LISTENER, ListenerType.log)
        for log_listener in log_listeners:
            log_listener_instance = log_listener.__class__()
            listeners.append(log_listener_instance)
        # append report listeners
        report_listeners = get_plugin(Plugin.LISTENER, ListenerType.report)
        for report_listener in report_listeners:
            report_listener_instance = report_listener.__class__()
            setattr(report_listener_instance, "report_path",
                    task.config.report_path)
            listeners.append(report_listener_instance)
        # append upload listeners
        upload_listeners = get_plugin(Plugin.LISTENER, ListenerType.upload)
        for upload_listener in upload_listeners:
            upload_listener_instance = upload_listener.__class__()
            listeners.append(upload_listener_instance)
        return listeners

    @classmethod
    def _exec_type_(cls) -> list:
        return [TestExecType.device_test, TestExecType.host_test, TestExecType.host_driven_test]

    @classmethod
    def _check_task(cls, task):
        available, unavailable = 0, 0
        for test_driver in task.test_drivers:
            _, desc = test_driver
            if not desc.error:
                available += 1
                continue
            unavailable += 1
            error_message = ErrorMessage.Common.Code_0101014.format(desc.source.module_name)
            LOG.error(error_message)
            report_not_executed(task.config.report_path, [test_driver], error_message)
        return available, unavailable

    def _prepare_environment(self, task):
        if getattr(task.config, ConfigConst.test_environment, ""):
            self._reset_environment(task.config.get(
                ConfigConst.test_environment, ""))
        elif getattr(task.config, ConfigConst.configfile, ""):
            self._reset_environment(config_file=task.config.get(
                ConfigConst.configfile, ""))

    @classmethod
    def _call_terminate(cls):
        cls.set_repeat_index(0)
        cls._auto_retry = 0
        return cls._terminate()

    @classmethod
    @abstractmethod
    def _terminate(cls):
        pass

    @abstractmethod
    def max_driver_threads_size(self) -> int:
        pass
