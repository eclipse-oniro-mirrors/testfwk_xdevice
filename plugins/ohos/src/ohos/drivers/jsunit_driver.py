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
import time
import json
import stat
from collections import namedtuple

from ohos.drivers import *
from ohos.drivers.constants import get_xml_output
from ohos.drivers.constants import ResultManager
from ohos.environment.dmlib import process_command_ret
from ohos.error import ErrorMessage
from ohos.parser.jsunit_parser import _ACE_LOG_MARKER

__all__ = ["JSUnitTestDriver"]
LOG = platform_logger("JSUnitTestDriver")


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.jsunit_test)
class JSUnitTestDriver(IDriver):
    """
    JSUnitTestDriver is a Test that runs a native test package on given device.
    """

    def __init__(self):
        self.xml_output = "false"
        self.timeout = 30 * 1000
        self.start_time = None
        self.result = ""
        self.error_message = ""
        self.kits = []
        self.config = None
        # log
        self.device_log = None
        self.hilog = None
        self.log_proc = None
        self.hilog_proc = None
        self.ace_log_marker = ""

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            device = request.config.environment.devices[0]
            exe_out = device.execute_shell_command(
                "param get const.product.software.version")
            LOG.debug("Software version is {}".format(exe_out))

            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file

            if not suite_file:
                err_msg = ErrorMessage.Common.Code_0301001.format(request.root.source.source_string)
                LOG.error(err_msg)
                raise ParamError(err_msg)
            LOG.debug("Test case file path: {}".format(suite_file))

            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)

            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)
            command = "target mount"
            self.config.device.connector_command(command)
            do_module_kit_setup(request, self.kits)
            self.run_js_outer(config_file, json_config, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
            raise exception
        finally:
            do_module_kit_teardown(request)
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def generate_console_output(self, request, timeout):
        LOG.info("prepare to read device log, may wait some time")
        message_list = list()
        label_list, suite_info, is_suites_end = self.read_device_log_timeout(
            self.hilog, message_list, timeout)
        if not is_suites_end and self.ace_log_marker:
            message_list.append(self.ace_log_marker + "  [end] run suites end\n")
            LOG.warning("there is no suites end")
        if len(label_list[0]) > 0 and sum(label_list[0]) != 0:
            # the problem happened! when the sum of label list is not zero
            self._insert_suite_end(label_list, message_list)

        result_message = "".join(message_list)
        message_list.clear()
        expect_tests_dict = self._parse_suite_info(suite_info)
        self._analyse_tests(request, result_message, expect_tests_dict)

    def _insert_suite_end(self, label_list, message_list):
        for i in range(len(label_list[0])):
            if label_list[0][i] != 1:  # skipp
                continue
            # check the start label, then peek next position
            if i + 1 == len(label_list[0]):  # next position at the tail
                message_list.insert(-1, self.ace_log_marker + " [suite end]\n")
                LOG.warning("there is no suite end")
                continue
            if label_list[0][i + 1] != 1:  # 0 present the end label
                continue
            message_list.insert(label_list[1][i + 1],
                                self.ace_log_marker + "  [suite end]\n")
            LOG.warning("there is no suite end")
            for j in range(i + 1, len(label_list[1])):
                label_list[1][j] += 1  # move the index to next

    def _analyse_tests(self, request, result_message, expect_tests_dict):
        exclude_list = self._make_exclude_list_file(request)
        exclude_list.extend(self._get_retry_skip_list(expect_tests_dict))
        listener_copy = request.listeners.copy()
        parsers = get_plugin(
            Plugin.PARSER, CommonParserType.jsunit)
        if parsers:
            parsers = parsers[:1]
        for listener in listener_copy:
            listener.device_sn = self.config.device.device_sn
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = request.get_module_name()
            parser_instance.listeners = listener_copy
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        handler.parsers[0].expect_tests_dict = expect_tests_dict
        handler.parsers[0].exclude_list = exclude_list
        process_command_ret(result_message, handler)

    def _get_retry_skip_list(self, expect_tests_dict):
        # do retry skip already pass case
        skip_list = []
        if hasattr(self.config, "history_report_path") and \
                self.config.testargs.get("test"):
            for class_name in expect_tests_dict.keys():
                for test_desc in expect_tests_dict.get(class_name, list()):
                    test = "{}#{}".format(test_desc.class_name, test_desc.test_name)
                    if test not in self.config.testargs.get("test"):
                        skip_list.append(test)
        LOG.debug("Retry skip list: {}, total skip cases: {}".format(skip_list, len(skip_list)))
        return skip_list

    @classmethod
    def _parse_suite_info(cls, suite_info):
        tests_dict = dict()
        test_count = 0
        if suite_info:
            json_str = "".join(suite_info)
            LOG.debug("Suites info: %s" % json_str)
            try:
                suite_dict_list = json.loads(json_str).get("suites", [])
                for suite_dict in suite_dict_list:
                    for class_name, test_name_dict_list in suite_dict.items():
                        tests_dict.update({class_name.strip(): []})
                        for test_name_dict in test_name_dict_list:
                            for test_name in test_name_dict.values():
                                test = TestDescription(class_name.strip(),
                                                       test_name.strip())
                                tests_dict.get(class_name.strip()).append(test)
                                test_count += 1
            except json.decoder.JSONDecodeError as json_error:
                LOG.warning("Suites info is invalid: %s" % json_error)
        LOG.debug("Collect suite count is %s, test count is %s" %
                  (len(tests_dict), test_count))
        return tests_dict

    def read_device_log(self, device_log_file, result_message):
        device_log_file_open = os.open(device_log_file, os.O_RDONLY,
                                       stat.S_IWUSR | stat.S_IRUSR)
        if not result_message:
            result_message = ""
        self.start_time = time.time()
        with os.fdopen(device_log_file_open, "r", encoding='utf-8') \
                as file_read_pipe:
            while True:
                try:
                    data = file_read_pipe.readline()
                    result_message += data
                    report_name = ""
                    if re.match(r'.*\[create report]*', data):
                        _, index = re.match(r'.*\[create report]*', data). \
                            span()
                    if result_message.find("[create report]") != -1 or \
                            int(time.time() - int(self.start_time)) > \
                            self.timeout:
                        break
                except UnicodeError as error:
                    LOG.warning("While read log file: %s" % error)
        return result_message, report_name

    def read_device_log_timeout(self, device_log_file,
                                message_list, timeout):
        LOG.info("The timeout is {} seconds".format(timeout))
        pattern = "^\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}\\.\\d{3}\\s+(\\d+)"
        while time.time() - self.start_time <= timeout:
            with open(device_log_file, "r", encoding='utf-8',
                      errors='ignore') as file_read_pipe:
                pid = ""
                message_list.clear()
                label_list = [[], []]  # [-1, 1 ..] [line1, line2 ..]
                suite_info = []
                while True:
                    try:
                        line = file_read_pipe.readline()
                    except (UnicodeError, EOFError) as error:
                        LOG.warning("While read log file: %s" % error)
                    if not line:
                        time.sleep(5)  # wait for log write to file
                        break
                    if self._is_match_marker(line):
                        if "[suites info]" in line:
                            _, pos = re.match(".+\\[suites info]", line).span()
                            suite_info.append(line[pos:].strip())

                        if "[start] start run suites" in line:  # 发现了任务开始标签
                            pid, is_update = \
                                self._init_suites_start(line, pattern, pid)
                            if is_update:
                                message_list.clear()
                                label_list[0].clear()
                                label_list[1].clear()
                        if not pid or pid not in line:
                            continue
                        message_list.append(line)
                        if "[suite end]" in line:
                            label_list[0].append(-1)
                            label_list[1].append(len(message_list) - 1)
                        if "[suite start]" in line:
                            label_list[0].append(1)
                            label_list[1].append(len(message_list) - 1)
                        if "[end] run suites end" in line:
                            LOG.info("Find the end mark then analysis result")
                            LOG.debug("current JSApp pid= %s" % pid)
                            return label_list, suite_info, True
        else:
            LOG.error("Hjsunit run timeout {}s reached".format(timeout))
            LOG.debug("current JSApp pid= %s" % pid)
            return label_list, suite_info, False

    @classmethod
    def _init_suites_start(cls, line, pattern, pid):
        matcher = re.match(pattern, line.strip())
        if matcher and matcher.group(1):
            pid = matcher.group(1)
            return pid, True
        return pid, False


    def _jsunit_clear(self):
        self.config.device.execute_shell_command(
            "rm -r /%s/%s/%s/%s" % ("data", "local", "tmp", "ajur"))

    def _get_driver_config(self, json_config):
        package = get_config_value('package', json_config.get_driver(), False)
        runner = "ohos.testkit.runner.Runner"

        default_ability = "ohos.testkit.runner.EntryAbility"
        ability_name = get_config_value('abilityName', json_config.
                                        get_driver(), False, default_ability)

        self.xml_output = get_xml_output(self.config, json_config)
        timeout_config = get_config_value('native-test-timeout',
                                          json_config.get_driver(), False)
        #  for historical reasons, this strategy is adopted
        #  priority: native-test-timeout higher than shell-timeout
        if not timeout_config:
            timeout_config = get_config_value('shell-timeout',
                                              json_config.get_driver(), False)
        testcase_timeout = get_config_value(
            'testcase-timeout', json_config.get_driver(), False, 5000)
        if timeout_config:
            self.timeout = int(timeout_config)

        if not package:
            raise ParamError(ErrorMessage.Config.Code_0302002)
        DriverConfig = namedtuple('DriverConfig',
                                  'package ability_name runner testcase_timeout')
        return DriverConfig(package, ability_name, runner, testcase_timeout)

    def run_js_outer(self, config_file, json_config, request):
        try:
            LOG.debug("Start execute xdevice extension JSUnit Test")
            LOG.debug("Outer version about Community")
            # avoid hilog service stuck issue
            self.config.device.connector_command("shell stop_service hilogd",
                                                 timeout=30 * 1000)
            self.config.device.connector_command("shell start_service hilogd",
                                                 timeout=30 * 1000)
            time.sleep(10)

            self.config.device.set_device_report_path(
                request.config.report_path)
            command = "shell hilog -r"
            self.config.device.connector_command(command, timeout=30 * 1000)
            self._run_jsunit_outer(json_config, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
            raise exception
        finally:
            serial = "{}_{}".format(str(self.config.device.__get_serial__()),
                                    time.time_ns())
            log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
            if self.config.device_log.get(ConfigConst.tag_enable) == ConfigConst.device_log_on:
                self.config.device.device_log_collector.start_get_crash_log(
                    log_tar_file_name,
                    module_name=request.get_module_name(),
                    repeat=request.config.repeat,
                    repeat_round=request.get_repeat_round())
            self.config.device.device_log_collector.remove_log_address(self.device_log, self.hilog)
            self.config.device.device_log_collector.stop_catch_device_log(self.log_proc)
            self.config.device.device_log_collector.stop_catch_device_log(self.hilog_proc)

    def _run_jsunit_outer(self, json_config, request):
        package, ability_name = self._get_driver_config_outer(json_config)
        self.hilog = get_device_log_file(
            request.config.report_path,
            request.config.device.__get_serial__(),
            "device_hilog",
            module_name=request.get_module_name(),
            repeat=request.config.repeat,
            repeat_round=request.get_repeat_round())

        hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                             0o755)
        # execute test case

        self.config.device.device_log_collector.add_log_address(None, self.hilog)
        with os.fdopen(hilog_open, "a") as hilog_file_pipe:
            self.log_proc, self.hilog_proc = self.config.device.device_log_collector. \
                start_catch_device_log(hilog_file_pipe=hilog_file_pipe)
        command = "aa start -d 123 -a %s -b %s" \
                  % (ability_name, package)
        result_value = self.config.device.execute_shell_command(command)
        if result_value and "start ability successfully" in \
                str(result_value).lower():
            setattr(self, "start_success", True)
            LOG.info("execute %s's testcase success. result value=%s"
                     % (package, result_value))
        else:
            LOG.info("execute %s's testcase failed. result value=%s"
                     % (package, result_value))
            raise RuntimeError(ErrorMessage.Common.Code_0301010)

        self.start_time = time.time()
        timeout_config = get_config_value('test-timeout',
                                          json_config.get_driver(),
                                          False, 60000)
        timeout = int(timeout_config) / 1000
        self.generate_console_output(request, timeout)

    def _jsunit_clear_outer(self):
        self.config.device.execute_shell_command(
            "rm -r /%s/%s/%s/%s" % ("data", "local", "tmp", "ajur"))

    def _get_driver_config_outer(self, json_config):
        package = get_config_value('package', json_config.get_driver(), False)
        default_ability = "{}.MainAbility".format(package)
        ability_name = get_config_value('abilityName', json_config.
                                        get_driver(), False, default_ability)
        self.xml_output = get_xml_output(self.config, json_config)
        timeout_config = get_config_value('native-test-timeout',
                                          json_config.get_driver(), False)
        if timeout_config:
            self.timeout = int(timeout_config)

        if not package:
            raise ParamError(ErrorMessage.Config.Code_0302002)
        return package, ability_name

    def _make_exclude_list_file(self, request):
        filter_list = []
        if "all-test-file-exclude-filter" in self.config.testargs:
            json_file_list = self.config.testargs.get(
                "all-test-file-exclude-filter")
            self.config.testargs.pop("all-test-file-exclude-filter")
            if not json_file_list:
                LOG.debug("all-test-file-exclude-filter value is empty!")
            else:
                if not os.path.isfile(json_file_list[0]):
                    LOG.warning(
                        " [{}] is not a valid file".format(json_file_list[0]))
                    return []
                file_open = os.open(json_file_list[0], os.O_RDONLY,
                                    stat.S_IWUSR | stat.S_IRUSR)
                with os.fdopen(file_open, "r") as file_handler:
                    json_data = json.load(file_handler)
                exclude_list = json_data.get(
                    DeviceTestType.jsunit_test, [])

                for exclude in exclude_list:
                    if request.get_module_name() not in exclude:
                        continue
                    filter_list.extend(exclude.get(request.get_module_name()))
        return filter_list

    def _is_match_marker(self, line):
        if self.ace_log_marker:
            return line.lower().find(self.ace_log_marker) != -1
        else:
            for mark_str in _ACE_LOG_MARKER:
                if line.lower().find(mark_str) != -1:
                    self.ace_log_marker = mark_str
                    return True
            return False

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""

def _lock_screen(device):
    device.execute_shell_command("svc power stayon false")
    time.sleep(1)

