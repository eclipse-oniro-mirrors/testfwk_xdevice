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
import platform
import subprocess
import time
import json
import re
import stat
import shutil
import zipfile
import threading
from typing import Union

from ohos.constants import CKit
from ohos.drivers import *
from ohos.drivers.constants import TIME_OUT
from ohos.error import ErrorMessage
from ohos.executor.listener import CollectingPassListener
from ohos.utils import get_ta_class
from ohos.utils import group_list
from ohos.utils import print_not_exist_class
from ohos.utils import modify_class_and_notclass
from ohos.utils import build_tests_dict
from ohos.utils import build_new_fault_case
from ohos.utils import setup_teardown
from ohos.utils import parse_and_modify_report
from ohos.utils import build_xml
from xdevice import Request

__all__ = ["oh_jsunit_para_parse", "OHJSUnitTestDriver", "OHJSUnitTestRunner", "OHJSLocalTestDriver"]

LOG = platform_logger("OHJSUnitDriver")


def oh_jsunit_para_parse(runner, junit_paras):
    junit_paras = dict(junit_paras)
    test_type_list = ["function", "performance", "reliability", "security"]
    size_list = ["small", "medium", "large"]
    level_list = ["0", "1", "2", "3", "4"]
    for para_name in junit_paras.keys():
        para_name = para_name.strip()
        para_values = junit_paras.get(para_name, [])
        if not para_values:
            continue
        para_value = para_values[0]
        if para_name == "testType" and para_value in test_type_list:
            # function/performance/reliability/security
            runner.add_arg(para_name, para_value)
        elif para_name == "size" and para_value in size_list:
            # small/medium/large
            runner.add_arg(para_name, para_value)
        elif para_name == "level" and para_value in level_list:
            # 0/1/2/3/4
            runner.add_arg(para_name, para_value)
        elif para_name == "stress":
            runner.add_arg(para_name, para_value)
        elif para_name == "coverage":
            runner.add_arg(para_name, para_value)


class OHJSCoverage:

    def __init__(self, request, runner):
        self.request = request
        self.runner = runner
        self.js_coverage_files = []

        request_config = self.request.config
        repeat_round = request.get_repeat_round()
        cov_folder = f"cov{repeat_round}" if request_config.repeat > 1 else "cov"
        # /report-path/cov
        self.cov_path = os.path.join(request_config.report_path, cov_folder)
        self.device = None
        if request_config.environment is not None:
            self.device = request_config.environment.devices[0]
        self.is_coverage_true = hasattr(request_config, "coverage") and request_config.coverage

    def generate_report(self):
        if not self.js_coverage_files:
            return
        npm = shutil.which("npm")
        if not npm:
            LOG.error("There is no npm in environment. please install it!")
            return
        output_dir = os.path.join(self.cov_path, "output")
        output_test = os.path.join(output_dir, ".test")
        os.makedirs(output_dir, exist_ok=True)
        base_dir = os.path.dirname(self.request.root.source.config_file)
        source_dir = os.path.join(base_dir, "source")
        test_dir = os.path.join(base_dir, ".test")

        copy_coverage_files = []
        init_coverage_jsons = []
        init_coverage_json_relative_path = os.path.join("intermediates", "ohosTest", "init_coverage.json")
        for folder in os.listdir(test_dir):
            temp_path = os.path.join(test_dir, folder)
            if os.path.isfile(temp_path):
                continue
            init_coverage_json = os.path.join(temp_path, init_coverage_json_relative_path)
            if os.path.exists(init_coverage_json):
                dst = os.path.join(output_test, folder, init_coverage_json_relative_path)
                copy_coverage_files.append((init_coverage_json, dst))
                init_coverage_jsons.append(init_coverage_json)
        _init_coverage = "#".join(init_coverage_jsons)
        _js_coverage = "#".join(self.js_coverage_files)

        command = '"{}" run report "{}" "{}" "{}#{}"'.format(
            npm, source_dir, output_dir, _init_coverage, _js_coverage)
        package_path = self.request.config.package_tool_path
        cwd = os.getcwd()
        os.chdir(package_path)
        LOG.debug("Current work directory: {}".format(os.getcwd()))
        LOG.debug(command)
        result = exec_cmd(command, join_result=True)
        LOG.debug(result)
        os.chdir(cwd)
        # 拷贝覆盖率数据文件到覆盖率报告生成目录
        for js_coverage_file in self.js_coverage_files:
            dst = os.path.join(output_dir, os.path.basename(js_coverage_file))
            copy_coverage_files.append((js_coverage_file, dst))
        for src, dst in copy_coverage_files:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
        self.write_command_to_file(command, output_dir)
        self.compress_coverage_file(output_dir, self.cov_path, "coverage.zip")
        LOG.debug("Covert coverage finished")

    @staticmethod
    def compress_coverage_file(output_dir, cov_dir, dist_name):
        if not os.path.exists(output_dir):
            return
        # 过滤源码文件
        exclude = re.compile(r'\.e?ts\.html$')
        zip_name = os.path.join(cov_dir, dist_name)
        z = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
        for top, _, files in os.walk(output_dir):
            if not files:
                continue
            for file_name in files:
                file_path = os.path.join(top, file_name)
                temp_path = file_path.replace(output_dir + os.sep, "").replace("\\", "/")
                if re.search(exclude, temp_path) is not None:
                    continue
                z.write(file_path, temp_path)
        z.close()
        LOG.debug('{} compress success'.format(zip_name))

    def write_command_to_file(self, command, output):
        save_file = os.path.join(output, "reportCommand.txt")
        LOG.debug("Save file: {}".format(save_file))
        save_file_open = os.open(save_file, os.O_WRONLY | os.O_CREAT, FilePermission.mode_755)
        with os.fdopen(save_file_open, "w", encoding="utf-8") as save_handler:
            save_handler.write(command)
            save_handler.flush()
        LOG.debug("Write command to reportCommand.txt success")

    def pull_coverage_json(self, index: int = 0):
        if self.device is None:
            return
        remote = self.runner.coverage_data_path
        if not remote:
            LOG.debug("Coverage data path is null")
            return
        LOG.debug("Coverage data path: {}".format(remote))
        if not self.is_coverage_true:
            return
        os.makedirs(self.cov_path, exist_ok=True)
        module_name = self.request.get_module_name()
        cov_file_name = f"{module_name}_{index}.cov" if index > 0 else f"{module_name}.cov"
        cov_file_path = os.path.join(self.cov_path, cov_file_name)
        self.device.pull_file(remote, cov_file_path)
        if os.path.exists(cov_file_path):
            self.js_coverage_files.append(cov_file_path)


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
        # 是否为半容器
        self.ohca = False
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
                raise ParamError(ErrorMessage.Common.Code_0301001.format(request.root.source.source_string))
            LOG.debug("Test case file path: %s" % suite_file)
            self.config.device.set_device_report_path(request.config.report_path)
            # 是否为半容器
            self.ohca = check_device_ohca(self.config.device)
            log_level = self.config.device_log.get(ConfigConst.tag_loglevel, "INFO")
            if self.ohca:
                self.device_log = get_device_log_file(
                    request.config.report_path,
                    request.config.device.__get_serial__(),
                    "device_log",
                    module_name=request.get_module_name(),
                    repeat=request.config.repeat,
                    repeat_round=request.get_repeat_round())
                device_log_open = os.open(self.device_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o755)
                self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
                with os.fdopen(device_log_open, "a") as device_log_file_pipe:
                    _, self.hilog_proc = self.config.device.device_log_collector. \
                        start_catch_device_log(log_file_pipe=device_log_file_pipe,
                                               hilog_file_pipe=None, log_level=log_level)
                    self.config.device.device_log_collector.start_hilog_task()
            else:
                self.hilog = get_device_log_file(
                    request.config.report_path,
                    request.config.device.__get_serial__(),
                    "device_hilog",
                    module_name=request.get_module_name(),
                    repeat=request.config.repeat,
                    repeat_round=request.get_repeat_round())
                hilog_open = os.open(self.hilog, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o755)
                self.config.device.device_log_collector.add_log_address(self.device_log, self.hilog)
                self.config.device.execute_shell_command(command="hilog -r")
                with os.fdopen(hilog_open, "a") as hilog_file_pipe:
                    _, self.hilog_proc = self.config.device.device_log_collector. \
                        start_catch_device_log(hilog_file_pipe=hilog_file_pipe, log_level=log_level)
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
                    request.config.report_path, self.result, self.error_message, request=request)

    def __dry_run_execute__(self, request):
        LOG.debug("Start dry run xdevice JSUnit Test")
        self.config = request.config
        self.config.device = request.config.environment.devices[0]
        config_file = request.root.source.config_file
        suite_file = request.root.source.source_file

        if not suite_file:
            raise ParamError(ErrorMessage.Common.Code_0301001.format(request.root.source.source_string))
        LOG.debug("Test case file path: %s" % suite_file)
        self._dry_run_oh_jsunit(config_file, request)

    def _dry_run_oh_jsunit(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)
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
            _ohjs_runner_config(self, json_config, request)
            oh_jsunit_para_parse(self.runner, self.config.testargs)

            test_to_run = self.collect_test_to_run()
            LOG.info("Collected suite count is: {}, test count is: {}".
                     format(len(self.runner.expect_tests_dict.keys()),
                            len(test_to_run) if test_to_run else 0))
        finally:
            do_module_kit_teardown(request)

    def _run_oh_jsunit(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)
            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)

            index = next((i for i, kit in enumerate(self.kits)
                          if kit.__class__.__name__ == "FaultKit"), None)
            if index is not None:
                fault_kit = self.kits.pop(index)
            else:
                fault_kit = None

            self._get_driver_config(json_config)
            self.config.device.connector_command("target mount")
            self._start_smart_perf()
            do_module_kit_setup(request, self.kits)
            self.runner = OHJSUnitTestRunner(self.config)
            self.runner.ohca = self.ohca
            self.runner.suites_name = request.get_module_name()
            _ohjs_runner_config(self, json_config, request)
            if hasattr(self.config, "history_report_path") and self.config.testargs.get("test"):
                self._do_test_retry(request.listeners, self.config.testargs, fault_kit=fault_kit)
            else:
                self._make_exclude_list_file(request)
                oh_jsunit_para_parse(self.runner, self.config.testargs)
                _ohjs_run_test(self, request, fault_kit=fault_kit)

        finally:
            do_module_kit_teardown(request)

    def _get_driver_config(self, json_config):
        package = get_config_value('package-name',
                                   json_config.get_driver(), False)
        module = get_config_value('module-name',
                                  json_config.get_driver(), False)
        bundle = get_config_value('bundle-name',
                                  json_config.get_driver(), False)
        is_rerun = get_config_value('rerun', json_config.get_driver(), False)
        workers = get_config_value('workers',
                                   json_config.get_driver(), False, 0)

        self.config.package_name = package
        self.config.module_name = module
        self.config.bundle_name = bundle
        self.rerun = True if is_rerun == 'true' else False
        self.config.worker = workers

        if not package and not module:
            raise ParamError(ErrorMessage.Config.Code_0302001)
        timeout_config = get_config_value("shell-timeout",
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config)
        else:
            self.config.timeout = TIME_OUT

        coverage = get_config_value("coverage", json_config.get_driver(), False)
        package_tool_path = get_config_value(
            "package-tool-path", json_config.get_driver(), "")
        self.config.coverage = coverage
        self.config.package_tool_path = package_tool_path

    def do_test_run(self, listeners):
        listener_fixed = self.runner.filter_listener(listeners)
        test_to_run = self.collect_test_to_run()
        LOG.info("Collected suite count is: {}, test count is: {}".
                 format(len(self.runner.expect_tests_dict.keys()),
                        len(test_to_run) if test_to_run else 0))
        filter_class = self.runner.arg_list.get("class", "")
        if filter_class:
            ta_class = filter_class.split(",")
            print_not_exist_class(ta_class, test_to_run)

        if not test_to_run or not self.rerun:
            try:
                self.runner.run(listener_fixed)
                self.runner.notify_finished()
            except Exception as e:
                self.runner.notify_finished(str(e))
                raise e
        else:
            self._run_with_rerun(listener_fixed, test_to_run)

    def collect_test_to_run(self):
        run_results = self.runner.dry_run()
        return run_results

    def _run_tests(self, listener):
        test_tracker = CollectingPassListener()
        listener_copy = listener.copy()
        listener_copy.append(test_tracker)
        try:
            self.runner.run(listener_copy)
        except Exception as e:
            self.runner.notify_finished(str(e))
            raise e
        test_run = test_tracker.get_current_run_results()
        return test_run

    def _refresh(self, listener_list):
        for listener in listener_list:
            count = getattr(listener, "cycle", 0) + 1
            setattr(listener, "cycle", count)

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
                LOG.warning("No tests to re-run twice,please check")
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
        self._refresh(listener)
        test_run = self._run_tests(listener)
        self.runner.retry_times -= 1
        LOG.debug("Rerun twice, has run: %s" % len(test_run))
        if len(test_run) < len(expected_tests):
            expected_tests = TestDescription.remove_test(expected_tests,
                                                         test_run)
            if not expected_tests:
                LOG.warning("No tests to re-run third,please check")
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
        LOG.debug("Ready to rerun third, expect run: %s" % len(expected_tests))
        self._refresh(listener)
        self._run_tests(listener)
        LOG.debug("Rerun third success")
        self.runner.notify_finished()

    def _make_exclude_list_file(self, request):
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

    def _do_test_retry(self, listener, testargs, **kwargs):
        fault_kit = kwargs.get("fault_kit", None)
        tests_dict, case_list = build_tests_dict(testargs.get("test"))
        self.config.testargs.pop("test")

        if not fault_kit:
            self.runner.add_arg("class", ",".join(case_list))
            self.runner.expect_tests_dict = tests_dict
            self.runner.run(listener)
            self.runner.notify_finished()
        else:
            new_fault_case = build_new_fault_case(fault_kit.fault_case, case_list)
            elements = []

            for test in new_fault_case:
                _class = test.get("class", None)
                if not _class:
                    continue
                faults = test.get("faults", [])
                fault_name = "#" + "#".join(faults) if faults else ""

                with setup_teardown(self.config.device, fault_kit, faults=faults):
                    self.runner.add_arg("class", ",".join(_class))
                    self.runner.expect_tests_dict = test.get("tests_dict", {})
                    self.runner.run(listener)
                    self.runner.notify_finished()
                    parse_and_modify_report(self.result, fault_name, elements)

            else:
                build_xml(self.result, elements)

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
        serial = "{}_{}".format(str(self.config.device.__get_serial__()),
                                time.time_ns())
        log_tar_file_name = "{}".format(str(serial).replace(":", "_"))
        if self.config.device_log.get(ConfigConst.tag_enable) == ConfigConst.device_log_on and \
                hasattr(self.config.device.device_log_collector,
                        "start_get_crash_log"):
            self.config.device.device_log_collector.start_get_crash_log(
                log_tar_file_name,
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
        if self.ohca:
            self.config.device.device_log_collector.stop_hilog_task(
                log_tar_file_name,
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())
        self.config.device.device_log_collector.remove_log_address(
            self.device_log, self.hilog)
        self.config.device.device_log_collector.stop_catch_device_log(
            self.log_proc)
        self.config.device.device_log_collector.stop_catch_device_log(
            self.hilog_proc)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class OHJSUnitTestRunner:
    MAX_RETRY_TIMES = 3

    def __init__(self, config):
        self.arg_list = {}
        self.suites_name = None
        self.config = config
        self.rerun_attemp = 3
        self.finished = False
        self.expect_tests_dict = dict()
        self.finished_observer = None
        # 是否为半容器
        self.ohca = False
        self.retry_times = 1
        self.compile_mode = ""
        self.coverage_data_path = ""

    def filter_listener(self, listeners):
        listener_fixed = []
        for listener in listeners:
            if listener.__class__.__name__ == "ReportListener":
                continue
            listener_fixed.append(listener)
        from xdevice import ListenerType
        plugins = get_plugin(Plugin.LISTENER, ListenerType.stack_report)
        stack_listener = plugins[0].__class__()
        stack_listener.report_path = self.config.report_path
        listener_fixed.append(stack_listener)
        return listener_fixed

    def dry_run(self):
        parsers = get_plugin(Plugin.PARSER, CommonParserType.oh_jsunit_list)
        if parsers:
            parsers = parsers[:1]
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        handler.add_process_method(_ohjs_output_method)
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

    def notify_finished(self, finish_msg: str = ""):
        if self.finished_observer:
            self.finished_observer.notify_task_finished(finish_msg=finish_msg)
        self.retry_times -= 1

    def _get_shell_handler(self, listener):
        if self.config.worker > 0:
            parsers = get_plugin(Plugin.PARSER, CommonParserType.worker)
        else:
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
        args_commands = []
        for key, value in self.arg_list.items():
            if key == 'test_args':
                # 跳过拓展的运行参数
                continue
            if key == 'wait_time':
                args_commands.append(f'-w {value}')
            else:
                args_commands.append(f'-s {key} {value}')
        # 处理拓展的运行参数
        for test_arg in self.arg_list.get('test_args', []):
            test_arg = str(test_arg).strip()
            opt, key, val = self.unpack_command(test_arg)
            # 检查命令参数的格式
            if not (opt and key and val or opt and val):
                continue
            # 检查命令参数是否重复，若参数重复，则优先使用驱动自有字段配置的值
            test_arg_exists = False
            for cmd_str in args_commands:
                opt_ext, key_ext, val_ext = self.unpack_command(cmd_str)
                if opt == opt_ext and key == key_ext or opt == opt_ext and not key:
                    test_arg_exists = True
                    break
            if not test_arg_exists:
                args_commands.append(test_arg)
        return ' '.join(args_commands)

    @staticmethod
    def unpack_command(cmd_str):
        opt, key, val = None, None, None
        items = cmd_str.split(' ')
        if len(items) == 2:
            opt, val = items[0], items[1]
        elif len(items) == 3:
            opt, key, val = items[0], items[1], items[2]
        return opt, key, val

    def _get_run_command(self):
        command = ""
        if self.config.package_name:
            # aa test -p ${packageName} -b ${bundleName} -s unittest OpenHarmonyTestRunner
            command = "aa test -p {} -b {} -s unittest OpenHarmonyTestRunner" \
                      " {} {}".format(self.config.package_name,
                                      self.config.bundle_name,
                                      self.get_args_command(),
                                      self.get_worker_count())
        elif self.config.module_name:
            # aa test -m ${moduleName} -b ${bundleName} -s unittest OpenHarmonyTestRunner
            command = "aa test -m {} -b {} -s unittest {} {} {}".format(
                self.config.module_name, self.config.bundle_name,
                self.get_oh_test_runner_path(), self.get_args_command(), self.get_worker_count())
        if self.ohca:
            command = "ohsh {}".format(command)

        return command.strip()

    def _get_dry_run_command(self):
        command = ""
        if self.config.package_name:
            command = "aa test -p {} -b {} -s unittest OpenHarmonyTestRunner" \
                      " {} -s dryRun true".format(self.config.package_name,
                                                  self.config.bundle_name,
                                                  self.get_args_command())
        elif self.config.module_name:
            command = "aa test -m {} -b {} -s unittest {}" \
                      " {} -s dryRun true". \
                format(self.config.module_name, self.config.bundle_name,
                       self.get_oh_test_runner_path(),
                       self.get_args_command())
        if self.ohca:
            command = "ohsh {}".format(command)

        return command

    def get_oh_test_runner_path(self):
        if self.compile_mode == "esmodule":
            return "/ets/testrunner/OpenHarmonyTestRunner"
        else:
            return "OpenHarmonyTestRunner"

    def get_worker_count(self):
        if self.config.worker > 0:
            return "-s worker {}".format(self.config.worker)
        else:
            return ""


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.ValidatorTest)
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
                '.'.join((request.get_module_name(), "xml")))
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
        isUpdate = False
        try:
            if "update" in self.config.testargs.keys():
                if dict(self.config.testargs).get("update")[0] == "true":
                    isUpdate = True
            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)
            self._get_driver_config(json_config)
            if isUpdate:
                do_module_kit_setup(request, self.kits)
            while True:
                print("Is test finished? Y/N")
                usr_input = input(">>>> ")
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
            if isUpdate:
                do_module_kit_teardown(request)

    def _get_driver_config(self, json_config):
        self.xml_path = \
            get_config_value("xml_path", json_config.get_driver(), False)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_jslocal_test)
class OHJSLocalTestDriver(IDriver):
    """
       OHJSLocalTestDriver is a Test that runs a native test package on PC.
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

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start execute OpenHarmony JSLocalTest")
            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))
            self.config = request.config

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file
            self.config.json_file = config_file
            if not suite_file:
                raise ParamError(ErrorMessage.Common.Code_0301001.format(request.root.source.source_string))
            LOG.debug("Test case file path: %s" % suite_file)
            self._run_oh_js_local(config_file, request)
        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=True, error_no="03409")
            raise exception
        finally:
            pass

    def _run_oh_js_local(self, config_file, request):
        try:
            if not os.path.exists(config_file):
                err_msg = ErrorMessage.Common.Code_0301002.format(config_file)
                LOG.error(err_msg)
                raise ParamError(err_msg)
            json_config = JsonParser(config_file)
            self.kits = get_kit_instances(json_config,
                                          self.config.resource_path,
                                          self.config.testcases_path)

            self._get_driver_config(json_config)
            do_module_kit_setup(request, self.kits)
            self.runner = OHJSLocalTestRunner(self.config)
            self.runner.suites_name = request.get_module_name()
            _ohjs_runner_config(self, json_config, request)
            oh_jsunit_para_parse(self.runner, self.config.testargs)
            _ohjs_run_test(self, request)

        finally:
            do_module_kit_teardown(request)

    def _get_driver_config(self, json_config):
        package = get_config_value('package-name',
                                   json_config.get_driver(), False)
        module = get_config_value('module-name',
                                  json_config.get_driver(), False)
        bundle = get_config_value('bundle-name',
                                  json_config.get_driver(), False)
        is_rerun = get_config_value('rerun', json_config.get_driver(), False)
        previewer_params = get_config_value('previewer-params', json_config.get_driver(), False)
        coverage = get_config_value("coverage", json_config.get_driver(), False)
        package_tool_path = get_config_value(
            "package-tool-path", json_config.get_driver(), "")

        self.config.coverage = coverage
        self.config.package_tool_path = package_tool_path
        self.config.package_name = package
        self.config.module_name = module
        self.config.bundle_name = bundle
        self.config.previewer_params = previewer_params
        self.rerun = True if is_rerun == 'true' else False

        if not package and not module:
            raise ParamError(ErrorMessage.Config.Code_0302001)
        timeout_config = get_config_value("shell-timeout",
                                          json_config.get_driver(), False)
        if timeout_config:
            self.config.timeout = int(timeout_config)
        else:
            self.config.timeout = TIME_OUT

    def do_test_run(self, listener):
        try:
            self.runner.run(listener)
            self.runner.notify_finished()
        except Exception as e:
            self.runner.notify_finished(str(e))
            raise e

    def collect_test_to_run(self):
        run_results = self.runner.dry_run()
        return run_results

    def _run_tests(self, listener):
        test_tracker = CollectingPassListener()
        listener_copy = listener.copy()
        listener_copy.append(test_tracker)
        self.runner.run(listener_copy)
        test_run = test_tracker.get_current_run_results()
        return test_run

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""


class OHJSLocalTestRunner:
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
        self.coverage_data_path = ""

    def run(self, listener):
        handler = self._get_shell_handler(listener)
        command = self._get_run_command(self.config)
        self.execute_jslocal_command(command, timeout=self.config.timeout, receiver=handler)

    @staticmethod
    def execute_jslocal_command(command, timeout=TIME_OUT, receiver=None, **kwargs):
        stop_event = threading.Event()
        output_flag = kwargs.get("output_flag", True)
        run_command = command
        try:
            if output_flag:
                LOG.info(" ".join(run_command))
            else:
                LOG.debug(" ".join(run_command))
            if platform.system() == "Windows":
                proc = subprocess.Popen(" ".join(run_command),
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
            else:
                proc = subprocess.Popen(run_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False)
            timeout_thread = threading.Thread(target=OHJSLocalTestRunner.kill_proc,
                                              args=(proc, timeout, stop_event))
            timeout_thread.daemon = True
            timeout_thread.start()
            while True:
                output = proc.stdout.readline()
                if output == b'' and proc.poll() is not None:
                    break
                if output and b'OHOS_REPORT' in output:
                    if receiver:
                        receiver.__read__(output.strip().decode('utf-8') + "\n")
                    else:
                        LOG.debug(output.strip().decode('utf-8'))
                if b'The AbilityDelegator.finishTest' in output:
                    break
            if stop_event.is_set():
                LOG.error("ShellCommandUnresponsiveException: command {}".format(run_command))
                LOG.exception("execute timeout!", exc_info=False)
                raise ShellCommandUnresponsiveException(ErrorMessage.Common.Code_0301011)
        except Exception as error:
            LOG.exception(error, exc_info=False)
            err_msg = ErrorMessage.Device.Code_0303012.format(error)
            LOG.error(err_msg)
            raise ExecuteTerminate(err_msg) from error
        finally:
            stop_event.set()
            if receiver:
                receiver.__done__()

    @staticmethod
    def kill_proc(proc, timeout, stop_event):
        # test-timeout单位是毫秒
        end_time = time.time() + int(timeout / 1000)
        while time.time() < end_time and not stop_event.is_set():
            time.sleep(1)
        if proc.poll() is None:
            proc.kill()
            stop_event.set()

    def notify_finished(self, finish_msg: str = ""):
        if self.finished_observer:
            self.finished_observer.notify_task_finished(finish_msg=finish_msg)
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

    def _get_run_command(self, config):
        sdk = os.environ.get("HarmonySdk")
        if not sdk:
            raise EnvironmentError(ErrorMessage.Common.Code_0301004)
        openharmony_path = os.path.join(sdk, "openharmony")
        sdk_version = sorted(os.listdir(openharmony_path), key=lambda x: int(x))[-1]
        exe_path = r"previewer\common\bin\Previewer.exe"
        previewer_path = os.path.join(openharmony_path, sdk_version, exe_path)
        folder_path = os.path.dirname(config.json_file)
        refresh = config.previewer_params.get("refresh")
        project_id = config.previewer_params.get("projectID")
        ts = config.previewer_params.get("ts")
        j = os.path.join(folder_path, ".test", config.previewer_params.get("j"))
        s = config.previewer_params.get("s")
        cpm = config.previewer_params.get("cpm")
        device = config.previewer_params.get("device")
        shape = config.previewer_params.get("shape")
        sd = config.previewer_params.get("sd")
        _or = config.previewer_params.get("or")
        cr = config.previewer_params.get("cr")
        f = os.path.join(folder_path, config.previewer_params.get("f"))
        n = config.previewer_params.get("n")
        av = config.previewer_params.get("av")
        url = config.previewer_params.get("url")
        pages = config.previewer_params.get("pages")
        arp = os.path.join(folder_path, ".test", config.previewer_params.get("arp"))
        pm = config.previewer_params.get("pm")
        l = config.previewer_params.get("l")
        cm = config.previewer_params.get("cm")
        o = config.previewer_params.get("o")
        lws = config.previewer_params.get("lws")
        command = [previewer_path, "-refresh", refresh, "-projectID", project_id, "-ts", ts, "-j", j, "-s", s, "-cpm",
                   cpm, "-device", device, "-shape", shape, "-sd", sd, "-or", _or, "-cr", cr, "-f", f, "-n", n, "-av",
                   av, "-url", url, "-pages", pages, "-arp", arp, "-pm", pm, "-l", l, "-cm", cm, "-o", o, "-lws", lws]
        return command


def _ohjs_output_method(handler, output, end_mark="\n"):
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


def _ohjs_runner_config(driver: Union[OHJSUnitTestDriver, OHJSLocalTestDriver], json_config: JsonParser, request: Request):
    runner = driver.runner
    driver_config = json_config.get_driver()
    test_timeout = get_config_value('test-timeout', driver_config, False)
    if test_timeout:
        runner.add_arg('wait_time', int(test_timeout))
    testcase_timeout = get_config_value('testcase-timeout', driver_config, False)
    if testcase_timeout:
        runner.add_arg('timeout', int(testcase_timeout))
    test_args = get_config_value('test-args', driver_config, default=[])
    test_args_from_tf = request.get_tf_test_args()
    test_args.extend(test_args_from_tf)
    if test_args:
        runner.add_arg('test_args', test_args)
    runner.compile_mode = get_config_value('compile-mode', driver_config, False)
    if driver.config.coverage:
        runner.add_arg('coverage', 'true')


def _ohjs_run_test(driver: Union[OHJSUnitTestDriver, OHJSLocalTestDriver], request: Request, **kwargs):
    listeners = request.listeners
    runner = driver.runner
    if driver.rerun:
        runner.retry_times = runner.MAX_RETRY_TIMES
    ohjs_cov_instance = OHJSCoverage(request, runner)

    fault_kit = kwargs.get("fault_kit", None)

    def _start_run_test():
        filter_class = group_list(get_ta_class(driver, request))
        if not filter_class:
            LOG.info('----- run test with no filter class -----')
            driver.do_test_run(listeners)
            ohjs_cov_instance.pull_coverage_json()
        else:
            LOG.info('----- run test with filter class -----')
            total = len(filter_class)
            for index, ta_class in enumerate(filter_class, 1):
                LOG.info(f'[{index}/{total}] run test with filter class size {len(ta_class)}')
                if driver.rerun:
                    runner.retry_times = runner.MAX_RETRY_TIMES
                runner.add_arg('class', ','.join(ta_class))
                driver.do_test_run(listeners)
                runner.remove_arg('class')
                ohjs_cov_instance.pull_coverage_json(index=index)
        ohjs_cov_instance.generate_report()

    if fault_kit:
        elements = []
        for test in fault_kit.fault_case:
            _class = test.get("class", None)
            notclass = test.get("notclass", None)
            faults = test.get("faults", [])
            modify_class_and_notclass(request, _class, notclass)
            fault_name = "#" + "#".join(faults) if faults else ""

            with setup_teardown(driver.config.device, fault_kit, faults):
                _start_run_test()
                parse_and_modify_report(driver.result, fault_name, elements)

        else:
            build_xml(driver.result, elements)

    else:
        _start_run_test()
