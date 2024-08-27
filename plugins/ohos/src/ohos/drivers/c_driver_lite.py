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
import re
import time

from xdevice import DeviceLabelType
from xdevice import get_test_component_version
from ohos.drivers import *
from ohos.constants import ComType
from ohos.constants import ParserType
from ohos.constants import CKit
from ohos.drivers.constants import JavaThread
from ohos.error import ErrorMessage
from ohos.exception import LiteDeviceExecuteCommandError
from ohos.testkit.kit_lite import DeployKit
from ohos.testkit.kit_lite import DeployToolKit

__all__ = ["CTestDriver"]
LOG = platform_logger("CTestDriverLite")
TIME_OUT = 90


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.ctest_lite)
class CTestDriver(IDriver):
    """
    CTest is a test that runs a native test package on given lite device.
    """
    config = None
    result = ""
    error_message = ""
    version_cmd = "AT+CSV"

    def __init__(self):
        self.file_name = ""
        self.run_third = False
        self.kit_type = None
        self.auto_deploy = None
        self.json_config = None
        self.jar_file = None
        self.execute_jar_path = None
        self.java_command = None
        self.java_log_file = None
        self.jar_params = None

    def __check_environment__(self, device_options):
        if len(device_options) != 1 or \
                device_options[0].label != DeviceLabelType.wifiiot:
            self.error_message = "check environment failed"
            return False
        return True

    def __check_config__(self, config=None):
        del config
        self.config = None

    def __execute__(self, request):
        try:
            java_thread = None
            self.config = request.config
            self.config.device = request.config.environment.devices[0]
            current_dir = request.config.resource_path if \
                request.config.resource_path else Variables.exec_dir
            if request.root.source.source_file.strip():
                source = os.path.join(current_dir,
                                      request.root.source.source_file.strip())
                self.file_name = os.path.basename(
                    request.root.source.source_file.strip()).split(".")[0]
            else:
                source = request.root.source.source_string.strip()
            self.json_config = JsonParser(source)
            self.jar_file = get_config_value('jar_file', self.json_config.get_driver(), False)
            kit_instances = get_kit_instances(self.json_config,
                                              request.config.resource_path,
                                              request.config.testcases_path)
            for (_, kit_info) in zip(kit_instances, self.json_config.get_kits()):
                self.auto_deploy = kit_info.get("auto_deploy", "")
                self.kit_type = kit_info.get("type", "")
                # 获取执行超时时间
                timeout_config = kit_info.get("timeout", "")
                if timeout_config:
                    self.config.timeout = int(timeout_config) // 1000
                else:
                    self.config.timeout = TIME_OUT

                if self.kit_type == CKit.deploytool:
                    self.run_third = True
            LOG.info("type:{}".format(self.kit_type))
            LOG.info("auto_deploy:{}".format(self.auto_deploy))
            LOG.info("run_third:{}".format(self.run_third))
            if self.run_third:
                LOG.debug("Run ctest third party")
                if self.auto_deploy in ["False", "false"]:
                    LOG.debug("run ctest hcptest")
                    if self.jar_file:
                        self.init_hcp_config(source, request)
                        java_thread = JavaThread(name='JavaThread', log_path=self.java_log_file,
                                                 command=self.java_command,
                                                 execute_jar_path=self.execute_jar_path)
                        java_thread.start()
                        time.sleep(2)
                        self._run_ctest_third_party_hcptest(source=source, request=request, timeout=self.config.timeout)
                    else:
                        self._run_ctest_third_party(source=source, request=request)

                else:
                    LOG.debug("run ctest third upgrade party")
                    self._run_ctest_upgrade_party(source=source,
                                                  request=request)
            else:
                LOG.debug("Run ctest")
                self._run_ctest(source=source, request=request)

        except (LiteDeviceExecuteCommandError, Exception) as exception:
            LOG.error(exception, error_no=getattr(exception, "error_no",
                                                  "00000"))
            self.error_message = exception
        finally:
            report_name = "report" if request.root.source. \
                test_name.startswith("{") else get_filename_extension(
                request.root.source.test_name)[0]
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message,
                report_name)
            if java_thread:
                java_thread.stop()

    def init_hcp_config(self, config_file, request):
        # jar包日志名称
        self.java_log_file = os.path.join(request.config.report_path, Variables.report_vars.log_dir,
                                          self.jar_file.split(".")[0].lower() + '.log')
        LOG.debug("java log file:{}".format(self.java_log_file))
        # jar包路径
        jar_file_path = os.path.join(os.path.dirname(config_file), self.jar_file)
        LOG.debug("jar file path:{}".format(jar_file_path))
        self.execute_jar_path = os.path.dirname(jar_file_path)
        # 获取执行参数
        self.jar_params = get_config_value('jar_params', self.json_config.get_driver(), True)
        jar_params = "\"{}\" {}".format(jar_file_path, "".join(self.jar_params))
        LOG.debug("jar params:{}".format(jar_params))
        self.java_command = "java -jar {}".format(jar_params)
        LOG.debug("jar execute command:{}".format(self.java_command))

    def _run_ctest(self, source=None, request=None, timeout=90):
        parser_instances = []
        parsers = get_plugin(Plugin.PARSER, ParserType.ctest_lite)
        try:
            if not source:
                LOG.error("Error: source don't exist %s." % source,
                          error_no="00101")
                return

            version = get_test_component_version(self.config)

            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suites_name = self.file_name
                parser_instance.product_info.setdefault("Version", version)
                parser_instance.listeners = request.listeners
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)

            reset_cmd = self._reset_device(request, source)
            self.result = "%s.xml" % os.path.join(
                request.config.report_path, "result", self.file_name)
            self.config.device.device.com_dict.get(
                ComType.deploy_com).connect()
            result, _, error = self.config.device.device. \
                execute_command_with_timeout(
                command=reset_cmd, case_type=DeviceTestType.ctest_lite,
                key=ComType.deploy_com, timeout=timeout, receiver=handler)
            device_log_file = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
            device_log_file_open = \
                os.open(device_log_file, os.O_WRONLY | os.O_CREAT |
                        os.O_APPEND, FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                file_name.write("{}{}".format(
                    "\n".join(result.split("\n")[0:-1]), "\n"))
                file_name.flush()
        finally:
            device = self.config.device
            device.device.com_dict.get(ComType.deploy_com).close()
            for parser_instance in parser_instances:
                if hasattr(parser_instance, "product_info"):
                    product_info = parser_instance.product_info
                    device.update_device_props(product_info)

    def _run_ctest_third_party(self, source=None, request=None, timeout=5):
        parser_instances = []
        parsers = get_plugin(Plugin.PARSER, ParserType.ctest_lite)
        try:
            if not source:
                LOG.error("Error: source don't exist %s." % source,
                          error_no="00101")
                return

            version = get_test_component_version(self.config)

            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suites_name = self.file_name
                parser_instance.product_info.setdefault("Version", version)
                parser_instance.listeners = request.listeners
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)

            while True:
                input_burning = input("Please enter 'y' or 'n' "
                                      "after the burning  is complete,"
                                      "enter 'quit' to exit:")
                if input_burning.lower().strip() in ["y", "yes"]:
                    LOG.info("Burning succeeded.")
                    break
                elif input_burning.lower().strip() in ["n", "no"]:
                    LOG.info("Burning failed.")
                elif input_burning.lower().strip() == "quit":
                    break
                else:
                    LOG.info({"The input parameter is incorrect,please"
                              " enter 'y' or 'n' after the burning is "
                              "complete,enter 'quit' to exit."})
            LOG.info("Please press the reset button on the device ")
            time.sleep(5)
            self.result = "%s.xml" % os.path.join(
                request.config.report_path, "result", self.file_name)
            self.config.device.device.com_dict.get(
                ComType.deploy_com).connect()

            LOG.debug("Device com:{}".format(self.config.device.device))
            result, _, error = self.config.device.device. \
                execute_command_with_timeout(
                command=[], case_type=DeviceTestType.ctest_lite,
                key=ComType.deploy_com, timeout=timeout, receiver=handler)
            device_log_file = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
            device_log_file_open = \
                os.open(device_log_file, os.O_WRONLY | os.O_CREAT |
                        os.O_APPEND, FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                file_name.write("{}{}".format(
                    "\n".join(result.split("\n")[0:-1]), "\n"))
                file_name.flush()
        finally:
            self.config.device.device.com_dict.get(
                ComType.deploy_com).close()

    def _run_ctest_third_party_hcptest(self, source=None, request=None, timeout=90):
        result = ""
        LOG.debug("Device com:{}".format(self.config.device.device))
        deploy_com = self.config.device.device.com_dict.get(ComType.deploy_com).connect()
        LOG.info("deploy com:{}".format(deploy_com))
        self.result = "%s.xml" % os.path.join(request.config.report_path, "result", self.file_name)
        parser_instances = []
        parsers = get_plugin(Plugin.PARSER, ParserType.ctest_lite)
        try:
            if not source:
                LOG.error("Error: source don't exist %s." % source,
                          error_no="00101")
                return

            version = get_test_component_version(self.config)
            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suites_name = self.file_name
                parser_instance.product_info.setdefault("Version", version)
                parser_instance.listeners = request.listeners
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)
            # 这里判断是否有重启设备
            start_time = time.time()
            while time.time() - start_time < 60:
                LOG.info("请在1min内重启设备")
                data = deploy_com.readline().decode('gbk', errors='ignore')  # 读取一行数据
                PATTERN = re.compile(r'\x1B(\[([0-9]{1,2}(;[0-9]{1,2})*)?m)*')
                data = PATTERN.sub('', data)
                result = "{}{}".format(result, data)
                if data:
                    LOG.info("重启拿到的数据：{}".format(data))  # 将字节数据转换为字符串并打印出来
                    res, _, error = self.config.device.device. \
                        execute_command_with_timeout(
                        command=[], case_type=DeviceTestType.ctest_lite,
                        key=ComType.deploy_com, timeout=int(timeout))
                    result = "{}{}".format(result, res)
                    handler.__read__(result)
                    handler.__done__()
                    break
                else:
                    LOG.info("用户没有在规定时间内重启设备，任务结束!")
                    break

            device_log_file = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
            device_log_file_open = \
                os.open(device_log_file, os.O_WRONLY | os.O_CREAT |
                        os.O_APPEND, FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                file_name.write("{}{}".format(
                    "\n".join(result.split("\n")[0:-1]), "\n"))
                file_name.flush()
        finally:
            self.config.device.device.com_dict.get(
                ComType.deploy_com).close()

    def _run_ctest_upgrade_party(self, source=None, request=None, time_out=5):
        parser_instances = []
        parsers = get_plugin(Plugin.PARSER, ParserType.ctest_lite)
        try:
            if not source:
                LOG.error("Error: source don't exist {}".format(source),
                          error_no="00101")
                return

            version = get_test_component_version(self.config)

            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suites_name = self.file_name
                parser_instance.product_info.setdefault("Version", version)
                parser_instance.listeners = request.listeners
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)
            result = self._reset_third_device(request, source)
            LOG.info("reset_cmd:{}".format(result))
            self.result = "{}.xml".format(
                os.path.join(request.config.report_path, "result",
                             self.file_name))
            if isinstance(result, list):
                self.config.device.device.com_dict.get(
                    ComType.deploy_com).connect()
                result, _, error = self.config.device.device. \
                    execute_command_with_timeout(
                    command=result, case_type=DeviceTestType.ctest_lite,
                    key=ComType.deploy_com, timeout=90, receiver=handler)
            else:
                handler.__read__(result)
                handler.__done__()

            device_log_file = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
            device_log_file_open = \
                os.open(device_log_file,
                        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                        FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                file_name.write("{}{}".format(
                    "\n".join(result.split("\n")[0:-1]), "\n"))
                file_name.flush()
        finally:
            self.config.device.device.com_dict.get(
                ComType.deploy_com).close()

    def _reset_device(self, request, source):
        json_config = JsonParser(source)
        reset_cmd = []
        kit_instances = get_kit_instances(json_config,
                                          request.config.resource_path,
                                          request.config.testcases_path)
        for (kit_instance, kit_info) in zip(kit_instances,
                                            json_config.get_kits()):
            if not isinstance(kit_instance, DeployKit):
                continue
            if not self.file_name:
                self.file_name = get_config_value(
                    'burn_file', kit_info)[0].split("\\")[-1].split(".")[0]
            reset_cmd = kit_instance.burn_command
            if not Binder.is_executing():
                raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
            kit_instance.__setup__(
                self.config.device)
        reset_cmd = [int(item, 16) for item in reset_cmd]
        return reset_cmd

    def _reset_third_device(self, request, source):
        json_config = JsonParser(source)
        reset_cmd = []
        kit_instances = get_kit_instances(json_config,
                                          request.config.resource_path,
                                          request.config.testcases_path)
        for (kit_instance, kit_info) in zip(kit_instances,
                                            json_config.get_kits()):
            if not isinstance(kit_instance, DeployToolKit):
                continue
            if not self.file_name:
                self.file_name = get_config_value(
                    'burn_file', kit_info)[0].split("\\")[-1].split(".")[0]
            if not Binder.is_executing():
                raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
            reset_cmd = kit_instance.__setup__(
                self.config.device)
        return reset_cmd

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""
