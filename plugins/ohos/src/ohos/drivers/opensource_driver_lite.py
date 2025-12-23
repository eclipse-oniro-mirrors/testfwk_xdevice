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

import os
from xdevice import DeviceLabelType
from ohos.constants import ParserType
from ohos.drivers import *
from ohos.drivers.constants import init_remote_server
from ohos.exception import LiteDeviceExecuteCommandError
from ohos.error import ErrorMessage

__all__ = ["OpenSourceTestDriver"]
LOG = platform_logger("OpenSourceTestDriver")


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.open_source_test)
class OpenSourceTestDriver(IDriver):
    """
    OpenSourceTest is a test that runs a native test package on given
    device lite device.
    """
    config = None
    result = ""
    error_message = ""
    has_param = False

    def __init__(self):
        self.rerun = True
        self.file_name = ""
        self.handler = None

    def __check_environment__(self, device_options):
        if len(device_options) != 1 or \
                device_options[0].label != DeviceLabelType.ipcamera:
            self.error_message = "check environment failed"
            return False
        return True

    def __check_config__(self, config=None):
        pass

    def __execute__(self, request):
        kits = []
        try:
            self.config = request.config
            setattr(self.config, "command_result", "")
            self.config.device = request.config.environment.devices[0]
            init_remote_server(self, request)
            config_file = request.root.source.config_file
            json_config = JsonParser(config_file)
            pre_cmd = get_config_value('pre_cmd', json_config.get_driver(),
                                       False)
            execute_dir = get_config_value('execute', json_config.get_driver(),
                                           False)
            kits = get_kit_instances(json_config,
                                     request.config.resource_path,
                                     request.config.testcases_path)
            for kit in kits:
                if not Binder.is_executing():
                    raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
                copy_list = kit.__setup__(request.config.device,
                                          request=request)

            self.file_name = request.root.source.test_name
            self.set_file_name(request, request.root.source.test_name)
            self.config.device.execute_command_with_timeout(
                command=pre_cmd, timeout=1)
            self.config.device.execute_command_with_timeout(
                command="cd {}".format(execute_dir), timeout=1)
            device_log_file = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
            device_log_file_open = \
                os.open(device_log_file, os.O_WRONLY | os.O_CREAT |
                        os.O_APPEND, FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                for test_bin in copy_list:
                    if not test_bin.endswith(".run-test"):
                        continue
                    if test_bin.startswith("/"):
                        command = ".%s" % test_bin
                    else:
                        command = "./%s" % test_bin
                    self._do_test_run(command, request)
                    file_name.write(self.config.command_result)
                file_name.flush()

        except (LiteDeviceExecuteCommandError, Exception) as exception:
            LOG.error(exception, error_no=getattr(exception, "error_no",
                                                  "00000"))
            self.error_message = exception
        finally:
            LOG.info("-------------finally-----------------")
            # umount the dirs already mount
            for kit in kits:
                kit.__teardown__(request.config.device)
            self.config.device.close()
            report_name = "report" if request.root.source. \
                test_name.startswith("{") else get_filename_extension(
                request.root.source.test_name)[0]
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message,
                report_name)

    def set_file_name(self, request, bin_file):
        self.result = "%s.xml" % os.path.join(
            request.config.report_path, "result", bin_file)

    def run(self, command=None, listener=None, timeout=20):
        parsers = get_plugin(Plugin.PARSER,
                             ParserType.open_source_test)
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suite_name = self.file_name
            parser_instance.test_name = command.replace("./", "")
            parser_instance.listeners = listener
            parser_instances.append(parser_instance)
        self.handler = ShellHandler(parser_instances)
        for _ in range(3):
            result, _, error = self.config.device.execute_command_with_timeout(
                command=command, case_type=DeviceTestType.open_source_test,
                timeout=timeout, receiver=self.handler)
            self.config.command_result = result
            if "pass" in result.lower():
                break
        return error, result, self.handler

    def _do_test_run(self, command, request):
        listeners = request.listeners
        for listener in listeners:
            listener.device_sn = self.config.device.device_sn
        error, _, _ = self.run(command, listeners, timeout=60)
        if error:
            LOG.error(
                "Execute %s failed" % command, error_no="00402")

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""
