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
import shutil
import glob
import time
import stat
from xdevice import DataHelper
from xdevice import DeviceLabelType
from xdevice import GTestConst
from xdevice import SuiteReporter
from ohos.drivers import *
from ohos.constants import ParserType
from ohos.constants import DeviceLiteKernel
from ohos.drivers.constants import get_nfs_server
from ohos.drivers.constants import init_remote_server
from ohos.error import ErrorMessage
from ohos.exception import LiteDeviceError
from ohos.executor.listener import CollectingLiteGTestListener


__all__ = ["CppTestDriver"]
LOG = platform_logger("CppTestDriverLite")
FAILED_RUN_TEST_ATTEMPTS = 2
CPP_TEST_MOUNT_STOP_SIGN = "not mount properly, Test Stop"
CPP_TEST_NFS_SIGN = "execve: I/O error"


def get_testcases(testcases_list):
    cases_list = []
    for test in testcases_list:
        test_item = test.split("#")
        if len(test_item) == 1:
            cases_list.append(test)
        elif len(test_item) == 2:
            cases_list.append(test_item[-1])
    return cases_list


def sort_by_length(file_name):
    return len(file_name)


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.cpp_test_lite)
class CppTestDriver(IDriver):
    """
    CppTest is a test that runs a native test package on given lite device.
    """
    config = None
    result = ""
    error_message = ""

    def __init__(self):
        self.rerun = True
        self.file_name = ""
        self.execute_bin = ""

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
        device_log_file = get_device_log_file(
            request.config.report_path,
            request.get_devices()[0].__get_serial__(),
            repeat=request.config.repeat,
            repeat_round=request.get_repeat_round())
        try:
            self.config = request.config
            self.init_cpp_config()
            self.config.device = request.config.environment.devices[0]
            init_remote_server(self, request=request)
            config_file = request.root.source.config_file
            json_config = JsonParser(config_file)
            self._get_driver_config(json_config)

            bin_file = get_config_value('execute', json_config.get_driver(),
                                        False)
            kits = get_kit_instances(json_config,
                                     request.config.resource_path,
                                     request.config.testcases_path)
            for kit in kits:
                if not Binder.is_executing():
                    raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
                kit.__setup__(request.config.device, request=request)

            command = self._get_execute_command(bin_file)

            self.set_file_name(request, command)

            if self.config.xml_output:
                self.delete_device_xml(request, self.config.device_xml_path)
            if os.path.exists(self.result):
                os.remove(self.result)
            if request.config.testargs.get("dry_run"):
                self.config.dry_run = request.config.testargs.get(
                    "dry_run")[0].lower()
                self.dry_run(command, request.listeners)
            else:
                self.run_cpp_test(command, request)
                self.generate_device_xml(request, self.execute_bin)

        except (LiteDeviceError, Exception) as exception:
            LOG.exception(exception, exc_info=False)
            self.error_message = exception
        finally:
            device_log_file_open = os.open(device_log_file, os.O_WRONLY |
                                           os.O_CREAT | os.O_APPEND,
                                           FilePermission.mode_755)
            with os.fdopen(device_log_file_open, "a") as file_name:
                file_name.write(self.config.command_result)
                file_name.flush()
            LOG.info("-------------finally-----------------")
            self._after_command(kits, request)
        self.result = check_result_report(
            request.config.report_path, self.result, self.error_message, request=request)

    def _get_execute_command(self, bin_file):
        if self.config.device.get("device_kernel") == \
                DeviceLiteKernel.linux_kernel:
            execute_dir = "/storage" + "/".join(bin_file.split("/")[0:-1])
        else:
            execute_dir = "/".join(bin_file.split("/")[0:-1])
        self.execute_bin = bin_file.split("/")[-1]

        self.config.device.execute_command_with_timeout(
            command="cd {}".format(execute_dir), timeout=1)
        self.config.execute_bin_path = execute_dir

        if self.execute_bin.startswith("/"):
            command = ".%s" % self.execute_bin
        else:
            command = "./%s" % self.execute_bin

        report_path = "/%s/%s/" % ("reports", self.execute_bin.split(".")[0])
        self.config.device_xml_path = (self.linux_directory + report_path). \
            replace("//", "/")
        self.config.device_report_path = execute_dir + report_path

        return command

    def _get_driver_config(self, json_config):
        xml_output = get_config_value('xml-output',
                                      json_config.get_driver(), False)

        if isinstance(xml_output, bool):
            self.config.xml_output = xml_output
        elif str(xml_output).lower() == "false":
            self.config.xml_output = False
        else:
            self.config.xml_output = True

        rerun = get_config_value('rerun', json_config.get_driver(), False)
        if isinstance(rerun, bool):
            self.rerun = rerun
        elif str(rerun).lower() == "false":
            self.rerun = False
        else:
            self.rerun = True

        timeout_config = get_config_value('timeout',
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config) // 1000
        else:
            self.config.timeout = 900

    def _after_command(self, kits, request):
        if self.config.device.get("device_kernel") == \
                DeviceLiteKernel.linux_kernel:
            self.config.device.execute_command_with_timeout(
                command="cd /storage", timeout=1)
        else:
            self.config.device.execute_command_with_timeout(
                command="cd /", timeout=1)
        for kit in kits:
            kit.__teardown__(request.config.device)
        self.config.device.close()
        self.delete_device_xml(request, self.linux_directory)

        report_name = "report" if request.root.source. \
            test_name.startswith("{") else get_filename_extension(
            request.root.source.test_name)[0]
        if not self.config.dry_run:
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message,
                report_name)

    def generate_device_xml(self, request, execute_bin):
        if self.config.xml_output:
            self.download_nfs_xml(request, self.config.device_xml_path)
            self.merge_xml(execute_bin)

    def dry_run(self, request, command, listener=None):
        if self.config.xml_output:
            collect_test_command = "%s --gtest_output=xml:%s " \
                                   "--gtest_list_tests" % \
                                   (command, self.config.device_report_path)
            result, _, _ = self.config.device.execute_command_with_timeout(
                command=collect_test_command,
                case_type=DeviceTestType.cpp_test_lite,
                timeout=15, receiver=None)
            if CPP_TEST_MOUNT_STOP_SIGN in result:
                tests = []
                return tests
            tests = self.read_nfs_xml(request, self.config.device_xml_path)
            self.delete_device_xml(request, self.config.device_xml_path)
            return tests

        else:
            parsers = get_plugin(Plugin.PARSER, ParserType.cpp_test_list_lite)
            parser_instances = []
            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suites_name = os.path.basename(self.result)
                if listener:
                    parser_instance.listeners = listener
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)

            collect_test_command = "%s --gtest_list_tests" % command
            result, _, _ = self.config.device.execute_command_with_timeout(
                command=collect_test_command,
                case_type=DeviceTestType.cpp_test_lite,
                timeout=15, receiver=handler)
            self.config.command_result = "{}{}".format(
                self.config.command_result, result)
            if parser_instances[0].tests and \
                    len(parser_instances[0].tests) > 0:
                suite_list = []
                for item in parser_instances[0].tests:
                    suite_list.append(item.test_name)
                SuiteReporter.set_suite_list(suite_list)
            else:
                SuiteReporter.set_suite_list([])
            tests = parser_instances[0].tests
        if not tests:
            LOG.error("Collect test failed!", error_no="00402")
        return parser_instances[0].tests

    def run_cpp_test(self, command, request):
        if request.config.testargs.get("test"):
            testcases_list = get_testcases(
                request.config.testargs.get("test"))
            for test in testcases_list:
                command_case = "{} --gtest_filter=*{}".format(
                    command, test)

                if not self.config.xml_output:
                    self.run(command_case, request.listeners, timeout=15)
                else:
                    command_case = "{} --gtest_output=xml:{}".format(
                        command_case, self.config.device_report_path)
                    self.run(command_case, None, timeout=15)
        else:
            self._do_test_run(command, request)

    def init_cpp_config(self):
        setattr(self.config, "command_result", "")
        setattr(self.config, "device_xml_path", "")
        setattr(self.config, "dry_run", False)

    def merge_xml(self, execute_bin):
        report_path = os.path.join(self.config.report_path, "result")
        summary_result = DataHelper.get_summary_result(
            report_path, self.result, key=sort_by_length,
            file_prefix=execute_bin)
        if summary_result:
            SuiteReporter.append_report_result((
                os.path.join(report_path, "%s.xml" % execute_bin),
                DataHelper.to_string(summary_result)))
        else:
            self.error_message = "The test case did not generate XML"
        for xml_file in os.listdir(os.path.split(self.result)[0]):
            if not xml_file.startswith(execute_bin):
                continue
            if xml_file != os.path.split(self.result)[1]:
                os.remove(os.path.join(os.path.split(
                    self.result)[0], xml_file))

    def set_file_name(self, request, command):
        self.file_name = command.split(" ")[0].split("/")[-1].split(".")[0]
        self.result = "%s.xml" % os.path.join(request.config.report_path,
                                              "result", self.file_name)

    def run(self, command=None, listener=None, timeout=None):
        if not timeout:
            timeout = self.config.timeout
        parser_instances = []
        if listener:
            parsers = get_plugin(Plugin.PARSER, ParserType.cpp_test_lite)
            for parser in parsers:
                parser_instance = parser.__class__()
                parser_instance.suite_name = self.file_name
                parser_instance.listeners = listener
                parser_instances.append(parser_instance)
            handler = ShellHandler(parser_instances)
        else:
            handler = None
        result, _, error = self.config.device.execute_command_with_timeout(
            command=command, case_type=DeviceTestType.cpp_test_lite,
            timeout=timeout, receiver=handler)
        self.config.command_result += result
        if result.count(CPP_TEST_NFS_SIGN) >= 1:
            _, _, error = self.config.device.execute_command_with_timeout(
                command="ping %s" % self.linux_host,
                case_type=DeviceTestType.cpp_test_lite,
                timeout=5)
        device = self.config.device
        for parser_instance in parser_instances:
            if hasattr(parser_instance, "product_info"):
                product_info = parser_instance.product_info
                device.update_device_props(product_info)
        return error, result, handler

    def _do_test_run(self, command, request):
        test_to_run = self._collect_test_to_run(request, command)
        self._run_with_rerun(command, request, test_to_run)

    def _run_with_rerun(self, command, request, expected_tests):
        if self.config.xml_output:
            self.run("{} --gtest_output=xml:{}".format(
                command, self.config.device_report_path))
            time.sleep(5)
            test_rerun = True
            if self.check_xml_exist(self.execute_bin + ".xml"):
                test_rerun = False
            test_run = self.read_nfs_xml(request,
                                         self.config.device_xml_path,
                                         test_rerun)
            if len(test_run) < len(expected_tests):
                expected_tests = TestDescription.remove_test(expected_tests,
                                                             test_run)
                self._rerun_tests(command, expected_tests, None)
        else:
            test_tracker = CollectingLiteGTestListener()
            listener = request.listeners
            listener_copy = listener.copy()
            listener_copy.append(test_tracker)
            self.run(command, listener_copy)
            test_run = test_tracker.get_current_run_results()
            if len(test_run) != len(expected_tests):
                expected_tests = TestDescription.remove_test(expected_tests,
                                                             test_run)
                self._rerun_tests(command, expected_tests, listener)

    def _rerun_tests(self, command, expected_tests, listener):
        if not expected_tests:
            LOG.debug("No tests to re-run, all tests executed at least once.")
        for test in expected_tests:
            self._re_run(command, test, listener)

    def _re_run(self, command, test, listener):
        if self.config.xml_output:
            _, _, handler = self.run("{} {}=*{} --gtest_output=xml:{}".format(
                command, GTestConst.exec_para_filter, test.test_name,
                self.config.device_report_path),
                listener, timeout=15)
        else:
            handler = None
            for _ in range(FAILED_RUN_TEST_ATTEMPTS):
                try:
                    listener_copy = listener.copy()
                    test_tracker = CollectingLiteGTestListener()
                    listener_copy.append(test_tracker)
                    _, _, handler = self.run("{} {}=*{}".format(
                        command, GTestConst.exec_para_filter, test.test_name),
                        listener_copy, timeout=15)
                    if test_tracker.get_current_run_results():
                        return
                except LiteDeviceError as _:
                    LOG.debug("Exception: ShellCommandUnresponsiveException")
            handler.parsers[0].mark_test_as_failed(test)

    def _collect_test_to_run(self, request, command):
        if self.rerun:
            tests = self.dry_run(request, command)
            return tests
        return []

    def download_nfs_xml(self, request, report_path):
        remote_nfs = get_nfs_server(request)
        if not remote_nfs:
            err_msg = ErrorMessage.Config.Code_0302022.format(self.remote)
            LOG.error(err_msg)
            raise TypeError(err_msg)
        LOG.info("Trying to pull remote server: {}:{} report files to local "
                 "in dir {}".format
                 (remote_nfs.get("ip"), remote_nfs.get("port"),
                  os.path.dirname(self.result)))
        result_dir = os.path.join(request.config.report_path, "result")
        os.makedirs(result_dir, exist_ok=True)
        try:
            if remote_nfs["remote"] == "true":
                import paramiko
                client = paramiko.Transport((remote_nfs.get("ip"),
                                             int(remote_nfs.get("port"))))
                client.connect(username=remote_nfs.get("username"),
                               password=remote_nfs.get("password"))
                sftp = paramiko.SFTPClient.from_transport(client)
                files = sftp.listdir(report_path)

                for report_xml in files:
                    if report_xml.endswith(".xml"):
                        filepath = report_path + report_xml
                        try:
                            sftp.get(remotepath=filepath,
                                     localpath=os.path.join(os.path.split(
                                         self.result)[0], report_xml))
                        except IOError as error:
                            LOG.error(error, error_no="00404")
                client.close()
            else:
                if os.path.isdir(report_path):
                    for report_xml in os.listdir(report_path):
                        if report_xml.endswith(".xml"):
                            filepath = report_path + report_xml
                            shutil.copy(filepath, os.path.join(os.path.split(self.result)[0], report_xml))
        except (FileNotFoundError, IOError) as error:
            LOG.error("Download xml failed %s" % error, error_no="00403")

    def check_xml_exist(self, xml_file, timeout=60):
        ls_command = "ls %s" % self.config.device_report_path
        start_time = time.time()
        while time.time() - start_time < timeout:
            result, _, _ = self.config.device.execute_command_with_timeout(
                command=ls_command, case_type=DeviceTestType.cpp_test_lite,
                timeout=5, receiver=None)
            if xml_file in result:
                return True
            time.sleep(5)
            if (self.execute_bin + "_1.xml") in result:
                return False
        return False

    def read_nfs_xml(self, request, report_path, is_true=False):
        remote_nfs = get_nfs_server(request)
        if not remote_nfs:
            err_msg = ErrorMessage.Config.Code_0302022.format(self.remote)
            LOG.error(err_msg)
            raise TypeError(err_msg)
        tests = []
        execute_bin_xml = (self.execute_bin + "_1.xml") if is_true else (
                self.execute_bin + ".xml")
        LOG.debug("run into :{}".format(is_true))
        file_path = os.path.join(report_path, execute_bin_xml)
        if not self.check_xml_exist(execute_bin_xml):
            return tests

        from xml.etree import ElementTree
        try:
            if remote_nfs["remote"] == "true":
                import paramiko
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(hostname=remote_nfs.get("ip"),
                               port=int(remote_nfs.get("port")),
                               username=remote_nfs.get("username"),
                               password=remote_nfs.get("password"))
                sftp_client = client.open_sftp()
                remote_file = sftp_client.open(file_path)
                try:
                    result = remote_file.read().decode()
                    suites_element = ElementTree.fromstring(result)
                    for suite_element in suites_element:
                        suite_name = suite_element.get("name", "")
                        for case in suite_element:
                            case_name = case.get("name")
                            test = TestDescription(suite_name, case_name)
                            if test not in tests:
                                tests.append(test)
                finally:
                    remote_file.close()
                client.close()
            else:
                if os.path.isdir(report_path):
                    flags = os.O_RDONLY
                    modes = stat.S_IWUSR | stat.S_IRUSR
                    with os.fdopen(os.open(file_path, flags, modes),
                                   "r") as test_file:
                        result = test_file.read()
                        suites_element = ElementTree.fromstring(result)
                        for suite_element in suites_element:
                            suite_name = suite_element.get("name", "")
                            for case in suite_element:
                                case_name = case.get("name")
                                test = TestDescription(suite_name, case_name)
                                if test not in tests:
                                    tests.append(test)
        except (FileNotFoundError, IOError) as error:
            LOG.error("Download xml failed %s" % error, error_no="00403")
        except SyntaxError as error:
            LOG.error("Parse xml failed %s" % error, error_no="00404")
        return tests

    def delete_device_xml(self, request, report_path):
        remote_nfs = get_nfs_server(request)
        if not remote_nfs:
            err_msg = ErrorMessage.Config.Code_0302022.format(self.remote)
            LOG.error(err_msg)
            raise TypeError(err_msg)
        LOG.info("Delete xml directory {} from remote server: {}"
                 "".format
                 (report_path, remote_nfs.get("ip")))
        if remote_nfs["remote"] == "true":
            import paramiko
            client = paramiko.Transport((remote_nfs.get("ip"),
                                         int(remote_nfs.get("port"))))
            client.connect(username=remote_nfs.get("username"),
                           password=remote_nfs.get("password"))
            sftp = paramiko.SFTPClient.from_transport(client)
            try:
                sftp.stat(report_path)
                files = sftp.listdir(report_path)
                for report_xml in files:
                    if report_xml.endswith(".xml"):
                        filepath = "{}{}".format(report_path, report_xml)
                        try:
                            sftp.remove(filepath)
                            time.sleep(0.5)
                        except IOError as _:
                            pass
            except FileNotFoundError as _:
                pass
            client.close()
        else:
            for report_xml in glob.glob(os.path.join(report_path, '*.xml')):
                try:
                    os.remove(report_xml)
                except Exception as exception:
                    LOG.error(
                        "remove {} Failed:{}".format(report_xml, exception))
                    pass

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""

