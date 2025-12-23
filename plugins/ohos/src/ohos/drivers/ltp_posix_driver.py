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

from ohos.drivers import *
from ohos.environment.dmlib import process_command_ret
from ohos.error import ErrorMessage

__all__ = ["LTPPosixTestDriver"]
LOG = platform_logger("LTPPosixTestDriver")


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.ltp_posix_test)
class LTPPosixTestDriver(IDriver):
    def __init__(self):
        self.timeout = 80 * 1000
        self.start_time = None
        self.result = ""
        self.error_message = ""
        self.kits = []
        self.config = None
        self.handler = None
        # log
        self.hilog = None
        self.log_proc = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start execute xdevice extension LTP Posix Test")
            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))
            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file

            if not suite_file:
                raise ParamError(ErrorMessage.Common.Code_0301001.format(request.root.source.source_string))

            LOG.debug("Test case file path: %s" % suite_file)
            # avoid hilog service stuck issue
            self.config.device.connector_command("shell stop_service hilogd",
                                                 timeout=30 * 1000)
            self.config.device.connector_command("shell start_service hilogd",
                                                 timeout=30 * 1000)
            time.sleep(10)

            self.config.device.connector_command("shell hilog -r",
                                                 timeout=30 * 1000)
            self._run_posix(config_file, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=True, error_no="03409")
            raise exception
        finally:
            self.config.device.device_log_collector.remove_log_address(None, self.hilog)
            self.config.device.device_log_collector.stop_catch_device_log(self.log_proc)
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def _run_posix(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)

            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)
            self.config.device.connector_command("target mount")
            test_list = None
            dsts = None
            for kit in self.kits:
                test_list, dsts = kit.__setup__(request.config.device,
                                                request=request)
            # apply the execute permission
            for dst in dsts:
                self.config.device.connector_command(
                    "shell chmod -R 777 {}".format(dst))

            self.hilog = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                "device_hilog",
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())

            hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 0o755)
            self.config.device.device_log_collector.add_log_address(None, self.hilog)
            with os.fdopen(hilog_open, "a") as hilog_file_pipe:
                _, self.log_proc = self.config.device.device_log_collector. \
                    start_catch_device_log(hilog_file_pipe=hilog_file_pipe)
                if hasattr(self.config, "history_report_path") and \
                        self.config.testargs.get("test"):
                    self._do_test_retry(request, self.config.testargs)
                else:
                    self._do_test_run(request, test_list)

        finally:
            do_module_kit_teardown(request)

    def _do_test_retry(self, request, testargs):
        un_pass_list = []
        for test in testargs.get("test"):
            test_item = test.split("#")
            if len(test_item) != 2:
                continue
            un_pass_list.append(test_item[1])
        LOG.debug("un pass list: [{}]".format(un_pass_list))
        self._do_test_run(request, un_pass_list)

    def _do_test_run(self, request, test_list):
        for test_bin in test_list:
            if not test_bin.endswith(".run-test"):
                continue
            listeners = request.listeners
            for listener in listeners:
                listener.device_sn = self.config.device.device_sn
            parsers = get_plugin(Plugin.PARSER,
                                 "OpenSourceTest")
            parser_instances = []
            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suite_name = request.root.source. \
                    test_name
                parser_instance.test_name = test_bin.replace("./", "")
                parser_instance.listeners = listeners
                parser_instances.append(parser_instance)
            self.handler = ShellHandler(parser_instances)
            self.handler.add_process_method(_ltp_output_method)
            result_message = self.config.device.connector_command(
                "shell {}".format(test_bin))
            LOG.info("get result from command {}".
                     format(result_message))
            process_command_ret(result_message, self.handler)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


def _ltp_output_method(handler, output, end_mark="\n"):
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
        return lines

