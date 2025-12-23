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
import stat
from ohos.drivers import *
from ohos.constants import ParserType
from ohos.environment.dmlib_lite import generate_report

__all__ = ["BuildOnlyTestDriver"]
LOG = platform_logger("BuildOnlyTestDriver")


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.build_only_test)
class BuildOnlyTestDriver(IDriver):
    """
    BuildOnlyTest is a test that runs a native test package on given
    device lite device.
    """
    config = None
    result = ""
    error_message = ""

    def __init__(self):
        self.file_name = ""
        self.config_file = None
        self.testcases_path = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        self.config = request.config
        self.config.device = request.config.environment.devices[0]
        self.file_name = request.root.source.test_name
        self.config_file = request.root.source.config_file
        self.testcases_path = request.config.testcases_path
        file_path = self._get_log_file()
        result_list = self._get_result_list(file_path)
        if len(result_list) == 0:
            LOG.error(
                "Error: source don't exist %s." % request.root.source.
                source_file, error_no="00101")
            return
        total_result = ''
        for result in result_list:
            flags = os.O_RDONLY
            modes = stat.S_IWUSR | stat.S_IRUSR
            with os.fdopen(os.open(result, flags, modes), "r",
                           encoding="utf-8") as file_content:
                result = file_content.read()
                if not result.endswith('\n'):
                    result = '%s\n' % result
            total_result = '{}{}'.format(total_result, result)
        parsers = get_plugin(Plugin.PARSER, ParserType.build_only_test)
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suite_name = self.file_name
            parser_instance.listeners = request.listeners
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        generate_report(handler, total_result)

    @classmethod
    def _get_result_list(cls, file_path):
        result_list = list()
        for root_path, _, file_names in os.walk(file_path):
            for file_name in file_names:
                if file_name == "logfile":
                    result_list.append(os.path.join(root_path, file_name))
        return result_list

    def _get_log_file(self):
        json_config = JsonParser(self.config_file)
        log_path = get_config_value('log_path', json_config.get_driver(),
                                    False)
        log_path = str(log_path.replace("/", "", 1)) if log_path.startswith(
            "/") else str(log_path)
        LOG.debug("The log path is:%s" % log_path)
        file_path = get_file_absolute_path(log_path,
                                           paths=[self.testcases_path])
        LOG.debug("The file path is:%s" % file_path)
        return file_path

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""
