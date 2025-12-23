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

import copy
import datetime
import os
import queue
import shutil
import json
import threading
from collections import Counter

from _core.context.impl import BaseScheduler
from _core.context.result import ExecuteFinished
from _core.utils import unique_id
from _core.utils import check_mode
from _core.utils import get_filename_extension

from _core.utils import get_cst_time
from _core.environment.manager_env import EnvironmentManager
from _core.error import ErrorMessage
from _core.exception import ExecuteTerminate
from _core.exception import LiteDeviceError
from _core.exception import DeviceError
from _core.executor.request import Request
from _core.executor.request import Descriptor

from _core.plugin import Config
from _core.constants import SchedulerType
from _core.plugin import Plugin
from _core.constants import TestExecType
from _core.constants import CKit
from _core.constants import ModeType
from _core.constants import DeviceLabelType
from _core.constants import ConfigConst
from _core.constants import ReportConst
from _core.executor.concurrent import DriversThread
from _core.executor.concurrent import ModuleThread
from _core.executor.concurrent import ExecuteMessage
from _core.executor.source import TestSetSource
from _core.executor.source import find_test_descriptors
from _core.executor.source import find_testdict_descriptors
from _core.logger import platform_logger
from _core.utils import convert_serial
from _core.report.reporter_helper import ExecInfo

from _core.context.life_stage import TaskStart, StageEvent
from _core.context.life_stage import TaskEnd
from _core.context.life_stage import CaseStart
from _core.context.life_stage import CaseEnd
from _core.context.upload import Uploader
from _core.context.option_util import get_device_options
from _core.context.tdd import TSD
from _core.exception import ParamError
from _core.context.handler import report_not_executed
from _core.context.life_stage import ILifeStageListener
from _core.variables import Variables

__all__ = ["Scheduler"]

LOG = platform_logger("Scheduler")


@Plugin(type=Plugin.SCHEDULER, id=SchedulerType.scheduler)
class Scheduler(BaseScheduler):
    """
    The Scheduler is the main entry point for client code that wishes to
    discover and execute tests.
    """
    lock = threading.Lock()
    terminate_result = queue.Queue()
    used_devices = {}

    def _do_execute_(self, task):
        Scheduler.used_devices.clear()
        if task.config.exectype == TestExecType.device_test:
            self._device_test_execute(task)
        elif task.config.exectype == TestExecType.host_test:
            self._host_test_execute(task)
        else:
            LOG.info("Exec type %s is bypassed" % task.config.exectype)

    def __discover__(self, args):
        """Discover task to execute"""
        from _core.executor.request import Task
        repeat = Variables.config.taskargs.get(ConfigConst.repeat)
        if not repeat:
            repeat = args.get(ConfigConst.repeat, 1)
        args.update({ConfigConst.repeat: int(repeat)})
        config = Config()
        config.update(args)
        task = Task(drivers=[])
        task.init(config)
        self.add_life_stage_listener(TaskListener())
        action = args.get("action", "")
        task_start = TaskStart(action)
        self.notify_stage(task_start)
        root_descriptor = self._find_test_root_descriptor(task.config)
        task.set_root_descriptor(root_descriptor)
        return task

    def _device_test_execute(self, task):
        try:
            self.run_in_loop(task, run_func=self.run_dynamic_concurrent)
        finally:
            Scheduler.__reset_environment__(self.used_devices)

    def _host_test_execute(self, task, ):
        """Execute host test"""
        self.run_in_loop(task, run_func=self.run_host_test)

    def run_host_test(self, task, test_drivers, current_driver_threads, message_queue):
        # get test driver and device
        test_driver = test_drivers[0]

        # display executing progress
        self._display_executing_process(None, test_driver,
                                        test_drivers)

        # start driver thread
        thread = self._start_driver_thread(current_driver_threads, (
            None, message_queue, task, test_driver))

        if task.config.scheduler == SchedulerType.synchronize:
            thread.join()

    def generate_task_report(self, task):
        task_info = ExecInfo()
        test_type = getattr(task.config, "testtype", [])
        task_name = getattr(task.config, "task", "")
        if task_name:
            task_info.test_type = str(task_name).upper()
        else:
            task_info.test_type = ",".join(test_type) if test_type else "Test"
        if self.used_devices:
            serials = []
            platforms = []
            test_labels = []
            for serial, device in self.used_devices.items():
                serials.append(convert_serial(serial))
                platform = str(device.test_platform)
                test_label = str(device.label).capitalize()
                if platform not in platforms:
                    platforms.append(platform)
                if test_label not in test_labels:
                    test_labels.append(test_label)
            task_info.device_name = ",".join(serials)
            task_info.platform = ",".join(platforms)
            task_info.device_label = ",".join(test_labels)
        else:
            task_info.device_name = "None"
            task_info.platform = "None"
            task_info.device_label = "None"
        task_info.repeat = getattr(task.config, ConfigConst.repeat, 1)
        task_info.test_time = task.config.start_time
        task_info.product_info = getattr(task, "product_info", "")

        return task_info

    def __allocate_environment__(self, options, test_driver):
        device_options = get_device_options(options, test_driver[1].source)
        environment = None
        env_manager = EnvironmentManager()
        while True:
            if not self.is_executing():
                break
            if not self.is_monitor_alive():
                LOG.error("Queue monitor thread is dead.")
                break
            environment = env_manager.apply_environment(device_options)
            applied_device_cnt = len(environment.devices)
            required_device_cnt = len(device_options)
            if applied_device_cnt == required_device_cnt:
                return environment
            else:
                env_manager.release_environment(environment)
                LOG.debug("'%s' is waiting available device",
                          test_driver[1].source.test_name)
                if env_manager.check_device_exist(device_options):
                    continue
                else:
                    raise DeviceError(ErrorMessage.Common.Code_0101021.format(required_device_cnt, applied_device_cnt))

        return environment

    @classmethod
    def __free_environment__(cls, environment):
        env_manager = EnvironmentManager()
        env_manager.release_environment(environment)

    @staticmethod
    def __reset_environment__(used_devices):
        env_manager = EnvironmentManager()
        env_manager.reset_environment(used_devices)

    @classmethod
    def _check_device_spt(cls, kit, driver_request, device):
        kit_spt = cls._parse_property_value(ConfigConst.spt,
                                            driver_request, kit)
        if not kit_spt:
            setattr(device, ConfigConst.task_state, False)
            LOG.error("Spt is empty", error_no="00108")
            return
        if getattr(driver_request, ConfigConst.product_info, ""):
            product_info = getattr(driver_request,
                                   ConfigConst.product_info)
            if not isinstance(product_info, dict):
                LOG.warning("Product info should be dict, %s",
                            product_info)
                setattr(device, ConfigConst.task_state, False)
                return
            device_spt = product_info.get("Security Patch", None)
            if not device_spt or not \
                    Scheduler._compare_spt_time(kit_spt, device_spt):
                LOG.error("The device %s spt is %s, "
                          "and the test case spt is %s, "
                          "which does not meet the requirements" %
                          (device.device_sn, device_spt, kit_spt),
                          error_no="00116")
                setattr(device, ConfigConst.task_state, False)
                return

    def _decc_task_setup(self, environment, task):
        config = Config()
        config.update(task.config.__dict__)
        config.environment = environment
        driver_request = Request(config=config)

        if environment is None:
            return False

        for device in environment.devices:
            if not getattr(device, ConfigConst.need_kit_setup, True):
                LOG.debug("Device %s need kit setup is false" % device)
                continue

            # do task setup for device
            kits_copy = copy.deepcopy(task.config.kits)
            setattr(device, ConfigConst.task_kits, kits_copy)
            for kit in getattr(device, ConfigConst.task_kits, []):
                if not self.is_executing():
                    break
                try:
                    kit.__setup__(device, request=driver_request)
                except (ParamError, ExecuteTerminate, DeviceError,
                        LiteDeviceError, ValueError, TypeError,
                        SyntaxError, AttributeError) as exception:
                    error_no = getattr(exception, "error_no", "00000")
                    LOG.exception(
                        "Task setup device: %s, exception: %s" % (
                            environment.__get_serial__(),
                            exception), exc_info=False, error_no=error_no)
                if kit.__class__.__name__ == CKit.query and \
                        device.label in [DeviceLabelType.ipcamera]:
                    self._check_device_spt(kit, driver_request, device)
            LOG.debug("Set device %s need kit setup to false" % device)
            setattr(device, ConfigConst.need_kit_setup, False)

        for device in environment.devices:
            if not getattr(device, ConfigConst.task_state, True):
                return False

        # set product_info to self.task
        if getattr(driver_request, ConfigConst.product_info, "") and \
                not getattr(task, ConfigConst.product_info, ""):
            product_info = getattr(driver_request, ConfigConst.product_info)
            if not isinstance(product_info, dict):
                LOG.warning("Product info should be dict, %s",
                            product_info)
            else:
                setattr(task, ConfigConst.product_info, product_info)
        return True

    def run_dynamic_concurrent(self, task, test_drivers, current_driver_threads, message_queue):
        task_unused_env = []
        test_driver = test_drivers[0]
        self.notify_stage(CaseStart(test_driver[1].source.module_name, test_driver))

        if getattr(task.config, ConfigConst.history_report_path, ""):
            module_name = test_driver[1].source.module_name
            if not self._is_module_need_retry(task, module_name):
                self._display_executing_process(None, test_driver,
                                                test_drivers)
                LOG.info("%s are passed, no need to retry" % module_name)
                self._append_history_result(task, module_name)
                LOG.info("")
                return

        if getattr(task.config, ConfigConst.component_mapper, ""):
            module_name = test_driver[1].source.module_name
            self._component_task_setup(task, module_name)

        # get environment
        try:
            environment = self.__allocate_environment__(
                task.config.__dict__, test_driver)
        except DeviceError as exception:
            self._handle_device_error(exception, task, test_drivers)
            self.notify_stage(CaseEnd(test_driver[1].source.module_name, "Failed", exception.args))
            return
        if not self.is_executing():
            if environment:
                Scheduler.__free_environment__(environment)

        if check_mode(ModeType.decc) or getattr(
                task.config, ConfigConst.check_device, False):
            LOG.info("Start to check environment: %s" %
                     environment.__get_serial__())
            status = self._decc_task_setup(environment, task)
            if not status:
                self.__free_environment__(environment)
                task_unused_env.append(environment)
                error_message = "Load Error[00116]"
                report_not_executed(task.config.report_path, [test_driver],
                                    error_message, task)
                return

            else:
                LOG.info("Environment %s check success",
                         environment.__get_serial__())

        # display executing progress
        self._display_executing_process(environment, test_driver,
                                        test_drivers)

        # add to used devices and set need_kit_setup attribute
        self._append_used_devices(environment, self.used_devices)

        # start driver thread
        self._start_driver_thread(current_driver_threads, (
            environment, message_queue, task, test_driver))

        self._do_taskkit_teardown(self.used_devices, task_unused_env)

    @classmethod
    def _append_history_result(cls, task, module_name):
        history_report_path = getattr(
            task.config, ConfigConst.history_report_path, "")
        from _core.report.result_reporter import ResultReporter
        params = ResultReporter.get_task_info_params(
            history_report_path)

        if not params or not params[ReportConst.data_reports]:
            LOG.debug("Task info record data reports is empty")
            return

        report_data_dict = dict(params[ReportConst.data_reports])
        if module_name not in report_data_dict.keys():
            module_name_ = str(module_name).split(".")[0]
            if module_name_ not in report_data_dict.keys():
                LOG.error("%s not in data reports" % module_name)
                return
            module_name = module_name_

        from xdevice import SuiteReporter
        if check_mode(ModeType.decc):
            virtual_report_path, report_result = SuiteReporter. \
                get_history_result_by_module(module_name)
            LOG.debug("Append history result: (%s, %s)" % (
                virtual_report_path, report_result))
            SuiteReporter.append_report_result(
                (virtual_report_path, report_result))
        else:
            history_execute_result = report_data_dict.get(module_name, "")
            LOG.info("Start copy %s" % history_execute_result)
            file_name = get_filename_extension(history_execute_result)[0]
            if os.path.exists(history_execute_result):
                result_dir = \
                    os.path.join(task.config.report_path, "result")
                os.makedirs(result_dir, exist_ok=True)
                target_execute_result = "%s.xml" % os.path.join(
                    task.config.report_path, "result", file_name)
                shutil.copyfile(history_execute_result, target_execute_result)
                LOG.info("Copy %s to %s" % (
                    history_execute_result, target_execute_result))
                if check_mode(ModeType.controller):
                    request = Request("", task.test_drivers[0][1], "", task.config)
                    exec_message = ExecuteMessage("", "", "", "")
                    exec_message.set_result(target_execute_result)
                    exec_message.set_request(request)
                    # # 是不是得加上調度已經停止的流程了
                    Uploader.upload_module_result(exec_message)
            else:
                error_msg = "Copy failed! %s not exists!" % \
                            history_execute_result
                raise ParamError(error_msg)

    def _handle_device_error(self, exception, task, test_drivers):
        test_driver = test_drivers[0]
        self._display_executing_process(None, test_driver, test_drivers)
        error_message = str(exception)
        LOG.exception(error_message, exc_info=False, error_no=exception.error_no)
        report_not_executed(task.config.report_path, [test_driver], error_message, task)

    def _start_driver_thread(self, current_driver_threads, thread_params):
        environment, message_queue, task, test_driver = thread_params

        if task.config.scheduler == SchedulerType.module:
            driver_thread = ModuleThread(test_driver, task, environment,
                                         message_queue, self.lock)
        else:
            driver_thread = DriversThread(test_driver, task, environment,
                                          message_queue)
        thread_name = self._get_thread_name(current_driver_threads)
        driver_thread.daemon = True
        driver_thread.name = thread_name
        driver_thread.set_listeners(self.__create_listeners__(task))
        driver_thread.start()
        current_driver_threads.setdefault(thread_name, driver_thread)
        LOG.info(f"Driver executing in thread {driver_thread.ident}")
        LOG.info(f"Thread {thread_name} execute started")
        return driver_thread

    @classmethod
    def _do_taskkit_teardown(cls, used_devices, task_unused_env):
        for device in used_devices.values():
            if getattr(device, ConfigConst.need_kit_setup, True):
                continue

            for kit in getattr(device, ConfigConst.task_kits, []):
                try:
                    kit.__teardown__(device)
                except Exception as error:
                    LOG.debug("Do task kit teardown: %s" % error)
            setattr(device, ConfigConst.task_kits, [])
            setattr(device, ConfigConst.need_kit_setup, True)

        for environment in task_unused_env:
            for device in environment.devices:
                setattr(device, ConfigConst.task_state, True)
                setattr(device, ConfigConst.need_kit_setup, True)

    def _display_executing_process(self, environment, test_driver,
                                   test_drivers):
        source = test_driver[1].source
        source_content = source.source_file or source.source_string
        test_type = source.test_type
        if environment is None:
            LOG.info("[%d / %d] Executing: %s, Driver: %s" %
                     (self.test_number - len(test_drivers) + 1,
                      self.test_number, source_content,
                      test_type))
            return

        LOG.info("[%d / %d] Executing: %s, Device: %s, Driver: %s" %
                 (self.test_number - len(test_drivers) + 1,
                  self.test_number, source_content,
                  environment.__get_serial__(),
                  test_type))

    @classmethod
    def _get_thread_name(cls, current_driver_threads):
        thread_id = get_cst_time().strftime('%Y-%m-%d-%H-%M-%S-%f')
        while thread_id in current_driver_threads.keys():
            thread_id = get_cst_time().strftime('%Y-%m-%d-%H-%M-%S-%f')
        return thread_id

    @classmethod
    def _append_used_devices(cls, environment, used_devices):
        if environment is not None:
            for device in environment.devices:
                device_serial = device.__get_serial__() if device else "None"
                if device_serial and device_serial not in used_devices.keys():
                    used_devices[device_serial] = device

    @classmethod
    def _reset_environment(cls, environment="", config_file=""):
        env_manager = EnvironmentManager()
        env_manager.env_stop()
        EnvironmentManager(environment, config_file)

    @classmethod
    def _restore_environment(cls):
        env_manager = EnvironmentManager()
        env_manager.env_stop()
        EnvironmentManager()

    def _on_task_error_(self, task, exception: Exception):
        Uploader.upload_unavailable_result(str(exception.args))

    def _on_execute_finished_(self, task, result: ExecuteFinished):
        TSD.reset_test_dict_source()
        LOG.debug('Starting to notify stage...')
        self.notify_stage(TaskEnd(task.config.report_path, result.unavailable, result.error_msg))
        LOG.debug('Starting to upload task result...')
        Uploader.upload_task_result(task, result.error_msg)
        if getattr(task.config, ConfigConst.test_environment, "") or \
                getattr(task.config, ConfigConst.configfile, ""):
            self._restore_environment()
        self.upload_report_end()

    @staticmethod
    def _find_test_root_descriptor(config):
        if getattr(config, ConfigConst.task, None) or \
                getattr(config, ConfigConst.testargs, None):
            Scheduler._pre_component_test(config)

        if getattr(config, ConfigConst.subsystems, "") or \
                getattr(config, ConfigConst.parts, "") or \
                getattr(config, ConfigConst.component_base_kit, ""):
            uid = unique_id("Scheduler", "component")
            if config.subsystems or config.parts:
                test_set = (config.subsystems, config.parts)
            else:
                kit = getattr(config, ConfigConst.component_base_kit)
                test_set = kit.get_white_list()

            root = Descriptor(uuid=uid, name="component",
                              source=TestSetSource(test_set),
                              container=True)

            root.children = find_test_descriptors(config)
            return root
            # read test list from testdict
        if getattr(config, ConfigConst.testdict, "") != "" and getattr(
                config, ConfigConst.testfile, "") == "":
            uid = unique_id("Scheduler", "testdict")
            root = Descriptor(uuid=uid, name="testdict",
                              source=TestSetSource(config.testdict),
                              container=True)
            root.children = find_testdict_descriptors(config)
            return root

            # read test list from testfile, testlist or task
        test_set = getattr(config, ConfigConst.testfile, "") or getattr(
            config, ConfigConst.testlist, "") or getattr(
            config, ConfigConst.task, "") or getattr(
            config, ConfigConst.testcase)
        if test_set:
            fname, _ = get_filename_extension(test_set)
            uid = unique_id("Scheduler", fname)
            root = Descriptor(uuid=uid, name=fname,
                              source=TestSetSource(test_set), container=True)
            if config.scheduler == SchedulerType.module:
                Scheduler._find_children_module(root, config)
            else:
                Scheduler._find_children_default(root, config)
            return root
        else:
            raise ParamError(ErrorMessage.Common.Code_0101022)

    @staticmethod
    def _find_children_default(root, config):
        root.children = find_test_descriptors(config)

    @staticmethod
    def _find_children_module(root, config):
        desc = find_test_descriptors(config)
        common_kits = {}
        task_list = {}
        all_data = {}
        for i in desc:
            module_subsystem = i.source.module_subsystem
            if module_subsystem not in task_list:
                task_list.update({module_subsystem: 1})
            else:
                task_list.update({module_subsystem: task_list.get(module_subsystem) + 1})
            if module_subsystem not in all_data:
                all_data[module_subsystem] = {
                    "run-command": [],
                    'pre-push': [],
                    "push": []
                }
            kits = Scheduler._get_test_kits(i.source.config_file)
            for kit in kits:
                if kit.get("type") == "AppInstallKit":
                    continue
                if kit.get("type") == "ShellKit":
                    shell_kit = kit.get("run-command", [])
                    for command in shell_kit:
                        if "remount" in command or "mkdir" in command:
                            all_data[module_subsystem].get("run-command").append(command)
                if kit.get("type") == "PushKit":
                    pre_push_kit = kit.get("pre-push", [])
                    for command in pre_push_kit:
                        if "remount" in command or "mkdir" in command:
                            all_data[module_subsystem].get("pre-push").append(command)
                    push_kit = kit.get("push", [])
                    all_data[module_subsystem].get("push").extend(push_kit)
        for _, value in all_data.items():
            for key1, value1 in value.items():
                common = value1
                count = Counter(common)
                new_common = [k for k, v in count.items() if v > 1]
                value[key1] = new_common
        for key, value in all_data.items():
            common_kit_tem = [{
                'type': 'ShellKit',
                'run-command': value.get("run-command", [])
            }, {
                'type': 'CommonPushKit',
                'pre-push': value.get("pre-push", []),
                "push": value.get("push", [])
            }]
            common_kits.update({key: common_kit_tem})
        LOG.debug(common_kits)
        LOG.debug(task_list)
        root.children = sorted(desc, key=lambda x: x.source.module_subsystem)
        setattr(root, "common_kits", common_kits)
        setattr(root, "task_list", task_list)

    @staticmethod
    def _get_test_kits(test_source):
        try:
            from _core.testkit.json_parser import JsonParser
            json_config = JsonParser(test_source)
            return json_config.get_kits()
        except ParamError as error:
            LOG.error(error, error_no=error.error_no)
            return ""

    @classmethod
    def _terminate(cls):
        LOG.info("Start to terminate execution")
        return Scheduler.terminate_result.get()

    @classmethod
    def upload_report_end(cls):
        if getattr(cls, "tmp_json", None):
            os.remove(cls.tmp_json)
            del cls.tmp_json
        Uploader.upload_report_end()

    @classmethod
    def _is_module_need_retry(cls, task, module_name):
        failed_flag = False
        if check_mode(ModeType.decc):
            from xdevice import SuiteReporter
            for module, _ in SuiteReporter.get_failed_case_list():
                if module_name == module or str(module_name).split(
                        ".")[0] == module:
                    failed_flag = True
                    break
        else:
            from xdevice import ResultReporter
            history_report_path = \
                getattr(task.config, ConfigConst.history_report_path, "")
            params = ResultReporter.get_task_info_params(history_report_path)
            if params and params[ReportConst.unsuccessful_params]:
                if dict(params[ReportConst.unsuccessful_params]).get(
                        module_name, []):
                    failed_flag = True
                elif dict(params[ReportConst.unsuccessful_params]).get(
                        str(module_name).split(".")[0], []):
                    failed_flag = True
        return failed_flag

    @classmethod
    def _compare_spt_time(cls, kit_spt, device_spt):
        if not kit_spt or not device_spt:
            return False
        try:
            kit_time = str(kit_spt).split("-")[:2]
            device_time = str(device_spt).split("-")[:2]
            k_spt = datetime.datetime.strptime(
                "-".join(kit_time), "%Y-%m")
            d_spt = datetime.datetime.strptime("-".join(device_time), "%Y-%m")
        except ValueError as value_error:
            LOG.debug("Date format is error, %s" % value_error.args)
            return False
        month_interval = int(k_spt.month) - int(d_spt.month)
        year_interval = int(k_spt.year) - int(d_spt.year)
        LOG.debug("Kit spt (year=%s, month=%s), device spt (year=%s, month=%s)"
                  % (k_spt.year, k_spt.month, d_spt.year, d_spt.month))
        if year_interval < 0:
            return True
        if year_interval == 0 and month_interval in range(-11, 3):
            return True
        if year_interval == 1 and month_interval + 12 in (1, 2):
            return True
        return False

    @classmethod
    def _parse_property_value(cls, property_name, driver_request, kit):
        test_args = copy.deepcopy(
            driver_request.config.get(ConfigConst.testargs, dict()))
        property_value = ""
        if ConfigConst.pass_through in test_args.keys():
            pt_dict = json.loads(test_args.get(ConfigConst.pass_through, ""))
            property_value = pt_dict.get(property_name, None)
        elif property_name in test_args.keys:
            property_value = test_args.get(property_name, None)
        return property_value if property_value else \
            kit.properties.get(property_name, None)

    @classmethod
    def _pre_component_test(cls, config):
        if not config.kits:
            return
        cur_kit = None
        for kit in config.kits:
            if kit.__class__.__name__ == CKit.component:
                cur_kit = kit
                break
        if not cur_kit:
            return
        get_white_list = getattr(cur_kit, "get_white_list", None)
        if not callable(get_white_list):
            return
        subsystems, parts = get_white_list()
        if not subsystems and not parts:
            return
        setattr(config, ConfigConst.component_base_kit, cur_kit)

    @classmethod
    def _component_task_setup(cls, task, module_name):
        component_kit = task.config.get(ConfigConst.component_base_kit, None)
        if not component_kit:
            # only -p -s .you do not care about the components that can be
            # supported. you only want to run the use cases of the current
            # component
            return
        LOG.debug("Start component task setup")
        _component_mapper = task.config.get(ConfigConst.component_mapper)
        _subsystem, _part = _component_mapper.get(module_name)

        is_hit = False
        # find in cache. if not find, update cache
        cache_subsystem, cache_part = component_kit.get_cache()
        if _subsystem in cache_subsystem or _part in cache_subsystem:
            is_hit = True
        if not is_hit:
            env_manager = EnvironmentManager()
            for _, manager in env_manager.managers.items():
                if getattr(manager, "devices_list", []):
                    for device in manager.devices_list:
                        component_kit.__setup__(device)
            cache_subsystem, cache_part = component_kit.get_cache()
            if _subsystem in cache_subsystem or _part in cache_subsystem:
                is_hit = True
        if not is_hit:
            LOG.warning("%s are skipped, no suitable component found. "
                        "Require subsystem=%s part=%s, no device match this"
                        % (module_name, _subsystem, _part))

    def max_driver_threads_size(self):
        return Variables.config.get_max_driver_threads()


class TaskListener(ILifeStageListener):
    def __on_event__(self, stage_event: StageEvent):
        from xdevice import Task
        if Task.life_stage_listener:
            data = stage_event.get_data()
            Task.life_stage_listener(data)
