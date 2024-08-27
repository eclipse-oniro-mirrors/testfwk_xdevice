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

import copy
import os
import sys

from xdevice import get_plugin
from xdevice import ModeType
from xdevice import ConfigConst
from xdevice import DeviceLabelType
from xdevice import TestExecType
from xdevice import DeviceError
from xdevice import ParamError
from xdevice import ReportException
from xdevice import ExecuteTerminate
from xdevice import IDriver
from xdevice import platform_logger
from xdevice import Plugin
from xdevice import JsonParser
from xdevice import get_config_value
from xdevice import do_module_kit_setup
from xdevice import do_module_kit_teardown
from xdevice import get_filename_extension
from xdevice import get_file_absolute_path
from xdevice import get_kit_instances
from xdevice import check_result_report
from xdevice import check_mode
from xdevice import SuiteReporter
from xdevice import CaseEnd
from xdevice import Binder
from xdevice import HostDrivenTestType
from xdevice import Variables
from devicetest.constants import CKit
from devicetest.core.constants import DeviceTestMode
from devicetest.error import ErrorMessage

__all__ = ["DeviceTestDriver", "DeviceTestSuiteDriver"]
LOG = platform_logger("DeviceTest")
PY_SUFFIX = ".py"
PYD_SUFFIX = ".pyd"
PYC_SUFFIX = ".pyc"


def _get_dict_test_list(module_path, file_name):
    test_list = []
    for root, _, files in os.walk(module_path):
        for _file in files:
            if (_file.endswith(".py") or _file.endswith(".pyd")) \
                    and file_name == os.path.splitext(_file)[0]:
                test_list.append(os.path.join(root, _file))
    return test_list


def start_smart_perf(config, kits):
    if not hasattr(config, ConfigConst.kits_in_module):
        return
    if CKit.smartperf not in config.get(ConfigConst.kits_in_module):
        return
    sp_kits = get_plugin(Plugin.TEST_KIT, CKit.smartperf)[0]
    sp_kits.target_name = config.get("bundle_name", "")
    param_config = config.get(ConfigConst.kits_params).get(CKit.smartperf, "")
    sp_kits.__check_config__(param_config)
    kits.insert(0, sp_kits)


def handle_test_args(config, request):
    pass


def do_driver_execute(driver_obj: IDriver, request):
    try:
        # delete sys devicetest mode
        if hasattr(sys, DeviceTestMode.MODE):
            delattr(sys, DeviceTestMode.MODE)

        # set self.config
        driver_obj.config = request.config
        driver_obj.config.devices = request.get_devices()
        if request.get("exectype") == TestExecType.device_test and \
                not driver_obj.config.devices:
            err_msg = ErrorMessage.TestCase.Code_0203009
            LOG.error(err_msg)
            raise ParamError(err_msg)

        # get source, json config and kits
        if request.get_config_file():
            source = request.get_config_file()
            LOG.debug("Test config file path: %s" % source)
        else:
            source = request.get_source_string()
            LOG.debug("Test String: %s" % source)

        if not source:
            err_msg = ErrorMessage.TestCase.Code_0203010.format(request.get_source_file())
            LOG.error(err_msg)
            raise ParamError(err_msg)

        json_config = JsonParser(source)
        kits = get_kit_instances(json_config, request.config.resource_path,
                                 request.config.testcases_path)
        start_smart_perf(driver_obj.config, kits)
        test_name = request.get_module_name()
        driver_obj.result = os.path.join(request.config.report_path, "result", "%s.xml" % test_name)

        # set configs keys
        configs = driver_obj._set_configs(json_config, kits, request)

        # handle test args
        handle_test_args(config=driver_obj.config, request=request)

        # get test list
        test_list = driver_obj._get_test_list(json_config, request, source)
        if not test_list:
            raise ParamError(ErrorMessage.TestCase.Code_0203011)
        driver_obj._run(configs, test_list)
    except (ReportException, ModuleNotFoundError, ExecuteTerminate,
            SyntaxError, ValueError, AttributeError, TypeError,
            KeyboardInterrupt, ParamError, DeviceError) \
            as exception:
        error_no = getattr(exception, "error_no", "00000")
        LOG.exception(exception, exc_info=False, error_no=error_no)
        driver_obj.error_message = exception
        Binder.notify_stage(
            CaseEnd(request.get_module_name(), "Failed", str(driver_obj.error_message)))
    finally:
        driver_obj._handle_finally(request)


@Plugin(type=Plugin.DRIVER, id=HostDrivenTestType.device_test)
class DeviceTestDriver(IDriver):
    """
    DeviceTest is a Test that runs a host-driven test on given devices.
    """
    # test driver config
    config = None
    result = ""
    error_message = ""
    py_file = ""

    def __init__(self):
        self.linux_host = ""
        self.linux_directory = ""

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config=None):
        pass

    def __init_nfs_server__(self, request=None):
        pass

    def __execute__(self, request):
        do_driver_execute(self, request)

    def _get_test_list(self, json_config, request, source):
        test_list = get_config_value('py_file', json_config.get_driver(),
                                     is_list=True)
        if str(request.root.source.source_file).endswith(PYD_SUFFIX) or \
                str(request.root.source.source_file).endswith(PY_SUFFIX):
            test_list = [request.root.source.source_file]

        if not test_list and os.path.exists(source):
            dir_name, file_name = os.path.split(source)
            file_name, _ = os.path.splitext(file_name)
            test_list = _get_dict_test_list(os.path.dirname(source), file_name)

        # check test list
        testcase = request.get("testcase")
        testcase_list = []
        if testcase:
            testcase_list = str(testcase).split(";")

        checked_test_list = []
        for _, test in enumerate(test_list):
            if not os.path.exists(test):
                try:
                    absolute_file = get_file_absolute_path(test, [
                        self.config.resource_path, self.config.testcases_path])
                except ParamError as error:
                    LOG.error(error, error_no=error.error_no)
                    continue
            else:
                absolute_file = test

            file_name = get_filename_extension(absolute_file)[0]
            if not testcase_list or file_name in testcase_list:
                checked_test_list.append(absolute_file)
            else:
                LOG.info("Test '%s' is ignored", absolute_file)
        if checked_test_list:
            LOG.info("Test list: {}".format(checked_test_list))
        else:
            err_msg = ErrorMessage.TestCase.Code_0203012
            LOG.error(err_msg)
            raise ParamError(err_msg)
        if len(checked_test_list) > 1:
            err_msg = ErrorMessage.TestCase.Code_0203013.format(request.get_module_name(), test_list)
            LOG.error(err_msg)
            raise ParamError(err_msg)
        return checked_test_list

    def _set_configs(self, json_config, kits, request):
        configs = dict()
        configs["testargs"] = self.config.testargs or {}
        configs["testcases_path"] = self.config.testcases_path or ""
        configs["request"] = request
        configs["test_name"] = request.get_module_name()
        configs["report_path"] = request.config.report_path
        configs["execute"] = get_config_value(
            'execute', json_config.get_driver(), False)

        for device in self.config.devices:
            do_module_kit_setup(request, kits)
            if device.label == DeviceLabelType.ipcamera:
                # add extra keys to configs for ipcamera device
                self.__init_nfs_server__(request=request)
                configs["linux_host"] = self.linux_host
                configs["linux_directory"] = self.linux_directory
                configs["kits"] = kits

        return configs

    def _handle_finally(self, request):
        # do kit teardown
        do_module_kit_teardown(request)

        # close device connect
        for device in self.config.devices:
            if device.label == DeviceLabelType.ipcamera or device.label == \
                    DeviceLabelType.watch_gt:
                device.close()
            if device.label == DeviceLabelType.phone:
                device.close()

        # check result report
        report_name = request.root.source.test_name if \
            not request.root.source.test_name.startswith("{") \
            else "report"
        module_name = request.get_module_name()
        if Binder.session().mode != ModeType.decc:
            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message,
                report_name, module_name)
        else:
            tmp_list = copy.copy(SuiteReporter.get_report_result())
            if self.result not in [report_path for report_path, _ in tmp_list]:
                if not self.error_message:
                    self.error_message = "Case not execute[01205]"
                self.result = check_result_report(
                    request.config.report_path, self.result,
                    self.error_message, report_name, module_name)

    def _run(self, configs, test_list):
        # insert paths for loading _devicetest module and testcases
        devicetest_module = os.path.join(Variables.modules_dir, "_devicetest")
        if os.path.exists(devicetest_module):
            sys.path.insert(1, devicetest_module)
        if configs["testcases_path"]:
            sys.path.insert(1, configs["testcases_path"])
            sys.path.insert(1, os.path.dirname(configs["testcases_path"]))

        # apply data to devicetest module about resource path
        request = configs.get('request', None)
        if request:
            sys.ecotest_resource_path = request.config.resource_path

        # run devicetest
        from devicetest.main import DeviceTest
        device_test = DeviceTest(test_list, configs, self.config.devices, self.result)
        device_test.run()

    def __result__(self):
        if check_mode(ModeType.decc):
            return self.result
        return self.result if os.path.exists(self.result) else ""


def _get_dict_testsuite(testsuite, config):
    post_suffix = [PY_SUFFIX, PYD_SUFFIX, PYC_SUFFIX]
    for suffix in post_suffix:
        testsuite_file = "{}{}".format(testsuite, suffix)
        if not os.path.exists(testsuite_file):
            try:
                absolute_file = get_file_absolute_path(testsuite_file, [
                    config.resource_path, config.testcases_path])
                return absolute_file
            except ParamError as error:
                LOG.error(error, error_no=error.error_no)
                continue
        else:
            return testsuite_file
    return None


@Plugin(type=Plugin.DRIVER, id=HostDrivenTestType.device_testsuite)
class DeviceTestSuiteDriver(IDriver):
    """
    DeviceTestSuiteDriver is a Test that runs a host-driven test on given devices.
    """
    # test driver config
    config = None
    result = ""
    error_message = ""
    py_file = ""

    def __init__(self):
        pass

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config=None):
        pass

    def __init_nfs_server__(self, request=None):
        pass

    def __execute__(self, request):
        do_driver_execute(self, request)

    def _get_test_list(self, json_config, request, source):
        testsuite = get_config_value('testsuite', json_config.get_driver(),
                                     is_list=False)

        if not testsuite and os.path.exists(source):
            dir_name, file_name = os.path.split(source)
            file_name, _ = os.path.splitext(file_name)
            temp_testsuite = _get_dict_test_list(os.path.dirname(source), file_name)
            if temp_testsuite:
                testsuite = temp_testsuite[0]

        if not testsuite:
            err_msg = ErrorMessage.TestCase.Code_0203014
            LOG.error(err_msg)
            raise ParamError(err_msg)

        checked_testsuite = None
        if testsuite.endswith(PY_SUFFIX) or \
                testsuite.endswith(PYD_SUFFIX) or \
                testsuite.endswith(PYC_SUFFIX):
            if not os.path.exists(testsuite):
                try:
                    checked_testsuite = get_file_absolute_path(testsuite, [
                        self.config.resource_path, self.config.testcases_path])
                except ParamError as error:
                    LOG.debug(error, error_no=error.error_no)
            else:
                checked_testsuite = testsuite
        else:
            checked_testsuite = _get_dict_testsuite(testsuite, self.config)

        if checked_testsuite:
            LOG.info("Test suite list: {}".format(checked_testsuite))
        else:
            err_msg = ErrorMessage.TestCase.Code_0203012
            LOG.error(err_msg)
            raise ParamError(err_msg)
        return checked_testsuite

    def _set_configs(self, json_config, kits, request):
        configs = dict()
        configs["testargs"] = self.config.testargs or {}
        configs["testcases_path"] = self.config.testcases_path or ""
        configs["resource_path"] = self.config.resource_path or ""
        configs["request"] = request
        configs["device_log"] = request.config.device_log
        configs["test_name"] = request.get_module_name()
        configs["report_path"] = request.config.report_path
        configs["suitecases"] = get_config_value(
            'suitecases', json_config.get_driver(), True)
        configs["listeners"] = request.listeners.copy()

        do_module_kit_setup(request, kits)

        return configs

    def _handle_finally(self, request):
        # do kit teardown
        do_module_kit_teardown(request)

        # close device connect
        for device in self.config.devices:
            if device.label == DeviceLabelType.phone:
                device.close()

        # check result report
        report_name = request.root.source.test_name if \
            not request.root.source.test_name.startswith("{") \
            else "report"
        module_name = request.get_module_name()
        self.result = check_result_report(
            request.config.report_path, self.result, self.error_message,
            report_name, module_name)

    def _run(self, configs, test_list):
        if configs["testcases_path"]:
            sys.path.insert(1, configs["testcases_path"])
            sys.path.insert(1, os.path.dirname(configs["testcases_path"]))
        request = configs.get('request', None)
        if request:
            sys.ecotest_resource_path = request.config.resource_path

        # run AppTest
        from devicetest.main import DeviceTestSuite
        app_test = DeviceTestSuite(test_list, configs, self.config.devices)
        app_test.run()

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""
