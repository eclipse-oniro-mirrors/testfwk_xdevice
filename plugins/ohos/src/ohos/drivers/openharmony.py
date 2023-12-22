#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2022 Huawei Device Co., Ltd.
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

import os
import time
import json
import stat
import shutil
import re
from datetime import datetime
from enum import Enum

from xdevice import ConfigConst
from xdevice import ParamError
from xdevice import IDriver
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import get_plugin
from xdevice import JsonParser
from xdevice import ShellHandler
from xdevice import TestDescription
from xdevice import get_device_log_file
from xdevice import check_result_report
from xdevice import get_kit_instances
from xdevice import get_config_value
from xdevice import do_module_kit_setup
from xdevice import do_module_kit_teardown
from xdevice import DeviceTestType
from xdevice import CommonParserType
from xdevice import FilePermission
from xdevice import ResourceManager
from xdevice import get_file_absolute_path
from xdevice import exec_cmd

from ohos.executor.listener import CollectingPassListener
from ohos.constants import CKit
from ohos.environment.dmlib import process_command_ret

__all__ = ["OHJSUnitTestDriver", "OHKernelTestDriver",
           "OHYaraTestDriver", "oh_jsunit_para_parse"]

TIME_OUT = 300 * 1000

LOG = platform_logger("OpenHarmony")


def oh_jsunit_para_parse(runner, junit_paras):
    junit_paras = dict(junit_paras)
    test_type_list = ["function", "performance", "reliability", "security"]
    size_list = ["small", "medium", "large"]
    level_list = ["0", "1", "2", "3"]
    for para_name in junit_paras.keys():
        para_name = para_name.strip()
        para_values = junit_paras.get(para_name, [])
        if para_name == "class":
            runner.add_arg(para_name, ",".join(para_values))
        elif para_name == "notClass":
            runner.add_arg(para_name, ",".join(para_values))
        elif para_name == "testType":
            if para_values[0] not in test_type_list:
                continue
            # function/performance/reliability/security
            runner.add_arg(para_name, para_values[0])
        elif para_name == "size":
            if para_values[0] not in size_list:
                continue
            # size small/medium/large
            runner.add_arg(para_name, para_values[0])
        elif para_name == "level":
            if para_values[0] not in level_list:
                continue
            # 0/1/2/3/4
            runner.add_arg(para_name, para_values[0])
        elif para_name == "stress":
            runner.add_arg(para_name, para_values[0])


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_kernel_test)
class OHKernelTestDriver(IDriver):
    """
        OpenHarmonyKernelTest
    """
    def __init__(self):
        self.timeout = 30 * 1000
        self.result = ""
        self.error_message = ""
        self.kits = []
        self.config = None
        self.runner = None
        # log
        self.device_log = None
        self.hilog = None
        self.log_proc = None
        self.hilog_proc = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start to Execute OpenHarmony Kernel Test")

            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file

            self.result = "%s.xml" % \
                          os.path.join(request.config.report_path,
                                       "result", request.get_module_name())
            self.device_log = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                "device_log")

            self.hilog = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                "device_hilog")

            device_log_open = os.open(self.device_log, os.O_WRONLY | os.O_CREAT |
                                      os.O_APPEND, FilePermission.mode_755)
            hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 FilePermission.mode_755)
            self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
            with os.fdopen(device_log_open, "a") as log_file_pipe, \
                    os.fdopen(hilog_open, "a") as hilog_file_pipe:
                self.log_proc, self.hilog_proc = self.config.device.device_log_collector.\
                    start_catch_device_log(log_file_pipe, hilog_file_pipe)
                self._run_oh_kernel(config_file, request.listeners, request)
                log_file_pipe.flush()
                hilog_file_pipe.flush()
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
            raise exception
        finally:
            do_module_kit_teardown(request)
            self.config.device.device_log_collector.remove_log_address(self.device_log, self.hilog)
            self.config.device.device_log_collector.stop_catch_device_log(self.log_proc)
            self.config.device.device_log_collector.stop_catch_device_log(self.hilog_proc)
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def _run_oh_kernel(self, config_file, listeners=None, request=None):
        try:
            json_config = JsonParser(config_file)
            kits = get_kit_instances(json_config, self.config.resource_path,
                                     self.config.testcases_path)
            self._get_driver_config(json_config)
            do_module_kit_setup(request, kits)
            self.runner = OHKernelTestRunner(self.config)
            self.runner.suite_name = request.get_module_name()
            self.runner.run(listeners)
        finally:
            do_module_kit_teardown(request)

    def _get_driver_config(self, json_config):
        target_test_path = get_config_value('native-test-device-path',
                                            json_config.get_driver(), False)
        test_suite_name = get_config_value('test-suite-name',
                                           json_config.get_driver(), False)
        test_suites_list = get_config_value('test-suites-list',
                                            json_config.get_driver(), False)
        timeout_limit = get_config_value('timeout-limit',
                                         json_config.get_driver(), False)
        conf_file = get_config_value('conf-file',
                                     json_config.get_driver(), False)
        self.config.arg_list = {}
        if target_test_path:
            self.config.target_test_path = target_test_path
        if test_suite_name:
            self.config.arg_list["test-suite-name"] = test_suite_name
        if test_suites_list:
            self.config.arg_list["test-suites-list"] = test_suites_list
        if timeout_limit:
            self.config.arg_list["timeout-limit"] = timeout_limit
        if conf_file:
            self.config.arg_list["conf-file"] = conf_file
        timeout_config = get_config_value('shell-timeout',
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config)
        else:
            self.config.timeout = TIME_OUT

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class OHKernelTestRunner:
    def __init__(self, config):
        self.suite_name = None
        self.config = config
        self.arg_list = config.arg_list

    def run(self, listeners):
        handler = self._get_shell_handler(listeners)
        # hdc shell cd /data/local/tmp/OH_kernel_test;
        # sh runtest test -t OpenHarmony_RK3568_config
        # -n OpenHarmony_RK3568_skiptest -l 60
        command = "cd %s; chmod +x *; sh runtest test %s" % (
            self.config.target_test_path, self.get_args_command())
        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)

    def _get_shell_handler(self, listeners):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.oh_kernel_test)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = self.suite_name
            parser_instance.listeners = listeners
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        return handler

    def get_args_command(self):
        args_commands = ""
        for key, value in self.arg_list.items():
            if key == "test-suite-name" or key == "test-suites-list":
                args_commands = "%s -t %s" % (args_commands, value)
            elif key == "conf-file":
                args_commands = "%s -n %s" % (args_commands, value)
            elif key == "timeout-limit":
                args_commands = "%s -l %s" % (args_commands, value)
        return args_commands


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_jsunit_test)
class OHJSUnitTestDriver(IDriver):
    """
       OHJSUnitTestDriver is a Test that runs a native test package on
       given device.
    """

    def __init__(self):
        self.timeout = 80 * 1000
        self.start_time = None
        self.result = ""
        self.error_message = ""
        self.kits = []
        self.config = None
        self.runner = None
        self.rerun = True
        self.rerun_all = True
        # log
        self.device_log = None
        self.hilog = None
        self.log_proc = None
        self.hilog_proc = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start execute OpenHarmony JSUnitTest")
            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))
            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file

            if not suite_file:
                raise ParamError(
                    "test source '%s' not exists" %
                    request.root.source.source_string, error_no="00110")
            LOG.debug("Test case file path: %s" % suite_file)
            self.config.device.set_device_report_path(request.config.report_path)
            self.hilog = get_device_log_file(request.config.report_path,
                                        request.config.device.__get_serial__() + "_" + request.
                                        get_module_name(),
                                        "device_hilog")

            hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 0o755)
            self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
            self.config.device.execute_shell_command(command="hilog -r")
            with os.fdopen(hilog_open, "a") as hilog_file_pipe:
                if hasattr(self.config, ConfigConst.device_log) \
                        and self.config.device_log.get(ConfigConst.tag_enable) == ConfigConst.device_log_on \
                        and hasattr(self.config.device, "clear_crash_log"):
                    self.config.device.device_log_collector.clear_crash_log()
                self.log_proc, self.hilog_proc = self.config.device.device_log_collector.\
                    start_catch_device_log(hilog_file_pipe=hilog_file_pipe)
                self._run_oh_jsunit(config_file, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=True, error_no="03409")
            raise exception
        finally:
            try:
                self._handle_logs(request)
            finally:
                self.result = check_result_report(
                    request.config.report_path, self.result, self.error_message)

    def __dry_run_execute__(self, request):
        LOG.debug("Start dry run xdevice JSUnit Test")
        self.config = request.config
        self.config.device = request.config.environment.devices[0]
        config_file = request.root.source.config_file
        suite_file = request.root.source.source_file

        if not suite_file:
            raise ParamError(
                "test source '%s' not exists" %
                request.root.source.source_string, error_no="00110")
        LOG.debug("Test case file path: %s" % suite_file)
        self._dry_run_oh_jsunit(config_file, request)

    def _dry_run_oh_jsunit(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                LOG.error("Error: Test cases don't exist %s." % config_file)
                raise ParamError(
                    "Error: Test cases don't exist %s." % config_file,
                    error_no="00102")
            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)

            self._get_driver_config(json_config)
            self.config.device.connector_command("target mount")
            do_module_kit_setup(request, self.kits)
            self.runner = OHJSUnitTestRunner(self.config)
            self.runner.suites_name = request.get_module_name()
            # execute test case
            self._get_runner_config(json_config)
            oh_jsunit_para_parse(self.runner, self.config.testargs)

            test_to_run = self._collect_test_to_run()
            LOG.info("Collected suite count is: {}, test count is: {}".
                     format(len(self.runner.expect_tests_dict.keys()),
                            len(test_to_run) if test_to_run else 0))
        finally:
            do_module_kit_teardown(request)

    def _run_oh_jsunit(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                LOG.error("Error: Test cases don't exist %s." % config_file)
                raise ParamError(
                    "Error: Test cases don't exist %s." % config_file,
                    error_no="00102")
            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)

            self._get_driver_config(json_config)
            self.config.device.connector_command("target mount")
            self._start_smart_perf()
            do_module_kit_setup(request, self.kits)
            self.runner = OHJSUnitTestRunner(self.config)
            self.runner.suites_name = request.get_module_name()
            self._get_runner_config(json_config)
            if hasattr(self.config, "history_report_path") and \
                    self.config.testargs.get("test"):
                self._do_test_retry(request.listeners, self.config.testargs)
            else:
                if self.rerun:
                    self.runner.retry_times = self.runner.MAX_RETRY_TIMES
                    # execute test case
                self._do_tf_suite()
                self._make_exclude_list_file(request)
                oh_jsunit_para_parse(self.runner, self.config.testargs)
                self._do_test_run(listener=request.listeners)

        finally:
            do_module_kit_teardown(request)

    def _get_driver_config(self, json_config):
        package = get_config_value('package-name',
                                   json_config.get_driver(), False)
        module = get_config_value('module-name',
                                  json_config.get_driver(), False)
        bundle = get_config_value('bundle-name',
                                  json_config. get_driver(), False)
        is_rerun = get_config_value('rerun', json_config.get_driver(), False)

        self.config.package_name = package
        self.config.module_name = module
        self.config.bundle_name = bundle
        self.rerun = True if is_rerun == 'true' else False

        if not package and not module:
            raise ParamError("Neither package nor module is found"
                             " in config file.", error_no="03201")
        timeout_config = get_config_value("shell-timeout",
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config)
        else:
            self.config.timeout = TIME_OUT

    def _get_runner_config(self, json_config):
        test_timeout = get_config_value('test-timeout',
                                        json_config.get_driver(), False)
        if test_timeout:
            self.runner.add_arg("wait_time", int(test_timeout))

        testcase_timeout = get_config_value('testcase-timeout',
                                            json_config.get_driver(), False)
        if testcase_timeout:
            self.runner.add_arg("timeout", int(testcase_timeout))
        self.runner.compile_mode = get_config_value(
            'compile-mode', json_config.get_driver(), False)

    def _do_test_run(self, listener):
        test_to_run = self._collect_test_to_run()
        LOG.info("Collected suite count is: {}, test count is: {}".
                 format(len(self.runner.expect_tests_dict.keys()),
                        len(test_to_run) if test_to_run else 0))
        if not test_to_run or not self.rerun:
            self.runner.run(listener)
            self.runner.notify_finished()
        else:
            self._run_with_rerun(listener, test_to_run)

    def _collect_test_to_run(self):
        run_results = self.runner.dry_run()
        return run_results

    def _run_tests(self, listener):
        test_tracker = CollectingPassListener()
        listener_copy = listener.copy()
        listener_copy.append(test_tracker)
        self.runner.run(listener_copy)
        test_run = test_tracker.get_current_run_results()
        return test_run

    def _run_with_rerun(self, listener, expected_tests):
        LOG.debug("Ready to run with rerun, expect run: %s"
                  % len(expected_tests))
        test_run = self._run_tests(listener)
        self.runner.retry_times -= 1
        LOG.debug("Run with rerun, has run: %s" % len(test_run)
                  if test_run else 0)
        if len(test_run) < len(expected_tests):
            expected_tests = TestDescription.remove_test(expected_tests,
                                                         test_run)
            if not expected_tests:
                LOG.debug("No tests to re-run twice,please check")
                self.runner.notify_finished()
            else:
                self._rerun_twice(expected_tests, listener)
        else:
            LOG.debug("Rerun once success")
            self.runner.notify_finished()

    def _rerun_twice(self, expected_tests, listener):
        tests = []
        for test in expected_tests:
            tests.append("%s#%s" % (test.class_name, test.test_name))
        self.runner.add_arg("class", ",".join(tests))
        LOG.debug("Ready to rerun twice, expect run: %s" % len(expected_tests))
        test_run = self._run_tests(listener)
        self.runner.retry_times -= 1
        LOG.debug("Rerun twice, has run: %s" % len(test_run))
        if len(test_run) < len(expected_tests):
            expected_tests = TestDescription.remove_test(expected_tests,
                                                         test_run)
            if not expected_tests:
                LOG.debug("No tests to re-run third,please check")
                self.runner.notify_finished()
            else:
                self._rerun_third(expected_tests, listener)
        else:
            LOG.debug("Rerun twice success")
            self.runner.notify_finished()

    def _rerun_third(self, expected_tests, listener):
        tests = []
        for test in expected_tests:
            tests.append("%s#%s" % (test.class_name, test.test_name))
        self.runner.add_arg("class", ",".join(tests))
        LOG.debug("Rerun to rerun third, expect run: %s" % len(expected_tests))
        self._run_tests(listener)
        LOG.debug("Rerun third success")
        self.runner.notify_finished()

    def _make_exclude_list_file(self, request):
        if "all-test-file-exclude-filter" in self.config.testargs:
            json_file_list = self.config.testargs.get(
                "all-test-file-exclude-filter")
            self.config.testargs.pop("all-test-file-exclude-filter")
            if not json_file_list:
                LOG.warning("all-test-file-exclude-filter value is empty!")
            else:
                if not os.path.isfile(json_file_list[0]):
                    LOG.warning(
                        "[{}] is not a valid file".format(json_file_list[0]))
                    return
                file_open = os.open(json_file_list[0], os.O_RDONLY,
                                    stat.S_IWUSR | stat.S_IRUSR)
                with os.fdopen(file_open, "r") as file_handler:
                    json_data = json.load(file_handler)
                exclude_list = json_data.get(
                    DeviceTestType.oh_jsunit_test, [])
                filter_list = []
                for exclude in exclude_list:
                    if request.get_module_name() not in exclude:
                        continue
                    filter_list.extend(exclude.get(request.get_module_name()))
                if not isinstance(self.config.testargs, dict):
                    return
                if 'notClass' in self.config.testargs.keys():
                    filter_list.extend(self.config.testargs.get('notClass', []))
                self.config.testargs.update({"notClass": filter_list})

    def _do_test_retry(self, listener, testargs):
        tests_dict = dict()
        case_list = list()
        for test in testargs.get("test"):
            test_item = test.split("#")
            if len(test_item) != 2:
                continue
            case_list.append(test)
            if test_item[0] not in tests_dict:
                tests_dict.update({test_item[0] : []})
            tests_dict.get(test_item[0]).append(
                TestDescription(test_item[0], test_item[1]))
        self.runner.add_arg("class", ",".join(case_list))
        self.runner.expect_tests_dict = tests_dict
        self.config.testargs.pop("test")
        self.runner.run(listener)
        self.runner.notify_finished()

    def _do_tf_suite(self):
        if hasattr(self.config, "tf_suite") and \
                self.config.tf_suite.get("cases", []):
            case_list = self.config["tf_suite"]["cases"]
            self.config.testargs.update({"class": case_list})

    def _start_smart_perf(self):
        if not hasattr(self.config, ConfigConst.kits_in_module):
            return
        if CKit.smartperf not in self.config.get(ConfigConst.kits_in_module):
            return
        sp_kits = get_plugin(Plugin.TEST_KIT, CKit.smartperf)[0]
        sp_kits.target_name = self.config.bundle_name
        param_config = self.config.get(ConfigConst.kits_params).get(
            CKit.smartperf, "")
        sp_kits.__check_config__(param_config)
        self.kits.insert(0, sp_kits)

    def _handle_logs(self, request):
        serial = "{}_{}".format(str(self.config.device.__get_serial__()), time.time_ns())
        log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
        if hasattr(self.config, ConfigConst.device_log) and \
                self.config.device_log.get(ConfigConst.tag_enable) == ConfigConst.device_log_on \
                and hasattr(self.config.device, "start_get_crash_log"):
            self.config.device.device_log_collector.\
                start_get_crash_log(log_tar_file_name, module_name=request.get_module_name())
        self.config.device.device_log_collector.\
            remove_log_address(self.device_log, self.hilog)
        self.config.device.device_log_collector.\
            stop_catch_device_log(self.log_proc)
        self.config.device.device_log_collector.\
            stop_catch_device_log(self.hilog_proc)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class OHJSUnitTestRunner:
    MAX_RETRY_TIMES = 3

    def __init__(self, config):
        self.arg_list = {}
        self.suites_name = None
        self.config = config
        self.rerun_attemp = 3
        self.suite_recorder = {}
        self.finished = False
        self.expect_tests_dict = dict()
        self.finished_observer = None
        self.retry_times = 1
        self.compile_mode = ""

    def dry_run(self):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.oh_jsunit_list)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        command = self._get_dry_run_command()
        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)
        self.expect_tests_dict = parser_instances[0].tests_dict
        return parser_instances[0].tests

    def run(self, listener):
        handler = self._get_shell_handler(listener)
        command = self._get_run_command()
        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)

    def notify_finished(self):
        if self.finished_observer:
            self.finished_observer.notify_task_finished()
        self.retry_times -= 1

    def _get_shell_handler(self, listener):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.oh_jsunit)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = self.suites_name
            parser_instance.listeners = listener
            parser_instance.runner = self
            parser_instances.append(parser_instance)
            self.finished_observer = parser_instance
        handler = ShellHandler(parser_instances)
        return handler

    def add_arg(self, name, value):
        if not name or not value:
            return
        self.arg_list[name] = value

    def remove_arg(self, name):
        if not name:
            return
        if name in self.arg_list:
            del self.arg_list[name]

    def get_args_command(self):
        args_commands = ""
        for key, value in self.arg_list.items():
            if "wait_time" == key:
                args_commands = "%s -w %s " % (args_commands, value)
            else:
                args_commands = "%s -s %s %s " % (args_commands, key, value)
        return args_commands

    def _get_run_command(self):
        command = ""
        if self.config.package_name:
            # aa test -p ${packageName} -b ${bundleName}-s
            # unittest OpenHarmonyTestRunner
            command = "aa test -p {} -b {} -s unittest OpenHarmonyTestRunner" \
                      " {}".format(self.config.package_name,
                                   self.config.bundle_name,
                                   self.get_args_command())
        elif self.config.module_name:
            #  aa test -m ${moduleName}  -b ${bundleName}
            #  -s unittest OpenHarmonyTestRunner
            command = "aa test -m {} -b {} -s unittest {} {}".format(
                self.config.module_name, self.config.bundle_name,
                self.get_oh_test_runner_path(), self.get_args_command())
        return command

    def _get_dry_run_command(self):
        command = ""
        if self.config.package_name:
            command = "aa test -p {} -b {} -s unittest OpenHarmonyTestRunner" \
                      " {} -s dryRun true".format(self.config.package_name,
                                                  self.config.bundle_name,
                                                  self.get_args_command())
        elif self.config.module_name:
            command = "aa test -m {} -b {} -s unittest {}" \
                      " {} -s dryRun true".format(self.config.module_name,
                                                  self.config.bundle_name,
                                                  self.get_oh_test_runner_path(),
                                                  self.get_args_command())

        return command

    def get_oh_test_runner_path(self):
        if self.compile_mode == "esmodule":
            return "/ets/testrunner/OpenHarmonyTestRunner"
        else:
            return "OpenHarmonyTestRunner"


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_rust_test)
class OHRustTestDriver(IDriver):
    def __init__(self):
        self.result = ""
        self.error_message = ""
        self.config = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start to execute open harmony rust test")
            self.config = request.config
            self.config.device = request.config.environment.devices[0]
            self.config.target_test_path = "/system/bin"

            suite_file = request.root.source.source_file
            LOG.debug("Testsuite filepath:{}".format(suite_file))

            if not suite_file:
                LOG.error("test source '{}' not exists".format(
                    request.root.source.source_string))
                return

            self.result = "{}.xml".format(
                os.path.join(request.config.report_path,
                             "result", request.get_module_name()))
            self.config.device.set_device_report_path(request.config.report_path)
            self.config.device.device_log_collector.start_hilog_task()
            self._init_oh_rust()
            self._run_oh_rust(suite_file, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
        finally:
            serial = "{}_{}".format(str(request.config.device.__get_serial__()),
                                    time.time_ns())
            log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
            self.config.device.device_log_collector.stop_hilog_task(
                log_tar_file_name, module_name=request.get_module_name())
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def _init_oh_rust(self):
        self.config.device.connector_command("target mount")
        self.config.device.execute_shell_command(
            "mount -o rw,remount,rw /")

    def _run_oh_rust(self, suite_file, request=None):
        # push testsuite file
        self.config.device.push_file(suite_file, self.config.target_test_path)
        # push resource file
        resource_manager = ResourceManager()
        resource_data_dict, resource_dir = \
            resource_manager.get_resource_data_dic(suite_file)
        resource_manager.process_preparer_data(resource_data_dict,
                                               resource_dir,
                                               self.config.device)
        for listener in request.listeners:
            listener.device_sn = self.config.device.device_sn

        parsers = get_plugin(Plugin.PARSER, CommonParserType.oh_rust)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suite_name = request.get_module_name()
            parser_instance.listeners = request.listeners
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)

        command = "cd {}; chmod +x *; ./{}".format(
            self.config.target_test_path, os.path.basename(suite_file))
        self.config.device.execute_shell_command(
            command, timeout=TIME_OUT, receiver=handler, retry=0)
        resource_manager.process_cleaner_data(resource_data_dict, resource_dir,
                                              self.config.device)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class OHYaraConfig(Enum):
    HAP_FILE = "hap-file"
    BUNDLE_NAME = "bundle-name"
    CLEANUP_APPS = "cleanup-apps"

    OS_FULLNAME_LIST = "osFullNameList"
    VULNERABILITIES = "vulnerabilities"
    VUL_ID = "vul_id"
    OPENHARMONY_SA = "openharmony-sa"
    CVE = "cve"
    AFFECTED_VERSION = "affected_versions"
    MONTH = "month"
    SEVERITY = "severity"
    VUL_DESCRIPTION = "vul_description"
    DISCLOSURE = "disclosure"
    OBJECT_TYPE = "object_type"
    AFFECTED_FILES = "affected_files"
    YARA_RULES = "yara_rules"

    PASS = "pass"
    FAIL = "fail"
    BLOCK = "block"

    ERROR_MSG_001 = "The patch label is longer than two months (60 days), which violates the OHCA agreement."
    ERROR_MSG_002 = "This test case is beyond the patch label scope and does not need to be executed."
    ERROR_MSG_003 = "Modify the code according to the patch requirements: "


class VulItem:
    vul_id = ""
    month = ""
    severity = ""
    vul_description = dict()
    disclosure = dict()
    object_type = ""
    affected_files = ""
    affected_versions = ""
    yara_rules = ""
    trace = ""
    final_risk = OHYaraConfig.PASS.value
    complete = False


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_yara_test)
class OHYaraTestDriver(IDriver):
    def __init__(self):
        self.result = ""
        self.error_message = ""
        self.config = None
        self.tool_hap_info = dict()
        self.security_patch = None
        self.system_version = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start to execute open harmony yara test")
            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))
            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file

            if not suite_file:
                raise ParamError(
                    "test source '%s' not exists" %
                    request.root.source.source_string, error_no="00110")
            LOG.debug("Test case file path: %s" % suite_file)
            self.config.device.set_device_report_path(request.config.report_path)
            self._run_oh_yara(config_file, request)

        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
        finally:
            if self.tool_hap_info.get(OHYaraConfig.CLEANUP_APPS.value):
                cmd = ["uninstall", self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)]
                result = self.config.device.connector_command(cmd)
                LOG.debug("Try uninstall tools hap, bundle name is {}, result is {}".format(
                    self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value), result))

            serial = "{}_{}".format(str(request.config.device.__get_serial__()),
                                    time.time_ns())
            log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
            self.config.device.device_log_collector.stop_hilog_task(
                log_tar_file_name, module_name=request.get_module_name())

            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def _get_driver_config(self, json_config):
        yara_bin = get_config_value('yara-bin',
                                    json_config.get_driver(), False)
        version_mapping_file = get_config_value('version-mapping-file',
                                                json_config.get_driver(), False)
        vul_info_file = get_config_value('vul-info-file',
                                         json_config.get_driver(), False)
        # get absolute file path
        self.config.yara_bin = get_file_absolute_path(yara_bin)
        self.config.version_mapping_file = get_file_absolute_path(version_mapping_file)
        if vul_info_file != "vul_info_patch_label_test":
            self.config.vul_info_file = get_file_absolute_path(vul_info_file, [self.config.testcases_path])

        # get tool hap info
        # default value
        self.tool_hap_info = {
            OHYaraConfig.HAP_FILE.value: "sststool.hap",
            OHYaraConfig.BUNDLE_NAME.value: "com.example.sststool",
            OHYaraConfig.CLEANUP_APPS.value: "true"
        }
        tool_hap_info = get_config_value('tools-hap-info',
                                         json_config.get_driver(), False)
        if tool_hap_info:
            self.tool_hap_info[OHYaraConfig.HAP_FILE.value] = \
                tool_hap_info.get(OHYaraConfig.HAP_FILE.value, "sststool.hap")
            self.tool_hap_info[OHYaraConfig.BUNDLE_NAME.value] = \
                tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value, "com.example.sststool")
            self.tool_hap_info[OHYaraConfig.CLEANUP_APPS.value] = \
                tool_hap_info.get(OHYaraConfig.CLEANUP_APPS.value, "true")

    def _run_oh_yara(self, config_file, request=None):
        message_list = list()

        json_config = JsonParser(config_file)
        self._get_driver_config(json_config)
        # get device info
        self.security_patch = self.config.device.execute_shell_command(
            "param get const.ohos.version.security_patch").strip()
        self.system_version = self.config.device.execute_shell_command(
            "param get const.ohos.fullname").strip()

        if "fail" in self.system_version:
            self._get_full_name_by_tool_hap()
        
        vul_info_file = get_config_value('vul-info-file', json_config.get_driver(), False)
        # Extract patch labels into separate testcase
        if vul_info_file == "vul_info_patch_label_test":
            vul_items = list()
            item = VulItem()
            item.vul_id = "Patch-label-test"
            item.month = "Patch-label-test"

            # security patch verify
            current_date_str = datetime.now().strftime('%Y-%m')
            if self._check_if_expire_or_risk(current_date_str):
                LOG.info("Security patch has expired.")
                item.final_risk = OHYaraConfig.FAIL.value
                item.trace = "{}{}".format(item.trace, OHYaraConfig.ERROR_MSG_001.value)
            else:
                LOG.info("Security patch is shorter than two months.")
                item.final_risk = OHYaraConfig.PASS.value
            item.complete = True
            vul_items.append(item)  
        
        else:
            vul_items = self._get_vul_items()
            # parse version mapping file
            mapping_info = self._do_parse_json(self.config.version_mapping_file)
            os_full_name_list = mapping_info.get(OHYaraConfig.OS_FULLNAME_LIST.value, None)
        
            # check if system version in version mapping list
            vul_version = os_full_name_list.get(self.system_version, None)
            # not in the maintenance scope, skip all case
            if not vul_version and "OpenHarmony" in self.system_version:
                vul_version_list = self.system_version.split("-")[-1].split(".")[:2]
                vul_version_list.append("0")
                vul_version = ".".join(vul_version_list)
            if vul_version is None:
                LOG.debug("The system version is not in the maintenance scope, skip it. "
                          "system versions is {}".format(self.system_version))
            else:
                for _, item in enumerate(vul_items):
                    LOG.debug("Affected files: {}".format(item.affected_files))
                    LOG.debug("Object type: {}".format(item.object_type))
                    for index, affected_file in enumerate(item.affected_files):
                        has_inter = False
                        for i, _ in enumerate(item.affected_versions):
                            if self._check_if_intersection(vul_version, item.affected_versions[i]):
                                has_inter = True
                                break
                        if not has_inter:
                            LOG.debug("Yara rule [{}] affected versions has no intersection "
                                      "in mapping version, skip it. Mapping version is {}, "
                                      "affected versions is {}".format(item.vul_id, vul_version,
                                                                       item.affected_versions))
                            continue
                        local_path = os.path.join(request.config.report_path, OHYaraConfig.AFFECTED_FILES.value,
                                                  request.get_module_name(), item.yara_rules[index].split('.')[0])
                        if not os.path.exists(local_path):
                            os.makedirs(local_path)
                        if item.object_type == "kernel_linux":
                            img_file = "/data/local/tmp/boot_linux.img"
                            package_file = self.kernel_packing(affected_file, img_file)
                            if not package_file:
                                LOG.error("Execute failed. Not found file named {}, "
                                          "please check the input".format(affected_file))
                                item.final_risk = OHYaraConfig.FAIL.value
                                item.trace = "Failed to pack the kernel file."
                                continue
                            self.config.device.pull_file(package_file, local_path)
                            affected_file = os.path.join(local_path, os.path.basename(package_file))
                        else:
                            self.config.device.pull_file(affected_file, local_path)
                            affected_file = os.path.join(local_path, os.path.basename(affected_file))
                        
                        if not os.path.exists(affected_file):
                            LOG.debug("affected file [{}] is not exist, skip it.".format(item.affected_files[index]))
                            item.final_risk = OHYaraConfig.PASS.value
                            continue
                        yara_file = get_file_absolute_path(item.yara_rules[index], [self.config.testcases_path])
                        if item.object_type == "kernel_linux":
                            affected_file_processed = self.file_process_kernel(affected_file, local_path)
                            if not affected_file_processed:
                                item.final_risk = OHYaraConfig.FAIL.value
                                item.trace = "Kernel file extraction error"
                                continue
                            cmd = [self.config.yara_bin, yara_file, affected_file_processed]
                        else:
                            cmd = [self.config.yara_bin, yara_file, affected_file]
                        result = exec_cmd(cmd)
                        LOG.debug("Yara result: {}, affected file: {}".format(result, item.affected_files[index]))
                        if "testcase pass" in result:
                            item.final_risk = OHYaraConfig.PASS.value
                            break
                        else:
                            if self._check_if_expire_or_risk(item.month, check_risk=True):
                                item.final_risk = OHYaraConfig.FAIL.value
                                item.trace = "{}{}".format(OHYaraConfig.ERROR_MSG_003.value,
                                                           item.disclosure.get("zh", ""))
                            else:
                                item.final_risk = OHYaraConfig.BLOCK.value
                                item.trace = "{}{}".format(item.trace, OHYaraConfig.ERROR_MSG_002.value)
                        # if no risk delete files, if rule has risk keep it
                        if item.final_risk != OHYaraConfig.FAIL.value:
                            local_path = os.path.join(request.config.report_path, OHYaraConfig.AFFECTED_FILES.value,
                                                      request.get_module_name(), item.yara_rules[index].split('.')[0])
                            if os.path.exists(local_path):
                                LOG.debug(
                                    "Yara rule [{}] has no risk, remove affected files.".format(
                                        item.yara_rules[index]))
                                shutil.rmtree(local_path)
                    item.complete = True
        self._generate_yara_report(request, vul_items, message_list)
        self._generate_xml_report(request, vul_items, message_list)

    def _check_if_expire_or_risk(self, date_str, expire_time=2, check_risk=False):
        from dateutil.relativedelta import relativedelta
        self.security_patch = self.security_patch.replace(' ', '')
        self.security_patch = self.security_patch.replace('/', '-')
        # get current date
        source_date = datetime.strptime(date_str, '%Y-%m')
        security_patch_date = datetime.strptime(self.security_patch[:-3], '%Y-%m')
        # check if expire 2 months
        rd = relativedelta(source_date, security_patch_date)
        months = rd.months + (rd.years * 12)
        if check_risk:
            # vul time before security patch time no risk
            LOG.debug("Security patch time: {}, vul time: {}, delta_months: {}"
                      .format(self.security_patch[:-3], date_str, months))
            if months > 0:
                return False
            else:
                return True
        else:
            # check if security patch time expire current time 2 months
            LOG.debug("Security patch time: {}, current time: {}, delta_months: {}"
                      .format(self.security_patch[:-3], date_str, months))
            if months > expire_time:
                return True
            else:
                return False

    @staticmethod
    def _check_if_intersection(source_version, dst_version):
        # para dst_less_sor control if dst less than source
        def _do_check(soruce, dst, dst_less_sor=True):
            if re.match(r'^\d{1,3}.\d{1,3}.\d{1,3}', soruce) and \
                    re.match(r'^\d{1,3}.\d{1,3}.\d{1,3}', dst):
                source_vers = soruce.split(".")
                dst_vers = dst.split(".")
                for index, _ in enumerate(source_vers):
                    if dst_less_sor:
                        # check if all source number less than dst number
                        if int(source_vers[index]) < int(dst_vers[index]):
                            return False
                    else:
                        # check if all source number larger than dst number
                        if int(source_vers[index]) > int(dst_vers[index]):
                            return False
                return True
            return False

        source_groups = source_version.split("-")
        dst_groups = dst_version.split("-")
        if source_version == dst_version:
            return True
        elif len(source_groups) == 1 and len(dst_groups) == 1:
            return source_version == dst_version
        elif len(source_groups) == 1 and len(dst_groups) == 2:
            return _do_check(source_groups[0], dst_groups[0]) and \
                   _do_check(source_groups[0], dst_groups[1], dst_less_sor=False)
        elif len(source_groups) == 2 and len(dst_groups) == 1:
            return _do_check(source_groups[0], dst_groups[0], dst_less_sor=False) and \
                   _do_check(source_groups[1], dst_groups[0])
        elif len(source_groups) == 2 and len(dst_groups) == 2:
            return _do_check(source_groups[0], dst_groups[1], dst_less_sor=False) and \
                   _do_check(source_groups[1], dst_groups[0])
        return False

    def kernel_packing(self, affected_file, img_file):
        cmd_result = self.config.device.execute_shell_command(f"ls -al {affected_file}").strip()
        LOG.debug("kernel file detail: {}".format(cmd_result))
        if "No such file or directory" in cmd_result:
            return False
        link_file = cmd_result.split(" ")[-1]
        pack_result = self.config.device.execute_shell_command(f"dd if={link_file} of={img_file}")
        LOG.debug("kernel package detail: {}".format(pack_result))
        if "No such file or directory" in pack_result:
            return False
        return img_file
    
    def file_process_kernel(self, affected_file, local_path):
        try:
            from vmlinux_to_elf.elf_symbolizer import ElfSymbolizer
            from vmlinux_to_elf.architecture_detecter import ArchitectureGuessError
            from vmlinux_to_elf.vmlinuz_decompressor import obtain_raw_kernel_from_file
        except ImportError:
            LOG.error("Please install the tool of vmlinux_to_elf before running.")
            return False
        
        # 内核文件解析慢，解析过一次放到公共目录下，该月份下用例共用
        dir_path = os.path.dirname(local_path)
        processed_file = os.path.join(dir_path, "vmlinux.elf")
        if os.path.exists(processed_file):
            LOG.debug("The kernel file has been extracted, will reuse the previous pasing file.")
            return processed_file
        # 1 解压
        try:
            exec_cmd("7z")
        except NameError:
            LOG.error("Please install the command of 7z before running.")
            return False
        decompress_result = exec_cmd(f"7z x {affected_file} -o{local_path}")
        LOG.debug("kernel file decompress detail: {}".format(decompress_result))
        # 2 解析
        print("Kernel file extraction will take a few minutes, please wait patiently...")
        input_file = os.path.join(local_path, "extlinux", "Image")
        output_file = processed_file
        if not input_file:
            LOG.error("An error occurred when decompressing the kernel file.")
            return False
        with open(input_file, "rb") as kernel_bin:
            try:
                ElfSymbolizer(obtain_raw_kernel_from_file(kernel_bin.read()), output_file)
            except ArchitectureGuessError:
                LOG.error("An error occurred when pasing the kernel file.")
                return None
        return output_file

    def _get_vul_items(self):
        vul_items = list()
        vul_info = self._do_parse_json(self.config.vul_info_file)
        vulnerabilities = vul_info.get(OHYaraConfig.VULNERABILITIES.value, [])
        for _, vul in enumerate(vulnerabilities):
            affected_versions = vul.get(OHYaraConfig.AFFECTED_VERSION.value, [])
            item = VulItem()
            item.vul_id = vul.get(OHYaraConfig.VUL_ID.value, dict()).get(OHYaraConfig.CVE.value, "")
            item.affected_versions = affected_versions
            item.month = vul.get(OHYaraConfig.MONTH.value, "")
            item.severity = vul.get(OHYaraConfig.SEVERITY.value, "")
            item.vul_description = vul.get(OHYaraConfig.VUL_DESCRIPTION.value, "")
            item.disclosure = vul.get(OHYaraConfig.DISCLOSURE.value, "")
            item.object_type = vul.get(OHYaraConfig.OBJECT_TYPE.value, "")
            item.affected_files = \
                vul["affected_device"]["standard"]["linux"]["arm"]["scan_strategy"]["ists"]["yara"].get(
                    OHYaraConfig.AFFECTED_FILES.value, [])
            item.yara_rules = \
                vul["affected_device"]["standard"]["linux"]["arm"]["scan_strategy"]["ists"]["yara"].get(
                    OHYaraConfig.YARA_RULES.value, [])
            vul_items.append(item)
        LOG.debug("Vul size is {}".format(len(vul_items)))
        return vul_items

    @staticmethod
    def _do_parse_json(file_path):
        json_content = None
        if not os.path.exists(file_path):
            raise ParamError("The json file {} does not exist".format(
                file_path), error_no="00110")
        flags = os.O_RDONLY
        modes = stat.S_IWUSR | stat.S_IRUSR
        with os.fdopen(os.open(file_path, flags, modes),
                       "r", encoding="utf-8") as file_content:
            json_content = json.load(file_content)
        if json_content is None:
            raise ParamError("The json file {} parse error".format(
                file_path), error_no="00110")
        return json_content

    def _get_full_name_by_tool_hap(self):
        # check if tool hap has installed
        result = self.config.device.execute_shell_command(
            "bm dump -a | grep {}".format(self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        LOG.debug(result)
        if self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value) not in result:
            hap_path = get_file_absolute_path(self.tool_hap_info.get(OHYaraConfig.HAP_FILE.value))
            self.config.device.push_file(hap_path, "/data/local/tmp")
            result = self.config.device.execute_shell_command(
                "bm install -p /data/local/tmp/{}".format(os.path.basename(hap_path)))
            LOG.debug(result)
            self.config.device.execute_shell_command(
                "mkdir -p /data/app/el2/100/base/{}/haps/entry/files".format(
                    self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        self.config.device.execute_shell_command(
            "aa start -a {}.MainAbility -b {}".format(
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value),
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        time.sleep(1)
        self.system_version = self.config.device.execute_shell_command(
            "cat /data/app/el2/100/base/{}/haps/entry/files/osFullNameInfo.txt".format(
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value))).replace('"', '')
        LOG.debug(self.system_version)

    def _generate_yara_report(self, request, vul_items, result_message):
        import csv
        result_message.clear()
        yara_report = os.path.join(request.config.report_path, "vul_info_{}.csv"
                                   .format(request.config.device.device_sn))
        if os.path.exists(yara_report):
            data = []
        else:
            data = [
                ["设备版本号:", self.system_version, "设备安全补丁标签:", self.security_patch],
                ["漏洞编号", "严重程度", "披露时间", "检测结果", "修复建议", "漏洞描述"]
            ]
        fd = os.open(yara_report, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o755)
        for _, item in enumerate(vul_items):
            data.append([item.vul_id, item.severity,
                         item.month, item.final_risk,
                         item.disclosure.get("zh", ""), item.vul_description.get("zh", "")])
            result = "{}|{}|{}|{}|{}|{}|{}\n".format(
                item.vul_id, item.severity,
                item.month, item.final_risk,
                item.disclosure.get("zh", ""), item.vul_description.get("zh", ""),
                item.trace)
            result_message.append(result)
        with os.fdopen(fd, "a", newline='') as file_handler:
            writer = csv.writer(file_handler)
            writer.writerows(data)

    def _generate_xml_report(self, request, vul_items, message_list):
        result_message = "".join(message_list)
        listener_copy = request.listeners.copy()
        parsers = get_plugin(
            Plugin.PARSER, CommonParserType.oh_yara)
        if parsers:
            parsers = parsers[:1]
        for listener in listener_copy:
            listener.device_sn = self.config.device.device_sn
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = request.get_module_name()
            parser_instance.vul_items = vul_items
            parser_instance.listeners = listener_copy
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        process_command_ret(result_message, handler)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""

    @Plugin(type=Plugin.DRIVER, id=DeviceTestType.validator_test)
    class ValidatorTestDriver(IDriver):

        def __init__(self):
            self.error_message = ""
            self.xml_path = ""
            self.result = ""
            self.config = None
            self.kits = []

        def __check_environment__(self, device_options):
            pass

        def __check_config__(self, config):
            pass

        def __execute__(self, request):
            try:
                self.result = os.path.join(
                    request.config.report_path, "result",
                    ".".join((request.get_module_name(), "xml")))
                self.config = request.config
                self.config.device = request.config.environment.devices[0]
                config_file = request.root.source.config_file
                self._run_validate_test(config_file, request)
            except Exception as exception:
                self.error_message = exception
                if not getattr(exception, "error_no", ""):
                    setattr(exception, "error_no", "03409")
                LOG.exception(self.error_message, exc_info=True, error_no="03409")
                raise exception
            finally:
                self.result = check_result_report(request.config.report_path,
                                                  self.result, self.error_message)

        def _run_validate_test(self, config_file, request):
            is_update = False
            try:
                if "update" in self.config.testargs.keys():
                    if dict(self.config.testargs).get("update")[0] == "true":
                        is_update = True
                json_config = JsonParser(config_file)
                self.kits = get_kit_instances(json_config, self.config.resource_path,
                                              self.config.testcases_path)
                self._get_driver_config(json_config)
                if is_update:
                    do_module_kit_setup(request, self.kits)
                while True:
                    print("Is test finished?Y/N")
                    usr_input = input(">>>")
                    if usr_input == "Y" or usr_input == "y":
                        LOG.debug("Finish current test")
                        break
                    else:
                        print("continue")
                        LOG.debug("Your input is:{}, continue".format(usr_input))
                if self.xml_path:
                    result_dir = os.path.join(request.config.report_path, "result")
                    if not os.path.exists(result_dir):
                        os.makedirs(result_dir)
                    self.config.device.pull_file(self.xml_path, self.result)
            finally:
                if is_update:
                    do_module_kit_teardown(request)

        def _get_driver_config(self, json_config):
            self.xml_path = get_config_value("xml_path", json_config.get_driver(), False)
        def __result__(self):
            return self.result if os.path.exists(self.result) else ""
