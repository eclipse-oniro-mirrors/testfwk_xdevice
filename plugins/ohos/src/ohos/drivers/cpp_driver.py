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
import re

from ohos.drivers import *
from ohos.error import ErrorMessage
from ohos.utils import get_ta_class
from ohos.utils import group_list
from ohos.utils import print_not_exist_class
from xdevice import Request

__all__ = ["CppTestDriver"]
LOG = platform_logger("CppTestDriver")
DEFAULT_TEST_PATH = "/data/test/"

FAILED_RUN_TEST_ATTEMPTS = 3
TIME_OUT = 900 * 1000


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.cpp_test)
class CppTestDriver(IDriver):
    """
    CppTestDriver is a Test that runs a native test package on given harmony
    device.
    """

    def __init__(self):
        self.result = ""
        self.error_message = ""
        self.config = None
        self.rerun = True
        self.rerun_all = True
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
            LOG.debug("Start execute xdevice extension CppTest")

            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file
            self.result = "%s.xml" % \
                          os.path.join(request.config.report_path,
                                       "result", request.root.source.test_name)

            self.device_log = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                "device_log",
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())

            self.hilog = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                "device_hilog",
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())

            device_log_open = os.open(self.device_log, os.O_WRONLY | os.O_CREAT |
                                      os.O_APPEND, FilePermission.mode_755)
            hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 FilePermission.mode_755)
            self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
            log_level = self.config.device_log.get(ConfigConst.tag_loglevel, "INFO")
            with os.fdopen(device_log_open, "a") as log_file_pipe, \
                    os.fdopen(hilog_open, "a") as hilog_file_pipe:
                self.log_proc, self.hilog_proc = self.config.device.device_log_collector. \
                    start_catch_device_log(log_file_pipe, hilog_file_pipe, log_level=log_level)
                self._run_cpp_test(config_file, listeners=request.listeners,
                                   request=request)
                log_file_pipe.flush()
                hilog_file_pipe.flush()

        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03404")
            LOG.exception(self.error_message, exc_info=False, error_no="03404")
            raise exception

        finally:
            self.config.device.device_log_collector.remove_log_address(self.device_log, self.hilog)
            self.config.device.device_log_collector.stop_catch_device_log(self.log_proc)
            self.config.device.device_log_collector.stop_catch_device_log(self.hilog_proc)
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message, request=request)

    def _run_cpp_test(self, config_file, listeners=None, request=None):
        try:
            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)

            json_config = JsonParser(config_file)
            kits = get_kit_instances(json_config, self.config.resource_path,
                                     self.config.testcases_path)

            for listener in listeners:
                listener.device_sn = self.config.device.device_sn

            self._get_driver_config(json_config)
            do_module_kit_setup(request, kits)
            self.runner = RemoteCppTestRunner(self.config)
            self.runner.suite_name = request.root.source.test_name

            if hasattr(self.config, "history_report_path") and \
                    self.config.testargs.get("test"):
                self._do_test_retry(listeners, self.config.testargs)
            else:
                gtest_para_parse(self.config.testargs, self.runner, request)
                _cpp_run_test(self, request)

        finally:
            do_module_kit_teardown(request)

    def _do_test_retry(self, listener, testargs):
        for test in testargs.get("test"):
            test_item = test.split("#")
            if len(test_item) != 2:
                continue
            self.runner.add_instrumentation_arg(
                "gtest_filter", "%s.%s" % (test_item[0], test_item[1]))
            self.runner.run(listener)

    def do_test_run(self, listener):
        test_to_run = self.collect_test_to_run()
        LOG.info("Collected test count is: %s" % (len(test_to_run)
                                                  if test_to_run else 0))
        filter_class = self.runner.arg_list.get("class", "")
        if filter_class:
            ta_class = filter_class.replace(".", "#").split(":")
            print_not_exist_class(ta_class, test_to_run)

        if not test_to_run:
            self.runner.run(listener)
        else:
            self._run_with_rerun(listener, test_to_run)

    def collect_test_to_run(self):
        self.runner.add_instrumentation_arg("gtest_list_tests", True)
        run_results = self.runner.dry_run()
        self.runner.remove_instrumentation_arg("gtest_list_tests")
        return run_results

    def _run_tests(self, listener):
        test_tracker = CollectingTestListener()
        listener_copy = listener.copy()
        listener_copy.append(test_tracker)
        self.runner.run(listener_copy)
        test_run = test_tracker.get_current_run_results()
        return test_run

    def _run_with_rerun(self, listener, expected_tests):
        LOG.debug("Ready to run with rerun, expect run: %s"
                  % len(expected_tests))
        test_run = self._run_tests(listener)
        LOG.debug("Run with rerun, has run: %s" % len(test_run)
                  if test_run else 0)
        if len(test_run) < len(expected_tests):
            expected_tests = TestDescription.remove_test(expected_tests,
                                                         test_run)
            if not expected_tests:
                LOG.debug("No tests to re-run, all tests executed at least "
                          "once.")
            if self.rerun_all:
                self._rerun_all(expected_tests, listener)
            else:
                self._rerun_serially(expected_tests, listener)

    def _rerun_all(self, expected_tests, listener):
        tests = []
        for test in expected_tests:
            tests.append("%s.%s" % (test.class_name, test.test_name))
        self.runner.add_instrumentation_arg("gtest_filter", ":".join(tests))
        LOG.debug("Ready to rerun file, expect run: %s" % len(expected_tests))
        test_run = self._run_tests(listener)
        LOG.debug("Rerun file, has run: %s" % len(test_run))
        if len(test_run) < len(expected_tests):
            expected_tests = TestDescription.remove_test(expected_tests,
                                                         test_run)
            if not expected_tests:
                LOG.debug("Rerun textFile success")
            self._rerun_serially(expected_tests, listener)

    def _rerun_serially(self, expected_tests, listener):
        LOG.debug("Rerun serially, expected run: %s" % len(expected_tests))
        for test in expected_tests:
            self.runner.remove_instrumentation_arg("gtest_filter")
            self.runner.add_instrumentation_arg(
                "gtest_filter", "%s.%s" % (test.class_name, test.test_name))
            self.runner.rerun(listener, test)
            self.runner.remove_instrumentation_arg("gtest_filter")

    def _get_driver_config(self, json_config):
        target_test_path = get_config_value('native-test-device-path',
                                            json_config.get_driver(), False)
        if target_test_path:
            self.config.target_test_path = target_test_path
        else:
            self.config.target_test_path = DEFAULT_TEST_PATH

        self.config.module_name = get_config_value(
            'module-name', json_config.get_driver(), False)

        timeout_config = get_config_value('native-test-timeout',
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config)
        else:
            self.config.timeout = TIME_OUT

        rerun = get_config_value('rerun', json_config.get_driver(), False)
        if isinstance(rerun, bool):
            self.rerun = rerun
        elif str(rerun).lower() == "false":
            self.rerun = False
        else:
            self.rerun = True

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class RemoteCppTestRunner:
    def __init__(self, config):
        self.arg_list = {}
        self.suite_name = None
        self.config = config
        self.rerun_attempt = FAILED_RUN_TEST_ATTEMPTS
        # 判断半容器
        self.ohca = check_device_ohca(self.config.device)

    def dry_run(self):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.cpptest_list)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        handler.add_process_method(_cpp_output_method)

        command = "cd %s; chmod +x *; ./%s %s --gtest_color=no" \
                  % (self.config.target_test_path, self.config.module_name,
                     self.get_args_command())
        if self.ohca:
            bin_path = "{}/{}".format(self.config.target_test_path,
                                      self.config.module_name)
            # 半容器的C++用例需要调整权限
            command = "ohsh toybox chown 20000000:20000000 {}; ohsh toybox chmod a+x {}; ohsh {} {}". \
                format(bin_path, bin_path, bin_path, self.get_args_command())

        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)
        return parser_instances[0].tests

    def run(self, listener):
        handler = self._get_shell_handler(listener)
        command = "cd %s; chmod +x *; ./%s %s --gtest_color=no" \
                  % (self.config.target_test_path, self.config.module_name,
                     self.get_args_command())
        if self.ohca:
            bin_path = "{}/{}".format(self.config.target_test_path,
                                      self.config.module_name)
            # 半容器的C++用例需要调整权限
            command = "ohsh toybox chown 20000000:20000000 {}; ohsh toybox chmod a+x {}; ohsh {} {}". \
                format(bin_path, bin_path, bin_path, self.get_args_command())

        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)

    def rerun(self, listener, test):
        if self.rerun_attempt:
            test_tracker = CollectingTestListener()
            listener_copy = listener.copy()
            listener_copy.append(test_tracker)
            handler = self._get_shell_handler(listener_copy)
            try:
                command = "cd %s; chmod +x *; ./%s %s" \
                          % (self.config.target_test_path,
                             self.config.module_name,
                             self.get_args_command())
                if self.ohca:
                    bin_path = "{}/{}".format(self.config.target_test_path,
                                              self.config.module_name)
                    command = "ohsh toybox chmod a+x {}; ohsh {} {}".format(
                        bin_path, bin_path, self.get_args_command())

                self.config.device.execute_shell_command(
                    command, timeout=self.config.timeout, receiver=handler,
                    retry=0)

            except ShellCommandUnresponsiveException as _:
                LOG.debug("Exception: ShellCommandUnresponsiveException")
            finally:
                if not test_tracker.get_current_run_results():
                    LOG.debug("No test case is obtained finally")
                    self.rerun_attempt -= 1
                    handler.parsers[0].mark_test_as_blocked(test)
        else:
            LOG.debug("Not execute and mark as blocked finally")
            handler = self._get_shell_handler(listener)
            handler.parsers[0].mark_test_as_blocked(test)

    def add_instrumentation_arg(self, name, value):
        if not name or not value:
            return
        self.arg_list[name] = value

    def remove_instrumentation_arg(self, name):
        if not name:
            return
        if name in self.arg_list:
            del self.arg_list[name]

    def get_args_command(self):
        args_commands = []
        for key, value in self.arg_list.items():
            if key == "test_args":
                # 跳过拓展的运行参数
                continue
            if key == "gtest_list_tests":
                args_commands.append("--gtest_list_tests")
            elif key == "class":
                args_commands.append(f"--gtest_filter={value}")
            else:
                args_commands.append(f"--{key}={value}")

        pattern = re.compile(r'--(\S+)=\S+')
        # 处理拓展的运行参数
        for test_arg in self.arg_list.get("test_args", []):
            test_arg = str(test_arg).strip()
            result = re.match(pattern, test_arg)
            if not result:
                continue
            cmd_opt = result.group(1)
            # 检查命令参数是否重复
            test_arg_exists = False
            for cmd_str in args_commands:
                if cmd_opt in cmd_str:
                    test_arg_exists = True
            if not test_arg_exists:
                args_commands.append(test_arg)
        return " ".join(args_commands)

    def _get_shell_handler(self, listener):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.cpptest)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suite_name = self.suite_name
            parser_instance.listeners = listener
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        handler.add_process_method(_cpp_output_method)
        return handler


def _cpp_output_method(handler, output, end_mark="\n"):
    content = output
    if handler.unfinished_line:
        content = "".join((handler.unfinished_line, content))
        handler.unfinished_line = ""
    lines = content.split(end_mark)
    if content.endswith(end_mark):
        # get rid of the tail element of this list contains empty str
        return lines[:-1]
    else:
        handler.unfinished_line = lines[-1]
        # not return the tail element of this list contains unfinished str,
        # so we set position -1
        return lines[:-1]


def _cpp_run_test(driver: CppTestDriver, request: Request):
    listeners = request.listeners
    runner = driver.runner
    test_args_from_tf = request.get_tf_test_args()
    if test_args_from_tf:
        runner.add_instrumentation_arg('test_args', test_args_from_tf)

    filter_class = group_list(get_ta_class(driver, request))
    if not filter_class:
        LOG.info('----- run test with no filter class -----')
        driver.do_test_run(listeners)
        return
    LOG.info('----- run test with filter class -----')
    total = len(filter_class)
    for index, ta_class in enumerate(filter_class, 1):
        LOG.info(f'[{index}/{total}] run test with filter class size {len(ta_class)}')
        runner.add_instrumentation_arg('class', ':'.join(ta_class).replace('#', '.'))
        driver.do_test_run(listeners)
        runner.remove_instrumentation_arg('class')
