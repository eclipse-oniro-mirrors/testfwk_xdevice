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
from ohos.drivers import *
from ohos.drivers.constants import TIME_OUT

__all__ = ["OHKernelTestDriver"]


LOG = platform_logger("OHKernelTestDriver")


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
            with os.fdopen(device_log_open, "a") as log_file_pipe, \
                    os.fdopen(hilog_open, "a") as hilog_file_pipe:
                self.log_proc, self.hilog_proc = self.config.device.device_log_collector. \
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
