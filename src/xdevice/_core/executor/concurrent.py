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

import copy
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait

from _core.constants import ModeType
from _core.constants import ConfigConst
from _core.constants import ReportConst
from _core.error import ErrorMessage
from _core.executor.request import Request
from _core.logger import platform_logger
from _core.logger import redirect_driver_log_begin
from _core.logger import redirect_driver_log_end
from _core.plugin import Config
from _core.plugin import get_plugin
from _core.plugin import Plugin
from _core.utils import calculate_elapsed_time
from _core.utils import check_mode
from _core.utils import get_file_absolute_path
from _core.utils import get_kit_instances
from _core.utils import check_device_name
from _core.utils import check_device_env_index
from _core.utils import get_repeat_round
from _core.exception import ParamError
from _core.exception import ExecuteTerminate
from _core.exception import DeviceError
from _core.exception import LiteDeviceError
from _core.report.reporter_helper import ReportConstant
from _core.report.reporter_helper import DataHelper
from _core.report.reporter_helper import Suite
from _core.report.reporter_helper import Case
from _core.context.center import Context
from _core.context.handler import handle_repeat_result
from _core.context.handler import update_report_xml
from _core.context.upload import Uploader
from _core.testkit.json_parser import JsonParser

LOG = platform_logger("Concurrent")


class Concurrent:
    @classmethod
    def executor_callback(cls, worker):
        worker_exception = worker.exception()
        if worker_exception:
            LOG.error("Worker return exception: {}".format(worker_exception))

    @classmethod
    def concurrent_execute(cls, func, params_list, max_size=8):
        """
        Provider the ability to execute target function concurrently
        :param func: target function name
        :param params_list: the list of params in these target functions
        :param max_size:  the max size of thread  you wanted  in thread pool
        :return:
        """
        with ThreadPoolExecutor(max_size) as executor:
            future_params = dict()
            for params in params_list:
                future = executor.submit(func, *params)
                future_params.update({future: params})
                future.add_done_callback(cls.executor_callback)
            wait(future_params)  # wait all function complete
            result_list = []
            for future in future_params:
                result_list.append((future.result(), future_params[future]))
            return result_list


class DriversThread(threading.Thread):
    def __init__(self, test_driver, task, environment, message_queue):
        super().__init__()
        self.test_driver = test_driver
        self.listeners = None
        self.task = task
        self.environment = environment
        self.message_queue = message_queue
        self.error_message = ""
        self.module_config_kits = None
        self.repeat = 1
        self.repeat_round = 1
        self.start_time = time.time()

    def set_listeners(self, listeners):
        self.listeners = listeners
        if self.environment is None:
            return

        for listener in listeners:
            listener.device_sn = self.environment.devices[0].device_sn

    def get_driver_log_file(self, test):
        self.repeat = Context.get_scheduler().get_repeat_index()
        self.repeat_round = get_repeat_round(test.unique_id)
        round_folder = f"round{self.repeat_round}" if self.repeat > 1 else ""
        log_file = os.path.join(
            self.task.config.log_path, round_folder,
            test.source.module_name, ReportConstant.module_run_log)
        return log_file

    def run(self):
        driver, test = None, None
        if self.test_driver and Context.is_executing():
            driver, test = self.test_driver
        if driver is None or test is None:
            return
        redirect_driver_log_begin(self.ident, self.get_driver_log_file(test))
        LOG.debug("Thread %s start" % self.name)
        execute_message = ExecuteMessage('', self.environment, self.test_driver, self.name)
        try:
            # construct params
            driver_request = self._get_driver_request(test, execute_message)
            if driver_request is None:
                return
            # setup device
            self._do_task_setup(driver_request)
            # driver execute
            self.reset_device(driver_request.config)
            driver.__execute__(driver_request)
        except Exception as exception:
            error_no = getattr(exception, "error_no", "00000")
            if self.environment is None:
                LOG.exception("Exception: %s", exception, exc_info=False,
                              error_no=error_no)
            else:
                LOG.exception(
                    "Device: %s, exception: %s" % (
                        self.environment.__get_serial__(), exception),
                    exc_info=False, error_no=error_no)
            self.error_message = str(exception)

        finally:
            self._do_commom_module_kit_teardown()
            self._handle_finally(driver, test, execute_message)
        redirect_driver_log_end(self.ident)

    @staticmethod
    def reset_device(config):
        if getattr(config, "reboot_per_module", False):
            for device in config.environment.devices:
                device.reboot()

    def _handle_finally(self, driver, test, execute_message):
        source_content = test.source.source_file or test.source.source_string
        end_time = time.time()
        LOG.info("Executed: %s, Execution Time: %s" % (
            source_content, calculate_elapsed_time(self.start_time, end_time)))

        # inherit history report under retry mode
        if driver and test:
            execute_result = driver.__result__()
            # move result file to round folder when repeat > 1
            if self.repeat > 1:
                execute_result = handle_repeat_result(
                    execute_result, self.task.config.report_path,
                    round_folder=f"round{self.repeat_round}")
            LOG.debug("Execute result: %s" % execute_result)

            # update result xml
            update_props = {
                ReportConstant.start_time: time.strftime(
                    ReportConstant.time_format, time.localtime(int(self.start_time))),
                ReportConstant.end_time: time.strftime(
                    ReportConstant.time_format, time.localtime(int(end_time))),
                ReportConstant.repeat: str(self.repeat),
                ReportConstant.round: str(self.repeat_round),
                ReportConstant.test_type: test.source.test_type
            }
            if self.environment is not None:
                update_props.update({ReportConstant.devices: self.environment.get_description()})
            update_report_xml(execute_result, update_props)

            if getattr(self.task.config, "history_report_path", ""):
                execute_result = self._inherit_execute_result(execute_result, test)
            execute_message.set_result(execute_result)

        # set execute state
        if self.error_message:
            execute_message.set_state(ExecuteMessage.DEVICE_ERROR)
        else:
            execute_message.set_state(ExecuteMessage.DEVICE_FINISH)

        # free environment
        if self.environment:
            LOG.debug("Thread %s free environment", execute_message.get_thread_name())
            Context.get_scheduler().__free_environment__(execute_message.get_environment())

        LOG.debug("Thread %s put result", self.name)
        self.message_queue.put(execute_message)
        LOG.info("Thread %s end", self.name)

    def _do_common_module_kit_setup(self, driver_request):
        for device in self.environment.devices:
            setattr(device, ConfigConst.common_module_kits, [])

        for kit in self.module_config_kits:
            run_flag = False
            for device in self.environment.devices:
                if not Context.is_executing():
                    raise ExecuteTerminate()
                if not check_device_env_index(device, kit):
                    continue
                if check_device_name(device, kit):
                    run_flag = True
                    kit_copy = copy.deepcopy(kit)
                    module_kits = getattr(device, ConfigConst.common_module_kits)
                    module_kits.append(kit_copy)
                    kit_copy.__setup__(device, request=driver_request)
            if not run_flag:
                err_msg = ErrorMessage.Common.Code_0101004.format(kit.__class__.__name__)
                LOG.error(err_msg)
                raise ParamError(err_msg)

    def _do_commom_module_kit_teardown(self):
        try:
            for device in self.environment.devices:
                for kit in getattr(device, ConfigConst.common_module_kits, []):
                    if check_device_name(device, kit, step="teardown"):
                        kit.__teardown__(device)
                setattr(device, ConfigConst.common_module_kits, [])
        except Exception as e:
            LOG.error("common module kit teardown error: {}".format(e))

    def _do_task_setup(self, driver_request):
        if check_mode(ModeType.decc) or getattr(
                driver_request.config, ConfigConst.check_device, False):
            return

        if self.environment is None:
            return

        if (hasattr(driver_request.config, ConfigConst.module_config) and
                getattr(driver_request.config, ConfigConst.module_config, None)):
            module_config_path = getattr(driver_request.config, ConfigConst.module_config, None)
            LOG.debug("Common module config path: {}".format(module_config_path))
            from xdevice import Variables
            config_path = get_file_absolute_path(module_config_path,
                                                 [os.path.join(Variables.exec_dir, "config")])
            json_config = JsonParser(config_path)
            self.module_config_kits = get_kit_instances(json_config,
                                                        driver_request.config.resource_path,
                                                        driver_request.config.testcases_path)
            self._do_common_module_kit_setup(driver_request)

        for device in self.environment.devices:
            if not getattr(device, ConfigConst.need_kit_setup, True):
                LOG.debug("Device %s need kit setup is false" % device)
                continue

            # do task setup for device
            kits_copy = copy.deepcopy(self.task.config.kits)
            setattr(device, ConfigConst.task_kits, kits_copy)
            for kit in getattr(device, ConfigConst.task_kits, []):
                if not Context.is_executing():
                    break
                try:
                    kit.__setup__(device, request=driver_request)
                except (ParamError, ExecuteTerminate, DeviceError,
                        LiteDeviceError, ValueError, TypeError,
                        SyntaxError, AttributeError) as exception:
                    error_no = getattr(exception, "error_no", "00000")
                    LOG.exception(
                        "Task setup device: %s, exception: %s" % (
                            self.environment.__get_serial__(),
                            exception), exc_info=False, error_no=error_no)
            LOG.debug("Set device %s need kit setup to false" % device)
            setattr(device, ConfigConst.need_kit_setup, False)

        # set product_info to self.task
        if getattr(driver_request, ConfigConst.product_info, "") and not \
                getattr(self.task, ConfigConst.product_info, ""):
            product_info = getattr(driver_request, ConfigConst.product_info)
            if not isinstance(product_info, dict):
                LOG.warning("Product info should be dict, %s",
                            product_info)
                return
            setattr(self.task, ConfigConst.product_info, product_info)

    def _get_driver_request(self, root_desc, execute_message):
        config = Config()
        config.update(copy.deepcopy(self.task.config).__dict__)
        config.environment = self.environment
        if getattr(config, "history_report_path", ""):
            # modify config.testargs
            history_report_path = getattr(config, "history_report_path", "")
            module_name = root_desc.source.module_name
            unpassed_test_params = self._get_unpassed_test_params(
                history_report_path, module_name)
            if not unpassed_test_params:
                LOG.info("%s all test cases are passed, no need retry", module_name)
                driver_request = Request(self.name, root_desc, self.listeners, config)
                execute_message.set_request(driver_request)
                return None
            if unpassed_test_params[0] != module_name and \
                    unpassed_test_params[0] != str(module_name).split(".")[0]:
                test_args = getattr(config, "testargs", {})
                test_params = []
                for unpassed_test_param in unpassed_test_params:
                    if unpassed_test_param not in test_params:
                        test_params.append(unpassed_test_param)
                test_args["test"] = test_params
                if "class" in test_args.keys():
                    test_args.pop("class")
                setattr(config, "testargs", test_args)
        if getattr(config, "tf_suite", ""):
            if root_desc.source.module_name in config.tf_suite.keys():
                config.tf_suite = config.tf_suite.get(
                    root_desc.source.module_name)
            else:
                config.tf_suite = dict()
        for listener in self.listeners:
            LOG.debug("Thread %s, listener %s" % (self.name, listener))
        driver_request = Request(self.name, root_desc, self.listeners, config)
        execute_message.set_request(driver_request)
        return driver_request

    @classmethod
    def _get_unpassed_test_params(cls, history_report_path, module_name):
        unpassed_test_params = []
        from _core.report.result_reporter import ResultReporter
        params = ResultReporter.get_task_info_params(history_report_path)
        if not params:
            return unpassed_test_params
        failed_list = []
        try:
            from devicetest.agent.decc import Handler
            if Handler.DAV.retry_select:
                for i in Handler.DAV.case_id_list:
                    failed_list.append(i + "#" + i)
            else:
                failed_list = params[ReportConst.unsuccessful_params].get(module_name, [])
        except Exception:
            failed_list = params[ReportConst.unsuccessful_params].get(module_name, [])
        if not failed_list:
            failed_list = params[ReportConst.unsuccessful_params].get(str(module_name).split(".")[0], [])
        unpassed_test_params.extend(failed_list)
        LOG.debug("Get unpassed test params %s", unpassed_test_params)
        return unpassed_test_params

    @classmethod
    def _append_unpassed_test_param(cls, history_report_file, unpassed_test_params):
        testsuites_element = DataHelper.parse_data_report(history_report_file)
        for testsuite_element in testsuites_element:
            suite_name = testsuite_element.get("name", "")
            suite = Suite()
            suite.set_cases(testsuite_element)
            for case in suite.cases:
                if case.is_passed():
                    continue
                unpassed_test_param = "{}#{}#{}".format(
                    suite_name, case.classname, case.name)
                unpassed_test_params.append(unpassed_test_param)

    def _inherit_execute_result(self, execute_result, root_desc):
        module_name = root_desc.source.module_name
        execute_result_name = "%s.xml" % module_name
        history_execute_result = self._get_history_execute_result(
            execute_result_name)
        if not history_execute_result:
            LOG.warning("%s no history execute result exists",
                        execute_result_name)
            return execute_result

        if not check_mode(ModeType.decc):
            if not os.path.exists(execute_result):
                result_dir = \
                    os.path.join(self.task.config.report_path, "result")
                os.makedirs(result_dir, exist_ok=True)
                target_execute_result = os.path.join(result_dir,
                                                     execute_result_name)
                shutil.copyfile(history_execute_result, target_execute_result)
                LOG.info("Copy %s to %s" % (history_execute_result,
                                            target_execute_result))
                return target_execute_result

        real_execute_result = self._get_real_execute_result(execute_result)

        # inherit history execute result
        testsuites_element = DataHelper.parse_data_report(real_execute_result)
        if self._is_empty_report(testsuites_element):
            if check_mode(ModeType.decc):
                LOG.info("Empty report no need to inherit history execute"
                         " result")
            else:
                LOG.info("Empty report '%s' no need to inherit history execute"
                         " result", history_execute_result)
            return execute_result

        real_history_execute_result = self._get_real_history_execute_result(
            history_execute_result, module_name)

        history_testsuites_element = DataHelper.parse_data_report(
            real_history_execute_result)
        if self._is_empty_report(history_testsuites_element):
            LOG.info("History report '%s' is empty", history_execute_result)
            return execute_result
        if check_mode(ModeType.decc):
            LOG.info("Inherit history execute result")
        else:
            LOG.info("Inherit history execute result: %s",
                     history_execute_result)
        self._inherit_element(history_testsuites_element, testsuites_element)

        if check_mode(ModeType.decc):
            from xdevice import SuiteReporter
            SuiteReporter.append_report_result(
                (execute_result, DataHelper.to_string(testsuites_element)))
        else:
            # generate inherit execute result
            DataHelper.generate_report(testsuites_element, execute_result)
        return execute_result

    def _inherit_element(self, history_testsuites_element, testsuites_element):
        for history_testsuite_element in history_testsuites_element:
            history_testsuite_name = history_testsuite_element.get("name", "")
            target_testsuite_element = None
            for testsuite_element in testsuites_element:
                if history_testsuite_name == testsuite_element.get("name", ""):
                    target_testsuite_element = testsuite_element
                    break

            if target_testsuite_element is None:
                testsuites_element.append(history_testsuite_element)
                inherited_test = int(testsuites_element.get(
                    ReportConstant.tests, 0)) + int(
                    history_testsuite_element.get(ReportConstant.tests, 0))
                testsuites_element.set(ReportConstant.tests,
                                       str(inherited_test))
                continue

            pass_num = 0
            for history_testcase_element in history_testsuite_element:
                if self._check_testcase_pass(history_testcase_element):
                    target_testsuite_element.append(history_testcase_element)
                    pass_num += 1

            inherited_test = int(target_testsuite_element.get(
                ReportConstant.tests, 0)) + pass_num
            target_testsuite_element.set(ReportConstant.tests,
                                         str(inherited_test))
            inherited_test = int(testsuites_element.get(
                ReportConstant.tests, 0)) + pass_num
            testsuites_element.set(ReportConstant.tests, str(inherited_test))

    def _get_history_execute_result(self, execute_result_name):
        if execute_result_name.endswith(".xml"):
            execute_result_name = execute_result_name[:-4]
        history_execute_result = \
            self._get_data_report_from_record(execute_result_name)
        if history_execute_result:
            return history_execute_result
        for root_dir, _, files in os.walk(
                self.task.config.history_report_path):
            for result_file in files:
                if result_file.endswith(execute_result_name):
                    history_execute_result = os.path.abspath(
                        os.path.join(root_dir, result_file))
        return history_execute_result

    @classmethod
    def _check_testcase_pass(cls, history_testcase_element):
        case = Case()
        case.result = history_testcase_element.get(ReportConstant.result, "")
        case.status = history_testcase_element.get(ReportConstant.status, "")
        case.message = history_testcase_element.get(ReportConstant.message, "")
        if len(history_testcase_element) > 0:
            if not case.result:
                case.result = ReportConstant.false
            case.message = history_testcase_element[0].get(
                ReportConstant.message)

        return case.is_passed()

    @classmethod
    def _is_empty_report(cls, testsuites_element):
        if len(testsuites_element) < 1:
            return True
        if len(testsuites_element) >= 2:
            return False

        if int(testsuites_element[0].get(ReportConstant.unavailable, 0)) > 0:
            return True
        return False

    def _get_data_report_from_record(self, execute_result_name):
        history_report_path = \
            getattr(self.task.config, "history_report_path", "")
        if history_report_path:
            from _core.report.result_reporter import ResultReporter
            params = ResultReporter.get_task_info_params(history_report_path)
            if params:
                report_data_dict = dict(params[ReportConst.data_reports])
                if execute_result_name in report_data_dict.keys():
                    return report_data_dict.get(execute_result_name)
                elif execute_result_name.split(".")[0] in \
                        report_data_dict.keys():
                    return report_data_dict.get(
                        execute_result_name.split(".")[0])
        return ""

    @classmethod
    def _get_real_execute_result(cls, execute_result):
        from xdevice import SuiteReporter
        LOG.debug("Get real execute result length is: %s" %
                  len(SuiteReporter.get_report_result()))
        if check_mode(ModeType.decc):
            for suite_report, report_result in \
                    SuiteReporter.get_report_result():
                if os.path.splitext(suite_report)[0] == \
                        os.path.splitext(execute_result)[0]:
                    return report_result
            return ""
        else:
            return execute_result

    @classmethod
    def _get_real_history_execute_result(cls, history_execute_result,
                                         module_name):
        from xdevice import SuiteReporter
        LOG.debug("Get real history execute result: %s" %
                  SuiteReporter.history_report_result)
        if check_mode(ModeType.decc):
            virtual_report_path, report_result = SuiteReporter. \
                get_history_result_by_module(module_name)
            return report_result
        else:
            return history_execute_result


class DriversDryRunThread(threading.Thread):
    def __init__(self, test_driver, task, environment, message_queue):
        super().__init__()
        self.test_driver = test_driver
        self.listeners = None
        self.task = task
        self.environment = environment
        self.message_queue = message_queue
        self.error_message = ""

    def run(self):
        LOG.debug("Thread %s start" % self.name)
        start_time = time.time()
        execute_message = ExecuteMessage('', self.environment, self.test_driver, self.name)
        driver, test = None, None
        try:
            if self.test_driver and Context.is_executing():
                # construct params
                driver, test = self.test_driver
                driver_request = self._get_driver_request(test,
                                                          execute_message)
                if driver_request is None:
                    return

                # setup device
                self._do_task_setup(driver_request)

                # driver execute
                self.reset_device(driver_request.config)
                driver.__dry_run_execute__(driver_request)

        except Exception as exception:
            error_no = getattr(exception, "error_no", "00000")
            if self.environment is None:
                LOG.exception("Exception: %s", exception, exc_info=False,
                              error_no=error_no)
            else:
                LOG.exception(
                    "Device: %s, exception: %s" % (
                        self.environment.__get_serial__(), exception),
                    exc_info=False, error_no=error_no)
            self.error_message = str(exception)

        finally:
            self._handle_finally(driver, execute_message, start_time, test)

    @staticmethod
    def reset_device(config):
        if getattr(config, "reboot_per_module", False):
            for device in config.environment.devices:
                device.reboot()

    def _handle_finally(self, driver, execute_message, start_time, test):
        source_content = (self.test_driver[1].source.source_file
                          or self.test_driver[1].source.source_string)
        LOG.info("Executed: %s, Execution Time: %s" % (
            source_content, calculate_elapsed_time(start_time, time.time())))

        # set execute state
        if self.error_message:
            execute_message.set_state(ExecuteMessage.DEVICE_ERROR)
        else:
            execute_message.set_state(ExecuteMessage.DEVICE_FINISH)

        # free environment
        if self.environment:
            LOG.debug("Thread %s free environment", execute_message.get_thread_name())
            Context.get_scheduler().__free_environment__(execute_message.get_environment())

        LOG.debug("Thread %s put result", self.name)
        self.message_queue.put(execute_message)

    def _do_task_setup(self, driver_request):
        if check_mode(ModeType.decc) or getattr(
                driver_request.config, ConfigConst.check_device, False):
            return

        if self.environment is None:
            return

        for device in self.environment.devices:
            if not getattr(device, ConfigConst.need_kit_setup, True):
                LOG.debug("Device %s need kit setup is false" % device)
                continue

            # do task setup for device
            kits_copy = copy.deepcopy(self.task.config.kits)
            setattr(device, ConfigConst.task_kits, kits_copy)
            for kit in getattr(device, ConfigConst.task_kits, []):
                if not Context.is_executing():
                    break
                try:
                    kit.__setup__(device, request=driver_request)
                except (ParamError, ExecuteTerminate, DeviceError,
                        LiteDeviceError, ValueError, TypeError,
                        SyntaxError, AttributeError) as exception:
                    error_no = getattr(exception, "error_no", "00000")
                    LOG.exception(
                        "Task setup device: %s, exception: %s" % (
                            self.environment.__get_serial__(),
                            exception), exc_info=False, error_no=error_no)
            LOG.debug("Set device %s need kit setup to false" % device)
            setattr(device, ConfigConst.need_kit_setup, False)

        # set product_info to self.task
        if getattr(driver_request, ConfigConst.product_info, "") and not \
                getattr(self.task, ConfigConst.product_info, ""):
            product_info = getattr(driver_request, ConfigConst.product_info)
            if not isinstance(product_info, dict):
                LOG.warning("Product info should be dict, %s",
                            product_info)
                return
            setattr(self.task, ConfigConst.product_info, product_info)

    def _get_driver_request(self, root_desc, execute_message):
        config = Config()
        config.update(copy.deepcopy(self.task.config).__dict__)
        config.environment = self.environment
        if self.listeners:
            for listener in self.listeners:
                LOG.debug("Thread %s, listener %s" % (self.name, listener))
        driver_request = Request(self.name, root_desc, self.listeners, config)
        execute_message.set_request(driver_request)
        return driver_request


class QueueMonitorThread(threading.Thread):

    def __init__(self, message_queue, current_driver_threads, test_drivers):
        super().__init__()
        self.message_queue = message_queue
        self.current_driver_threads = current_driver_threads
        self.test_drivers = test_drivers

    def check_current_thread_status(self):
        for tid_key in self.current_driver_threads.keys():
            if self.current_driver_threads[tid_key].is_alive():
                LOG.debug("Running thread is alive, thread is {}.".format(tid_key))
            else:
                # if error need free thread environment
                LOG.debug("Running thread is dead, thread is {}".format(tid_key))

    def run(self):
        LOG.debug("Queue monitor thread start")
        while self.test_drivers or self.current_driver_threads:
            if not self.current_driver_threads:
                time.sleep(3)
                continue
            execute_message = self.message_queue.get()

            self.current_driver_threads.pop(execute_message.get_thread_name())

            if execute_message.get_state() == ExecuteMessage.DEVICE_FINISH:
                LOG.debug("Thread %s execute finished" % execute_message.get_thread_name())
            elif execute_message.get_state() == ExecuteMessage.DEVICE_ERROR:
                LOG.debug("Thread %s execute error" % execute_message.get_thread_name())
            Uploader.upload_module_result(execute_message)

        LOG.debug("Queue monitor thread end")
        if not Context.is_executing():
            LOG.info("Terminate success")
            Context.get_scheduler().terminate_result.put("terminate success")


class ExecuteMessage:
    DEVICE_RUN = 'device_run'
    DEVICE_FINISH = 'device_finish'
    DEVICE_ERROR = 'device_error'

    def __init__(self, state, environment, drivers, thread_name):
        self.state = state
        self.environment = environment
        self.drivers = drivers
        self.thread_name = thread_name
        self.request = None
        self.result = None

    def set_state(self, state):
        self.state = state

    def get_state(self):
        return self.state

    def set_request(self, request):
        self.request = request

    def get_request(self):
        return self.request

    def set_result(self, result):
        self.result = result

    def get_result(self):
        return self.result

    def get_environment(self):
        return self.environment

    def get_thread_name(self):
        return self.thread_name

    def get_drivers(self):
        return self.drivers


class ModuleThread(DriversThread):

    def __init__(self, test_driver, task, environment, message_queue, lock):
        super().__init__(test_driver, task, environment, message_queue)
        self.lock = lock

    def run(self):
        driver, test = None, None
        if self.test_driver and Context.is_executing():
            driver, test = self.test_driver
        if driver is None or test is None:
            return
        redirect_driver_log_begin(self.ident, self.get_driver_log_file(test))
        LOG.debug("Thread %s start" % self.name)
        execute_message = ExecuteMessage('', self.environment, self.test_driver, self.name)
        driver, test = None, None
        try:
            # construct params
            driver, test = self.test_driver
            driver_request = self._get_driver_request(test,
                                                      execute_message)
            if driver_request is None:
                return

            # setup device
            self._do_task_setup(driver_request)

            # do common kit setup
            self._do_common_kit_setup(self.environment, self.task, self.test_driver)

            # driver execute
            self.reset_device(driver_request.config)
            driver.__execute__(driver_request)
        except Exception as exception:
            error_no = getattr(exception, "error_no", "00000")
            if self.environment is None:
                LOG.exception("Exception: %s", exception, exc_info=False,
                              error_no=error_no)
            else:
                LOG.exception(
                    "Device: %s, exception: %s" % (
                        self.environment.__get_serial__(), exception),
                    exc_info=False, error_no=error_no)
            self.error_message = str(exception)

        finally:
            # do common kit teardown
            self.__do_common_kit_teardown()
            self._handle_finally(driver, test, execute_message)
        redirect_driver_log_end(self.ident)

    def _do_common_kit_setup(self, environment, task, test_driver):
        LOG.info("Do common setup kit")
        common_kits = task.root.common_kits
        module_subsystem = test_driver[1].source.module_subsystem
        try:
            LOG.info("lock acquire")
            self.lock.acquire()
            task.root.task_list.update({module_subsystem: task.root.task_list.get(module_subsystem) - 1})
        except Exception as e:
            LOG.error(e)
        finally:
            self.lock.release()
            LOG.info("lock release")
        kits = common_kits.get(module_subsystem, None)
        if kits:
            new_kits = self.get_kit_instances(kits, task.config.resource_path, task.config.testcases_path)
            LOG.info(new_kits)
            for device in environment.devices:
                if not getattr(device, "current_subsystem_kit", None):
                    setattr(device, "current_subsystem_kit", module_subsystem)
                    setattr(device, "common_kits", new_kits)
                    self.__do_common_kit_setup(device)
                elif getattr(device, "current_subsystem_kit") != module_subsystem:
                    self.__do_common_kit_teardown()
                    setattr(device, "current_subsystem_kit", module_subsystem)
                    setattr(device, "common_kits", new_kits)
                    self.__do_common_kit_setup(device)

    def __do_common_kit_teardown(self):
        for device in self.environment.devices:
            module_subsystem = getattr(device, "current_subsystem_kit", None)
            if module_subsystem:
                try:
                    LOG.info("lock acquire")
                    self.lock.acquire()
                    LOG.info(self.task.root.task_list.get(module_subsystem))
                    if self.task.root.task_list.get(module_subsystem) <= 0:
                        LOG.info("do common kit teardown")
                        for kit in getattr(device, ConfigConst.common_kits, []):
                            kit.__teardown__(device)
                        setattr(device, ConfigConst.common_kits, [])
                        setattr(device, "current_subsystem_kit", None)
                except Exception as e:
                    LOG.error(e)
                finally:
                    self.lock.release()
                    LOG.info("lock release")

    @staticmethod
    def __do_common_kit_setup(device):
        for kit in getattr(device, ConfigConst.common_kits, []):
            if not Context.is_executing():
                raise ExecuteTerminate()
            kit.__setup__(device, request=None)

    @staticmethod
    def get_kit_instances(kits, resource_path, testcases_path):
        # get kit instances
        kit_instances = []
        for kit in kits:
            kit["paths"] = [resource_path, testcases_path]
            kit_type = kit.get("type", "")
            device_name = kit.get("device_name", None)
            if get_plugin(plugin_type=Plugin.TEST_KIT, plugin_id=kit_type):
                test_kit = \
                    get_plugin(plugin_type=Plugin.TEST_KIT, plugin_id=kit_type)[0]
                test_kit_instance = test_kit.__class__()
                test_kit_instance.__check_config__(kit)
                setattr(test_kit_instance, "device_name", device_name)
                kit_instances.append(test_kit_instance)
            else:
                raise ParamError(ErrorMessage.Common.Code_0101003.format(kit_type))
        return kit_instances
