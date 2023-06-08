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
import shutil
import zipfile
import tempfile
import stat
from dataclasses import dataclass

from xdevice import ConfigConst
from xdevice import ParamError
from xdevice import ExecuteTerminate
from xdevice import IDriver
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import get_plugin
from xdevice import JsonParser
from xdevice import ShellHandler
from xdevice import TestDescription
from xdevice import ResourceManager
from xdevice import get_device_log_file
from xdevice import check_result_report
from xdevice import get_kit_instances
from xdevice import get_config_value
from xdevice import do_module_kit_setup
from xdevice import do_module_kit_teardown
from xdevice import DeviceTestType
from xdevice import CommonParserType
from xdevice import FilePermission
from xdevice import CollectingTestListener
from xdevice import ShellCommandUnresponsiveException
from xdevice import HapNotSupportTest
from xdevice import HdcCommandRejectedException
from xdevice import HdcError
from xdevice import DeviceConnectorType
from xdevice import get_filename_extension
from xdevice import junit_para_parse
from xdevice import gtest_para_parse
from xdevice import reset_junit_para
from xdevice import disable_keyguard
from xdevice import unlock_screen
from xdevice import unlock_device
from xdevice import get_cst_time

from ohos.environment.dmlib import process_command_ret
from ohos.environment.dmlib import DisplayOutputReceiver
from ohos.testkit.kit import junit_dex_para_parse
from ohos.parser.parser import _ACE_LOG_MARKER

__all__ = ["CppTestDriver", "DexTestDriver", "HapTestDriver",
           "JSUnitTestDriver", "JUnitTestDriver", "RemoteTestRunner",
           "RemoteDexRunner"]
LOG = platform_logger("Drivers")
DEFAULT_TEST_PATH = "/%s/%s/" % ("data", "test")
ON_DEVICE_TEST_DIR_LOCATION = "/%s/%s/%s/" % ("data", "local", "tmp")

FAILED_RUN_TEST_ATTEMPTS = 3
TIME_OUT = 900 * 1000


def get_xml_output(config, json_config):
    xml_output = config.testargs.get("xml-output")
    if not xml_output:
        if get_config_value('xml-output', json_config.get_driver(), False):
            xml_output = get_config_value('xml-output',
                                          json_config.get_driver(), False)
        else:
            xml_output = "false"
    else:
        xml_output = xml_output[0]
    xml_output = str(xml_output).lower()
    return xml_output


def get_result_savepath(testsuit_path, result_rootpath):
    findkey = "%stests%s" % (os.sep, os.sep)
    filedir, _ = os.path.split(testsuit_path)
    pos = filedir.find(findkey)
    if -1 != pos:
        subpath = filedir[pos + len(findkey):]
        pos1 = subpath.find(os.sep)
        if -1 != pos1:
            subpath = subpath[pos1 + len(os.sep):]
            result_path = os.path.join(result_rootpath, "result", subpath)
        else:
            result_path = os.path.join(result_rootpath, "result")
    else:
        result_path = os.path.join(result_rootpath, "result")

    if not os.path.exists(result_path):
        os.makedirs(result_path)

    LOG.info("Result save path = %s" % result_path)
    return result_path


# all testsuit common Unavailable test result xml
def _create_empty_result_file(filepath, filename, error_message):
    error_message = str(error_message)
    error_message = error_message.replace("\"", "&quot;")
    error_message = error_message.replace("<", "&lt;")
    error_message = error_message.replace(">", "&gt;")
    error_message = error_message.replace("&", "&amp;")
    if filename.endswith(".hap"):
        filename = filename.split(".")[0]
    if not os.path.exists(filepath):
        file_open = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                            FilePermission.mode_755)
        with os.fdopen(file_open, "w") as file_desc:
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime())
            file_desc.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file_desc.write('<testsuites tests="0" failures="0" '
                            'disabled="0" errors="0" timestamp="%s" '
                            'time="0" name="AllTests">\n' % time_stamp)
            file_desc.write(
                '  <testsuite name="%s" tests="0" failures="0" '
                'disabled="0" errors="0" time="0.0" '
                'unavailable="1" message="%s">\n' %
                (filename, error_message))
            file_desc.write('  </testsuite>\n')
            file_desc.write('</testsuites>\n')
            file_desc.flush()
    return


class ResultManager(object):
    def __init__(self, testsuit_path, result_rootpath, device,
                 device_testpath):
        self.testsuite_path = testsuit_path
        self.result_rootpath = result_rootpath
        self.device = device
        self.device_testpath = device_testpath
        self.testsuite_name = os.path.basename(self.testsuite_path)
        self.is_coverage = False

    def set_is_coverage(self, is_coverage):
        self.is_coverage = is_coverage

    def get_test_results(self, error_message=""):
        # Get test result files
        filepath = self.obtain_test_result_file()
        if not os.path.exists(filepath):
            _create_empty_result_file(filepath, self.testsuite_name,
                                      error_message)

        # Get coverage data files
        if self.is_coverage:
            self.obtain_coverage_data()

        return filepath

    def obtain_test_result_file(self):
        result_savepath = get_result_savepath(self.testsuite_path,
                                              self.result_rootpath)
        if self.testsuite_path.endswith('.hap'):
            filepath = os.path.join(result_savepath, "%s.xml" % str(
                self.testsuite_name).split(".")[0])

            remote_result_name = ""
            if self.device.is_file_exist(os.path.join(self.device_testpath,
                                                      "testcase_result.xml")):
                remote_result_name = "testcase_result.xml"
            elif self.device.is_file_exist(os.path.join(self.device_testpath,
                                                        "report.xml")):
                remote_result_name = "report.xml"

            if remote_result_name:
                self.device.pull_file(
                    os.path.join(self.device_testpath, remote_result_name),
                    filepath)
            else:
                LOG.error("%s no report file", self.device_testpath)

        else:
            filepath = os.path.join(result_savepath, "%s.xml" %
                                    self.testsuite_name)
            remote_result_file = os.path.join(self.device_testpath,
                                              "%s.xml" % self.testsuite_name)

            if self.device.is_file_exist(remote_result_file):
                self.device.pull_file(remote_result_file, result_savepath)
            else:
                LOG.error("%s not exists", remote_result_file)
        return filepath

    def is_exist_target_in_device(self, path, target):
        command = "ls -l %s | grep %s" % (path, target)

        check_result = False
        stdout_info = self.device.execute_shell_command(command)
        if stdout_info != "" and stdout_info.find(target) != -1:
            check_result = True
        return check_result

    def obtain_coverage_data(self):
        java_cov_path = os.path.abspath(
            os.path.join(self.result_rootpath, "..", "coverage/data/exec"))
        dst_target_name = "%s.exec" % self.testsuite_name
        src_target_name = "jacoco.exec"
        if self.is_exist_target_in_device(self.device_testpath,
                                          src_target_name):
            if not os.path.exists(java_cov_path):
                os.makedirs(java_cov_path)
            self.device.pull_file(
                os.path.join(self.device_testpath, src_target_name),
                os.path.join(java_cov_path, dst_target_name))

        cxx_cov_path = os.path.abspath(
            os.path.join(self.result_rootpath, "..", "coverage/data/cxx",
                         self.testsuite_name))
        target_name = "obj"
        if self.is_exist_target_in_device(self.device_testpath, target_name):
            if not os.path.exists(cxx_cov_path):
                os.makedirs(cxx_cov_path)
            src_file = os.path.join(self.device_testpath, target_name)
            self.device.pull_file(src_file, cxx_cov_path)


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
                request.config.device.__get_serial__() + "_" + request.
                get_module_name(),
                "device_log")

            self.hilog = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__() + "_" + request.
                get_module_name(),
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
                request.config.report_path, self.result, self.error_message)

    def _run_cpp_test(self, config_file, listeners=None, request=None):
        try:
            if not os.path.exists(config_file):
                LOG.error("Error: Test cases don't exit %s." % config_file,
                          error_no="00102")
                raise ParamError(
                    "Error: Test cases don't exit %s." % config_file,
                    error_no="00102")

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
                self._do_test_run(listeners)

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

    def _do_test_run(self, listener):
        test_to_run = self._collect_test_to_run()
        LOG.info("Collected test count is: %s" % (len(test_to_run)
                 if test_to_run else 0))
        if not test_to_run:
            self.runner.run(listener)
        else:
            self._run_with_rerun(listener, test_to_run)

    def _collect_test_to_run(self):
        if self.rerun:
            self.runner.add_instrumentation_arg("gtest_list_tests", True)
            run_results = self.runner.dry_run()
            self.runner.remove_instrumentation_arg("gtest_list_tests")
            return run_results
        return None

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

    def dry_run(self):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.cpptest_list)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)

        command = "cd %s; chmod +x *; ./%s %s" \
                  % (self.config.target_test_path, self.config.module_name,
                     self.get_args_command())

        self.config.device.execute_shell_command(
            command, timeout=self.config.timeout, receiver=handler, retry=0)
        return parser_instances[0].tests

    def run(self, listener):
        handler = self._get_shell_handler(listener)
        command = "cd %s; chmod +x *; ./%s %s" \
                  % (self.config.target_test_path, self.config.module_name,
                     self.get_args_command())

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

                self.config.device.execute_shell_command(
                    command, timeout=self.config.timeout, receiver=handler,
                    retry=0)

            except ShellCommandUnresponsiveException as _:
                LOG.debug("Exception: ShellCommandUnresponsiveException")
            finally:
                if not len(test_tracker.get_current_run_results()):
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
        args_commands = ""
        for key, value in self.arg_list.items():
            if key == "gtest_list_tests":
                args_commands = "%s --%s" % (args_commands, key)
            else:
                args_commands = "%s --%s=%s" % (args_commands, key, value)
        return args_commands

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
        return handler


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

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):

        device = request.config.environment.devices[0]
        exe_out = device.execute_shell_command(
            "param get const.product.software.version")
        LOG.debug("Software version is {}".format(exe_out))
        self.run_js_outer(request)

    def generate_console_output(self, request, timeout):
        LOG.info("prepare to read device log, may wait some time")
        message_list = list()
        label_list, suite_info, is_suites_end = self.read_device_log_timeout(
            self.hilog, message_list, timeout)
        if not is_suites_end:
            message_list.append(_ACE_LOG_MARKER + ": [end] run suites end\n")
            LOG.warning("there is no suites end")
        if len(label_list[0]) > 0 and sum(label_list[0]) != 0:
            # the problem happened! when the sum of label list is not zero
            self._insert_suite_end(label_list, message_list)

        result_message = "".join(message_list)
        message_list.clear()
        expect_tests_dict = self._parse_suite_info(suite_info)
        self._analyse_tests(request, result_message, expect_tests_dict)

    @classmethod
    def _insert_suite_end(cls, label_list, message_list):
        for i in range(len(label_list[0])):
            if label_list[0][i] != 1:  # skipp
                continue
            # check the start label, then peek next position
            if i + 1 == len(label_list[0]):  # next position at the tail
                message_list.insert(-1, _ACE_LOG_MARKER + ": [suite end]\n")
                LOG.warning("there is no suite end")
                continue
            if label_list[0][i + 1] != 1:  # 0 present the end label
                continue
            message_list.insert(label_list[1][i + 1],
                                _ACE_LOG_MARKER + ": [suite end]\n")
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
        # get already pass case
        skip_list = []
        if hasattr(self.config, "history_report_path") and \
                self.config.testargs.get("test"):
            for class_name in expect_tests_dict.keys():
                for test_desc in expect_tests_dict.get(class_name, list()):
                    test = "{}#{}".format(test_desc.class_name, test_desc.test_name)
                    if test not in self.config.testargs.get("test"):
                        skip_list.append(test)
        LOG.debug("Retry skip list: {}, total skip case: {}".
                  format(skip_list, len(skip_list)))
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
                    except UnicodeError as error:
                        LOG.warning("While read log file: %s" % error)
                    if not line:
                        time.sleep(5)  # wait for log write to file
                        break
                    if line.lower().find(_ACE_LOG_MARKER + ":") != -1:
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

    def run_js_outer(self, request):
        try:
            LOG.debug("Start execute xdevice extension JSUnit Test")
            LOG.debug("Outer version about Community")
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
            # avoid hilog service stuck issue
            self.config.device.connector_command("shell stop_service hilogd",
                                           timeout=30 * 1000)
            self.config.device.connector_command("shell start_service hilogd",
                                           timeout=30 * 1000)
            time.sleep(10)

            self.config.device.set_device_report_path(request.config.report_path)
            self.config.device.connector_command("shell hilog -r", timeout=30 * 1000)
            self._run_jsunit_outer(config_file, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
            raise exception
        finally:
            try:
                serial = "{}_{}".format(str(self.config.device.__get_serial__()), time.time_ns())
                log_tar_file_name = "{}_{}".format(request.get_module_name(),
                                                   str(serial).replace(":", "_"))
                if hasattr(self.config, "device_log") and \
                        self.config.device_log == ConfigConst.device_log_on:
                    self.config.device.device_log_collector.start_get_crash_log(log_tar_file_name)
                self.config.device.device_log_collector.remove_log_address(self.device_log, self.hilog)
                self.config.device.device_log_collector.stop_catch_device_log(self.log_proc)
                self.config.device.device_log_collector.stop_catch_device_log(self.hilog_proc)
            finally:
                do_module_kit_teardown(request)
                self.result = check_result_report(
                    request.config.report_path, self.result, self.error_message)

    def _run_jsunit_outer(self, config_file, request):
        if not os.path.exists(config_file):
            LOG.error("Error: Test cases don't exist %s." % config_file)
            raise ParamError(
                "Error: Test cases don't exist %s." % config_file,
                error_no="00102")

        json_config = JsonParser(config_file)
        self.kits = get_kit_instances(json_config,
                                      self.config.resource_path,
                                      self.config.testcases_path)

        package, ability_name = self._get_driver_config_outer(json_config)
        self.config.device.connector_command("target mount")
        do_module_kit_setup(request, self.kits)

        self.hilog = get_device_log_file(
            request.config.report_path,
            request.config.device.__get_serial__() + "_" + request.
            get_module_name(),
            "device_hilog")

        hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                             0o755)
        self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
        with os.fdopen(hilog_open, "a") as hilog_file_pipe:
            if hasattr(self.config, "device_log") and \
                    self.config.device_log == ConfigConst.device_log_on:
                self.config.device.device_log_collector.clear_crash_log()
            self.log_proc, self.hilog_proc = self.config.device.device_log_collector. \
                start_catch_device_log(hilog_file_pipe=hilog_file_pipe)

        # execute test case
        command = "shell aa start -d 123 -a %s -b %s" \
                  % (ability_name, package)
        result_value = self.config.device.connector_command(command)
        if result_value and "start ability successfully" in \
                str(result_value).lower():
            setattr(self, "start_success", True)
            LOG.info("execute %s's testcase success. result value=%s"
                     % (package, result_value))
        else:
            LOG.info("execute %s's testcase failed. result value=%s"
                     % (package, result_value))
            raise RuntimeError("hjsunit test run error happened!")

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
            raise ParamError("Can't find package in config file.",
                             error_no="03201")
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
                        "[{}] is not a valid file".format(json_file_list[0]))
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

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


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
                raise ParamError(
                    "test source '%s' not exists" %
                    request.root.source.source_string, error_no="00110")

            LOG.debug("Test case file path: %s" % suite_file)
            # avoid hilog service stuck issue
            self.config.device.connector_command("shell stop_service hilogd",
                                           timeout=30 * 1000)
            self.config.device.connector_command("shell start_service hilogd",
                                           timeout=30 * 1000)
            time.sleep(10)

            self.config.device.connector_command("shell hilog -r", timeout=30 * 1000)
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
                LOG.error("Error: Test cases don't exist %s." % config_file)
                raise ParamError(
                    "Error: Test cases don't exist %s." % config_file,
                    error_no="00102")

            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)
            self.config.device.connector_command("target mount")
            test_list = None
            dst = None
            for kit in self.kits:
                test_list, dst = kit.__setup__(request.config.device,
                                               request=request)
            # apply execute right
            self.config.device.connector_command("shell chmod -R 777 {}".format(dst))

            self.hilog = get_device_log_file(
                request.config.report_path,
                request.config.device.__get_serial__() + "_" + request.
                get_module_name(),
                "device_hilog")

            hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                                 0o755)
            self.config.device.device_log_collector.add_log_address(None, self.hilog)
            with os.fdopen(hilog_open, "a") as hilog_file_pipe:
                _, self.log_proc = self.config.device.device_log_collector.\
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
        LOG.debug("LTP Posix un pass list: [{}]".format(un_pass_list))
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


def _lock_screen(device):
    device.execute_shell_command("svc power stayon false")
    time.sleep(1)


def _sleep_according_to_result(result):
    if result:
        time.sleep(1)


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