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

import re
import sys
import time
import traceback
import warnings
from functools import wraps
from typing import Union

from xdevice import convert_serial
from xdevice import get_decode
from xdevice import get_cst_time
from xdevice import ConfigConst
from xdevice import IDevice
from xdevice import EnvPool
from xdevice import is_env_pool_run_mode
from xdevice import AgentMode
from xdevice import Variables

from devicetest.core.exception import BaseTestError
from devicetest.core.exception import HdcCommandRejectedException
from devicetest.core.exception import ShellCommandUnresponsiveException
from devicetest.core.exception import DeviceNotFound
from devicetest.core.exception import AppInstallError
from devicetest.core.exception import RpcNotRunningError
from devicetest.core.exception import TestFailure
from devicetest.core.exception import TestError
from devicetest.core.exception import TestSkip
from devicetest.core.exception import TestTerminated
from devicetest.core.exception import TestAbortManual
from devicetest.core.exception import DeviceTestError
from devicetest.core.exception import TestAssertionError
from devicetest.core.constants import RunResult
from devicetest.core.constants import RunSection
from devicetest.core.constants import RunStatus
from devicetest.core.variables import DeccVariable
from devicetest.core.variables import CurCase
from devicetest.error import ErrorMessage
from devicetest.utils.time_util import TS
from devicetest.utils.type_utils import T
from devicetest.log.logger import DeviceTestLog as log
from devicetest.controllers.tools.screen_agent import ScreenAgent

RESULT_LINE_TEMPLATE = "[Test Step] %s %s"


def validate_test_name(name):
    """Checks if a test name is not null.
    Args:
        name: name of a test case.
    Raises:
        BaseTestError is raised if the name is null.
    """
    if name == "" or name is None or len(name) < 1:
        raise BaseTestError(ErrorMessage.TestCase.Code_0203004.format(name))


class DeviceRoot:
    is_root_device = False

    def __init__(self):
        pass

    @staticmethod
    def set_device_root(is_root):
        DeviceRoot.is_root_device = is_root

    @staticmethod
    def get_device_root():
        return DeviceRoot.is_root_device


class CoreCase:
    """Base class for all test classes to inherit from.
    This class gets all the controller objects from test_runner and executes
    the test cases requested within itself.
    """

    def __init__(self, tag, configs):
        self.cur_case = None
        self.devices = []
        self.configs = configs
        self.result = RunResult.PASSED
        self.last_result = RunResult.PASSED
        self.test_method_result = RunResult.PASSED
        self.section = RunSection.SETUP
        self.error_msg = ''
        self.trace_info = ''
        self.start_time = get_cst_time()
        self.log = self.configs["log"]
        self.set_project(self.configs["project"])
        self.con_fail_times = 0
        self.fail_times = 0
        self.step_flash_fail_msg = False
        self.pass_through = Variables.config.pass_through
        # loop执行场景标记，避免exec_one_testcase覆写loop里设置的结果
        self._is_loop_scenario = False
        # proxy function
        self.execption_callback = None
        # case end function
        self.case_end_callback = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._exec_func(self.clean_up)

    def _print_error(self, error: str, result: RunResult = RunResult.FAILED,
                     refresh_method_result: bool = False, screenshot: bool = True):
        """打印异常信息
        error : str, error message
        result: RunResult, RunResult class variables
        refresh_method_result: bool, refresh result flag
        screenshot: bool, 运行keyword/checkepr装饰的接口异常，默认是有失败截图，可将其设为False，可避免重复截图
        """
        self.log.error(error)
        self.error_msg = str(error)
        self.result = result
        if refresh_method_result:
            self.test_method_result = result
        if screenshot:
            # 在非keyword装饰的接口执行失败的时候，对每个设备进行截图
            for device in self.devices:
                ScreenAgent.screen_take_picture([device], False, "shot_on_fail")

        trace_info = traceback.format_exc()
        index = self.cur_case.step_index
        if index == -1:
            self.log.error(self.error_msg)
            self.log.error(trace_info)
            return
        step_error_id = f'step_error_{index}'
        self.log.error(f'<span id="{step_error_id}">{self.error_msg}</span>')
        self.log.error(traceback.format_exc())
        _error = f'<a href="javascript:" onclick="gotoStep(\'{step_error_id}\')">{self.error_msg}</a>'
        UpdateStep(index, error=_error)

    def setup(self):
        """Setup function that will be called before executing any test case
        in the test class. Implementation is optional.
        """
        return True

    def process(self):
        """process function that will be called before setup function and after
        teardown function in the test class. Implementation is optional.
        """
        pass

    def teardown(self):
        """Teardown function that will be called after all the selected test
        cases in the test class have been executed.
        Implementation is optional.
        """
        pass

    def exec_one_testcase(self, test_name, test_func):
        """Executes one test case and update test results.
        Args:
            test_name: Name of the test.
            test_func: The test function.
        Returns:
            True if the test passes, False otherwise.
        """
        if not self._exec_func(self.setup_test):
            self.log.error("Setup for {} failed, skipping.".format(test_name))
        _result = None
        error = None
        try:
            verdict = test_func()
        except TestSkip:
            # Test skipped.
            _result = True
            self.log.debug("TestSkip")
        except (AppInstallError, BaseTestError, DeviceNotFound, DeviceTestError,
                TestAssertionError, TestError, TestFailure, TestTerminated, TestAbortManual) as exception:
            # 上述异常，已设置错误码，无需再次设置
            error = str(exception)
            self._print_error(error, refresh_method_result=True, screenshot=False)
        except HdcCommandRejectedException as exception:
            error = ErrorMessage.Device.Code_0202302.format(exception)
            self._print_error(error, refresh_method_result=True)
        except ShellCommandUnresponsiveException as exception:
            error = ErrorMessage.Device.Code_0202304.format(exception)
            self._print_error(error, refresh_method_result=True)
        except RpcNotRunningError as exception:
            error = ErrorMessage.Device.Code_0202305.format(exception)
            self._print_error(error, refresh_method_result=True)
        except ConnectionRefusedError as exception:
            error = ErrorMessage.Device.Code_0202306.format(exception)
            self._print_error(error, refresh_method_result=True)
        except ImportError as exception:
            error = ErrorMessage.TestCase.Code_0203006.format(exception)
            self._print_error(error, refresh_method_result=True, screenshot=False)
        except Exception as exception:
            error = ErrorMessage.TestCase.Code_0203002.format(exception)
            self._print_error(error, refresh_method_result=True)
        else:
            # loop执行场景，由其方法内设置测试结果
            if self._is_loop_scenario:
                _result = True
                return
            if (verdict is None or verdict is True) \
                    and self.test_method_result == RunResult.PASSED:
                # Test passed.
                self.print_case_result(test_name, RunResult.PASSED)
                _result = True
            # Test failed because it didn't return True.
            # This should be removed eventually.
            else:
                error_msg = "test func '{}' The actual input value of " \
                            "the checkpoint is inconsistent with the " \
                            "expected result.".format(test_func.__name__)
                self.log.error(error_msg)
                self.test_method_result = self.result = RunResult.FAILED
                self.error_msg = error_msg
                _result = False

        finally:
            if self.execption_callback is not None and error is not None:
                self.execption_callback(error)
            self._exec_func(self.teardown_test)

    def _exec_func(self, func, *args):
        """Executes a function with exception safeguard.
        Args:
            func: Function to be executed.
            args: Arguments to be passed to the function.
        Returns:
            Whatever the function returns, or False if unhandled exception
            occured.
        """
        ret = False
        error = None
        try:
            func(*args)
            ret = True
        except (AppInstallError, DeviceNotFound, DeviceTestError,
                TestAssertionError, TestError, TestAbortManual, TestTerminated) as exception:
            # 上述异常，已设置错误码，无需再次设置
            error = str(exception)
            self._print_error(error, screenshot=False)
        except HdcCommandRejectedException as exception:
            error = ErrorMessage.Device.Code_0202302.format(exception)
            self._print_error(error)
        except ShellCommandUnresponsiveException as exception:
            error = ErrorMessage.Device.Code_0202304.format(exception)
            self._print_error(error)
        except RpcNotRunningError as exception:
            error = ErrorMessage.Device.Code_0202305.format(exception)
            self._print_error(error)
        except ConnectionRefusedError as exception:
            error = ErrorMessage.Device.Code_0202306.format(exception)
            self._print_error(error)
        except Exception as exception:
            error = ErrorMessage.TestCase.Code_0203002.format(exception)
            self._print_error(error)
        finally:
            if self.execption_callback is not None and error is not None:
                self.execption_callback(error)
        return ret

    def _get_test_funcs(self):
        # All tests are selected if test_cases list is None.
        # Load functions based on test names. Also find the longest test name.
        test_funcs = []
        for test_name in self.tests:
            try:
                validate_test_name(test_name)
                test_funcs.append((test_name, getattr(self, test_name)))
            except AttributeError:
                self.result = RunResult.FAILED
                self.error_msg = "{} does not have test step {}.".format(
                    self.TAG, test_name)
                self.log.error(self.error_msg)

            except BaseTestError as exception:
                self.result = RunResult.FAILED
                self.error_msg = self.generate_fail_msg("{}:{}".format(str(exception), traceback.format_exc()))
                self.log.error(str(exception))

        return test_funcs

    def run(self, test_names=None):
        """Runs test cases within a test class by the order they
        appear in the test list.
        Being in the test_names list makes the test case "requested". If its
        name passes validation, then it'll be executed, otherwise the name will
        be skipped.
        Args:
            test_names: A list of names of the requested test cases. If None,
                all test cases in the class are considered requested.
        Returns:
            A tuple of: The number of requested test cases, the number of test
            cases executed, and the number of test cases passed.
        """
        if RunStatus.FINISHED == self.run_setup():
            return
        self.run_tests(test_names)
        run_result = self.result
        self.run_teardown()
        # 避免teardown报错导致结果失败1/./
        self.result = run_result
        if self.case_end_callback is not None:
            self.case_end_callback()

    def run_setup(self):
        self.section = RunSection.SETUP
        self.cur_case.set_run_section(self.section)
        self.run_setup_start()
        self.log.info("**********SetUp Starts!")
        ret = self._exec_func(self.setup)
        if not ret:
            self.log.info("**********SetUp Ends!")
            self.log.error("setup step fails")
            self.section = RunSection.TEARDOWN
            self.cur_case.set_run_section(self.section)
            self.log.info("**********TearDown Starts!")
            self._exec_func(self.teardown)
            if self.result != RunResult.BLOCKED:
                self.result = RunResult.FAILED
            self.log.info('**********TearDown Ends!')

            self.print_case_result(self.TAG, self.result)

            return RunStatus.FINISHED
        else:
            self.log.info("**********SetUp Ends!")
            self.run_setup_end()

        return RunStatus.RUNNING

    def run_tests(self, test_names):
        self.section = RunSection.TEST
        self.cur_case.set_run_section(self.section)
        if hasattr(self, "tests") and isinstance(getattr(self, "tests", None), list):
            tests = self._get_test_funcs()
            for test_name, test_func in tests:
                self.run_test(test_name, test_func)
        else:
            self.run_process()
        self.log.info("**********All test methods Ends!**********")

    def run_process(self):
        self._exec_func(self.process)

    def run_test(self, test_name, test_func):
        self.log.info("[Test Step] {}".format(test_name))
        self.test_method_result = RunResult.PASSED
        self.exec_one_testcase(test_name, test_func)
        self.test_method_end(test_name)

    def run_teardown(self):
        self.section = RunSection.TEARDOWN
        self.cur_case.set_run_section(self.section)
        self.run_teardown_start()
        self.log.info("**********TearDown Starts!")
        self._exec_func(self.teardown)
        self.log.info("**********TearDown Ends!")
        self.run_teardown_end()
        self._exec_func(self.clean_up)

    def run_perf_models(self, models, fail_break=False):
        """
        models: list, list of model object
        fail_break: bool, if this is set to True, break down the loop of model execution when it fails
        """
        self._is_loop_scenario = True
        fail_models, pass_models, total = [], [], len(models)
        for model in models:
            model_name = model.__class__.__name__
            # 预置model的测试结果pass，避免执行循环时测试结果受到干扰
            self.test_method_result = RunResult.PASSED
            self.log.info("Executing test model {}".format(model_name))
            # 执行jump_to_start_anchor成功后，再执行execute
            self.exec_one_testcase("{}.jump_to_start_anchor".format(model_name), model.jump_to_start_anchor)
            if self.test_method_result == RunResult.PASSED:
                self.exec_one_testcase("{}.execute".format(model_name), model.execute)
            if self.test_method_result == RunResult.PASSED:
                pass_models.append(model_name)
                continue
            fail_models.append(model_name)
            if fail_break:
                break
        fail_cnt, pass_cnt = len(fail_models), len(pass_models)
        self.log.info("Test models executed result with "
                      "{} fail({}), {} pass({})".format(fail_cnt, fail_models, pass_cnt, pass_models))
        # 所有model执行通过，用例pass
        if pass_cnt == total:
            self.error_msg = ""
            self.result = RunResult.PASSED
            return
        self.result = RunResult.FAILED

    def test_method_end(self, test_name):
        """
        case test method end event
        """
        self.log.info("TestMethod: {} result is {}".format(test_name, self.test_method_result))
        self.log.info("TestMethod: {} End".format(test_name))

    def clean_up(self):
        """A function that is executed upon completion of all tests cases
        selected in the test class.
        This function should clean up objects initialized in the constructor
        by user.
        """
        pass

    def run_setup_start(self):
        """A function that is before all tests cases and before setup cases
        selected in the test class.
        This function can be customized to create different base classes or use cases.
        """
        self.setup_start()

    def setup_start(self):
        """A function that is before all tests cases
        selected in the test class.
        This function can be used to execute before running.
        """
        pass

    def run_setup_end(self):
        """A function that is before all tests cases and after setup cases
        selected in the test class.
        This function can be customized to create different base classes or use cases.
        """
        self.setup_end()

    def setup_end(self):
        """A function that is after setup cases
        selected in the test class.
        This function can be used to execute after setup.
        """
        pass

    @classmethod
    def setup_test(cls):
        """Setup function that will be called every time before executing each
        test case in the test class.

        Implementation is optional.
        """
        return True

    def teardown_test(self):
        """Teardown function that will be called every time a test case has
        been executed.
        Implementation is optional.
        """
        pass

    def run_teardown_start(self):
        """A function that is after all tests cases and before teardown cases
        selected in the test class.
        This function can be customized to create different base classes or use cases.
        """
        self.teardown_start()

    def teardown_start(self):
        """A function that is before teardown cases
        selected in the test class.
        This function can be used to execute before running.
        """
        pass

    def run_teardown_end(self):
        """A function that is after all tests cases and teardown cases
        selected in the test class.
        This function can be customized to create different base classes or use cases.
        """
        self.teardown_end()

    def teardown_end(self):
        """A function that is after teardown cases
        selected in the test class.
        This function can be used to execute before running.
        """
        pass

    def print_case_result(self, case, result):
        self.log.info("****************************Test {} result is: {}"
                      .format(case, result))

    def generate_fail_msg(self, msg):
        if isinstance(self.error_msg, str) and self.error_msg != "":
            pass
        else:
            self.error_msg = msg
        return self.error_msg

    def set_log(self, _log):
        self.log = _log

    def set_project(self, project):
        self.project = project
        DeccVariable.set_project_obj(self.project)
        self.cur_case = DeccVariable.cur_case()
        self._init_case_var(self.TAG)
        self.log.info("init case variables success.")

    def _init_case_var(self, tag):
        if tag:
            self.cur_case.set_name(tag)
        else:
            self.cur_case.set_name(self.project.execute_case_name)

        if not hasattr(self, "tests"):
            setattr(self, "tests", ["process"])
        request = self.configs.get("request", None)
        repeat, repeat_round = 1, 1
        if request is not None:
            repeat, repeat_round = request.config.repeat, request.get_repeat_round()
        self.cur_case.set_step_total(1)
        self.cur_case.set_case_screenshot_dir(
            self.project.test_suite_path,
            self.project.task_report_dir,
            self.project.cur_case_full_path,
            repeat=repeat, repeat_round=repeat_round)

    @classmethod
    def step(cls, _ad, stepepr):
        result = stepepr
        if result is not None and isinstance(result, bool) and not result:
            _ad.log.error(_ad.device_id + " exec step is fail")
        elif _ad.screenshot:
            pass
        return result


class BaseCase:
    """Base class for simple test classes to inherit from.
    This class gets all the controller objects from test_runner and executes
    the test cases requested within itself.
    """

    def __init__(self, tag, controllers: Union[IDevice, dict]):
        self.log = None
        if isinstance(controllers, dict):
            if controllers.get("devices", None):
                if not isinstance(controllers["devices"], list):
                    devices = list()
                    devices.append(controllers["devices"])
                    self.devices = devices
                else:
                    self.devices = controllers["devices"]
        else:
            devices = list()
            devices.append(controllers)
            self.devices = devices
        self.result = RunResult.PASSED
        self.error_msg = ''
        self.trace_info = ''
        self.start_time = get_cst_time()
        self.test_method_result = None
        self._set_device_attr(controllers)
        self._auto_record_steps = False
        self.configs = controllers
        self.configs.setdefault("report_path", EnvPool.report_path)
        # loop执行场景标记，避免exec_one_testcase覆写loop里设置的结果
        self._is_loop_scenario = False
        # proxy function
        self.execption_callback = None
        # case end function
        self.case_end_callback = None
        self.pass_through = self.configs.get(ConfigConst.testargs, {}).get(ConfigConst.pass_through, {})
        self.cur_case = DeccVariable.cur_case()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def _set_device_attr(self, controllers):
        index = 1
        for device in self.devices:
            setattr(self, "Phone{}".format(index), device)
            setattr(self, "device{}".format(index), device)
            if controllers.get("screenshot", None):
                setattr(device, "screenshot", controllers["screenshot"])
            if controllers.get("screenshot_fail", None):
                setattr(device, "screenshot_fail", controllers["screenshot_fail"])
            else:
                setattr(device, "screenshot_fail", True)
            # 控制agent的模式, 默认是bin模式
            mode = controllers.get("agent_mode", AgentMode.bin)
            device.set_agent_mode(mode)

    def set_auto_record_steps(self, flag):
        """
        flag: bool, A switch be used to disable record steps automatically
        """
        self._auto_record_steps = flag

    def get_auto_record_steps_status(self):
        """
        return if record steps automatically
        """
        return self._auto_record_steps

    def get_case_result(self):
        return self.result


class TestCase(CoreCase, BaseCase):
    """Base class for all test classes to inherit from.
    This class gets all the controller objects from test_runner and executes
    the test cases requested within itself.
    """

    def __init__(self, tag, configs):
        if is_env_pool_run_mode():
            BaseCase.__init__(self, tag, configs)
        else:
            CoreCase.__init__(self, tag, configs)
            self.devices = []
            self.device1 = None
            self.device2 = None
            self.set_devices(self.configs["devices"])
            self.testLoop = 0

    def _exec_func(self, func, *args):
        """Executes a function with exception safeguard.
        Args:
            func: Function to be executed.
            args: Arguments to be passed to the function.
        Returns:
            Whatever the function returns, or False if unhandled exception
            occured.
        """
        return CoreCase._exec_func(self, func, *args)

    def loop_start(self):
        pass

    def loop_end(self, testResult):
        pass

    def loop(self, test_name, looptimes=0, fail_break=False, fail_times=0, reset_test=None, cat_log_step=None,
             continues_fail=False):

        self.con_fail_times = 0
        self.last_result = RunResult.PASSED

        self.fail_times = 0
        self.testLoop = 0
        for i in range(0, int(looptimes)):
            self.log.info("--- Loop in %s time ---" % str(i + 1))
            self.testLoop += 1
            if self.result != RunResult.PASSED:
                if fail_break and not fail_times:
                    break

            if self.project.record.is_shutdown():
                self.result = RunResult.FAILED
                self.error_msg = "Testcase is stopped by manual!"
                self.log.error(self.error_msg)
                break

            self.test_method_result = RunResult.PASSED
            self.error_msg = ""
            self.loop_start()
            self.exec_one_testcase(test_name, getattr(self, test_name))
            self.loop_end(self.result)

            self.log.info("--- Loop in %s-loop%s time result is: %s ---"
                          % (test_name, str(i + 1), self.test_method_result))
            self.test_method_end(self.test_method_result)

            if DeccVariable.cur_case().test_method.func_ret:
                self.log.warning("{} time loop end, the FUNCRET has error, clear FUNCRET again.".format(str(i + 1)))
                DeccVariable.cur_case().test_method.func_ret.clear()
            if self.test_method_result != "Passed":
                self.fail_times += 1

                if continues_fail:
                    if self.last_result != "Passed":
                        self.con_fail_times += 1
                    else:
                        self.con_fail_times = 1

                if cat_log_step is not None:
                    self.exec_one_testcase(cat_log_step, getattr(self, cat_log_step))
                if reset_test is not None:
                    self.exec_one_testcase(reset_test, getattr(self, reset_test))

            self.last_result = self.test_method_result
            if continues_fail and fail_break and self.con_fail_times > fail_times:
                break
            if not continues_fail and fail_break and self.fail_times > fail_times:
                break

        if self.test_method_result != "Passed":
            self.test_method_result = RunResult.PASSED

        if not continues_fail and self.fail_times >= fail_times:
            self.error_msg += " -- Loop fail %d times" % self.fail_times
            self.log.error("{} fail {} times".format(test_name, self.fail_times))
        elif continues_fail and self.con_fail_times >= fail_times:
            self.error_msg += " -- Loop continues fail %d times" % self.con_fail_times
            self.log.error("{} continues fail {} times".format(test_name, self.con_fail_times))
        else:
            self.result = RunResult.PASSED
            self.error_msg = ""

    def set_devices(self, devices):
        self.devices = devices
        if not devices:
            return

        try:
            for num, _ad in enumerate(self.devices, 1):
                if not hasattr(_ad, "device_id") or not getattr(_ad, "device_id"):
                    setattr(_ad, "device_id", "device{}".format(num))
                # 兼容release2 增加id、serial
                setattr(_ad, "id", _ad.device_id)
                setattr(_ad, "serial", _ad.device_sn)
                setattr(self, _ad.device_id, _ad)
                setattr(self, "device{}".format(num), _ad)
        except Exception as error:
            err_msg = ErrorMessage.TestCase.Code_0203007
            log.error(err_msg, is_traceback=True)
            raise DeviceTestError(err_msg) from error

    def set_property(self, index):
        if isinstance(self.project.property_config, dict):
            get_devices = self.project.property_config.get("devices")
            if isinstance(get_devices, list) and len(get_devices) > index:
                propertys = get_devices[index]
                if isinstance(propertys, dict):
                    self.log.debug("set propertys: {}".format(propertys))
                    return propertys
                self.log.debug("get propertys: {}".format(propertys))
                self.log.warning("propertys not a dict!")
        return {}

    def get_property(self, property):
        if hasattr(self, "propertys"):
            get_value = self.propertys.get(property)
            log.debug("get property {}:{}".format(property, get_value))
            return get_value
        else:
            log.warning("'Device' object has no attribute 'propertys'")
            return None

    def get_case_report_path(self):
        return self.configs.get("report_path")

    def get_case_result(self):
        return self.result

    def set_case_result_content(self, content: dict):
        """set result content for testcase（供用例拓展结果内容）
        content: dict, result content
        """
        if not isinstance(content, dict) or not content:
            return
        self.log.info(f"setting result content: {content}")
        setattr(self, "result_content", content)

    def set_auto_record_steps(self, flag):
        """
        flag: bool, A switch be used to disable record steps automatically
        """
        warnings.warn("function is deprecated", DeprecationWarning)
        cur_case = DeccVariable.cur_case()
        if cur_case is None:
            self.log.warning("current case object is none, can not disable record step automatically")
            return
        DeccVariable.cur_case().auto_record_steps_info = flag


class WindowsTestCase(CoreCase):
    """Base class for all windows test classes to inherit from.
    This class gets all the controller objects from test_runner and executes
    the test cases requested within itself.
    """

    def __init__(self, tag, configs):
        super().__init__(tag, configs)

    def _exec_func(self, func, *args):
        """Executes a function with exception safeguard.
        Args:
            func: Function to be executed.
            args: Arguments to be passed to the function.
        Returns:
            Whatever the function returns, or False if unhandled exception
            occurred.
        """
        return CoreCase._exec_func(self, func, *args)

    def clear_device_callback_method(self):
        pass


def _log_info_aw_information(func, args, kwargs, is_checkepr=False):
    cur_case = DeccVariable.cur_case()
    if len(cur_case.test_method.func_ret) == 0:
        if is_checkepr:
            cur_case.set_checkepr(True)
            cur_case.cur_check_cmd.__init__()
        else:
            cur_case.set_checkepr(False)
        aw_level = "aw"
    elif len(cur_case.test_method.func_ret) == 1:
        aw_level = "aw1"
    else:
        aw_level = "aw2"
    aw_info = _gen_aw_invoke_info_no_div(func, args, kwargs)
    log.info("<div class='{}'>{}</div>".format(aw_level, aw_info))


def _get_is_raise_exception(kwargs):
    if "EXCEPTION" not in kwargs:
        is_raise_exception = True
    else:
        is_raise_exception = kwargs.pop("EXCEPTION")
    return is_raise_exception, kwargs


def _get_msg_args(kwargs):
    msg_args = None
    if "failMsg" in kwargs:
        msg_args = kwargs.pop("failMsg")
        msg_args = '' if msg_args is None else ErrorMessage.TestCase.Code_0203002.format(msg_args)

    return msg_args, kwargs


def _get_ignore_fail():
    # 忽略定义在teardown里的接口的运行报错，使得teardown里的每个接口都能被执行
    return DeccVariable.cur_case().run_section == RunSection.TEARDOWN


def _screenshot_and_flash_error_msg(ignore_fail, is_raise_exception, msg_args,
                                    func_name, args, error_msg):
    ScreenAgent.screen_take_picture(args, False, func_name, is_raise_exception=is_raise_exception)
    if not ignore_fail:
        # 非teardown阶段
        if is_raise_exception:
            _flash_error_msg(msg_args, error_msg)
            raise DeviceTestError(error_msg)
        else:
            # 忽略异常
            log.info("Ignore current exception because parameter EXCEPTION is False.")
    else:
        # teardown阶段
        _flash_error_msg(msg_args, error_msg)


def _is_in_top_aw():
    starts_num = DeccVariable.cur_case().test_method.func_ret.count("Starts")
    ends_num = DeccVariable.cur_case().test_method.func_ret.count("Ends")
    log.debug("Starts: {}, Ends: {}".format(starts_num, ends_num))
    return True if starts_num == ends_num else False


def _check_ret_in_run_keyword(func, args, kwargs, _ret, cost_time,
                              ignore_fail, is_raise_exception, msg_args):
    aw_info = _gen_aw_invoke_info_no_div(func, args, kwargs)
    result = False if isinstance(_ret, bool) and not _ret else True
    cur_case = DeccVariable.cur_case()
    if _is_in_top_aw():
        cost = 0 if cost_time is None else round(cost_time / 1000, 3)
        log.info("<div class='aw'>{} cost: {}s</div>".format(aw_info, cost))
        cur_case.test_method.func_ret.clear()
        ScreenAgent.screen_take_picture(args, result, func.__name__, is_raise_exception=is_raise_exception)

    if not cur_case.checkepr and not result:
        if is_raise_exception and not ignore_fail:
            _flash_error_msg(msg_args, "测试用例执行失败")
            if msg_args:
                raise DeviceTestError(msg_args)
            raise TestFailure(ErrorMessage.TestCase.Code_0203003.format(aw_info))


def _check_ret_in_run_checkepr(func, args, kwargs, _ret, ignore_fail,
                               is_raise_exception, msg_args):
    cur_case = DeccVariable.cur_case()
    if _is_in_top_aw():
        cur_case.test_method.func_ret.clear()
        result = False if isinstance(_ret, bool) and not _ret else True
        ScreenAgent.screen_take_picture(args, result, func.__name__, is_raise_exception=is_raise_exception)
        if not _ret:
            aw_info = _gen_aw_invoke_info_no_div(func, args, kwargs)
            if cur_case.cur_check_cmd.get_cur_check_status():
                msg = cur_case.cur_check_cmd.get_cur_check_msg()
            else:
                msg = "Check Result: {} = {}!".format(_ret, aw_info)
                log.info("Return: {}".format(_ret))

            if is_raise_exception and not ignore_fail:
                _flash_error_msg(msg_args, "测试用例执行失败")
                if msg_args:
                    raise DeviceTestError(msg_args)
                raise TestFailure(ErrorMessage.TestCase.Code_0203003.format(aw_info))
            else:
                log.info(msg)
            time.sleep(0.01)  # 避免日志顺序混乱

        else:
            log.info("Return: {}".format(_ret))


def _check_exception(exception, in_method=False):
    # 测试设备断连找不见, 直接抛出异常
    find_result = re.search(r'device \w* not found|offline', str(exception))
    if find_result is not None:
        err_msg = ErrorMessage.Device.Code_0202306
        log.error(err_msg)
        if in_method:
            return True
        raise DeviceNotFound(err_msg)
    return False


def checkepr(func: T) -> T:
    @wraps(func)
    def wrapper(*args, **kwargs):
        # set default case obj
        if DeccVariable.cur_case() is None:
            cur_case = CurCase(log)
            DeccVariable.set_cur_case_obj(cur_case)
        DeccVariable.project.record.is_shutdown()
        _res = run_checkepr(func, *args, **kwargs)
        return _res

    return wrapper


def keyword(func: T) -> T:
    @wraps(func)
    def wrapper(*args, **kwargs):
        # set default case obj
        if DeccVariable.cur_case() is None:
            cur_case = CurCase(log)
            DeccVariable.set_cur_case_obj(cur_case)
        DeccVariable.project.record.is_shutdown()
        run_k = run_keyword(func, *args, **kwargs)
        return run_k

    return wrapper


def run_keyword(func, *args, **kwargs):
    _log_info_aw_information(func, args, kwargs)
    DeccVariable.cur_case().test_method.func_ret.append("Starts")
    is_raise_exception, kwargs = _get_is_raise_exception(kwargs)
    msg_args, kwargs = _get_msg_args(kwargs)
    ignore_fail = _get_ignore_fail()
    is_exception = True
    _ret = None
    cost_time = 0
    func_name = func.__name__
    try:
        TS.start()
        _ret = func(*args, **kwargs)
        log.debug("func {} ret: {}".format(func_name, _ret))
        cost_time = TS.stop()
        is_exception = False

        if is_raise_exception and (not ignore_fail) and func_name == 'get_info_from_decc_svr':
            if isinstance(_ret, dict):
                if _ret['code'] != 200 and (_ret['success'] == 'false'
                                            or _ret['success'] is False):
                    raise TestAssertionError('result error.')
    except (DeviceNotFound, DeviceTestError) as e:
        # 设备异常或DeviceTestError，直接将异常抛出，可解决错误码重复添加的问题
        raise e
    except TestAssertionError as exception:
        # 断言的自定义异常优先于aw自定义的failMsg
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, str(exception), func_name, args, '')
    except TypeError as exception:
        error_msg = ErrorMessage.TestCase.Code_0203008.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except HdcCommandRejectedException as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202302.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except ShellCommandUnresponsiveException as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202304.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except AppInstallError as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202307.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except RpcNotRunningError as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202305.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except ConnectionRefusedError as exception:
        # 设备掉线connector client连接拒绝
        error_msg = ErrorMessage.Device.Code_0202306.format(exception)
        log.error(error_msg)
        raise DeviceNotFound(error_msg) from exception
    except Exception as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.TestCase.Code_0203002.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    finally:
        DeccVariable.cur_case().test_method.func_ret.append("Ends")
        # 1.若执行接口出现异常，会进入_screenshot_and_flash_error_msg方法
        # 2.当接口不是定义在teardown里，且没有接口参数没有设置EXCEPTION=False，
        # 那么_screenshot_and_flash_error_msg方法会重新抛出DeviceTestError异常
        # 3.若接口不是定义在teardown里，执行出现异常，且回到了顶层aw，将Starts/Ends计数器清零
        if is_exception and not ignore_fail and _is_in_top_aw():
            log.debug('----------finally clear Starts/Ends--------')
            DeccVariable.cur_case().test_method.func_ret.clear()

    if is_exception:
        if _is_in_top_aw():
            DeccVariable.cur_case().test_method.func_ret.clear()
        return False
    _check_ret_in_run_keyword(func, args, kwargs, _ret, cost_time,
                              ignore_fail, is_raise_exception, msg_args)
    return _ret


def run_checkepr(func, *args, **kwargs):
    _log_info_aw_information(func, args, kwargs, is_checkepr=True)
    DeccVariable.cur_case().test_method.func_ret.append("Starts")
    is_raise_exception, kwargs = _get_is_raise_exception(kwargs)
    msg_args, kwargs = _get_msg_args(kwargs)
    ignore_fail = _get_ignore_fail()
    is_exception = True
    _ret = None
    func_name = func.__name__
    try:
        TS.start()
        # 执行当前函数
        _ret = func(*args, **kwargs)
        log.debug("step {} execute result: {}".format(func_name, _ret))
        TS.stop()
        is_exception = False
    except (DeviceNotFound, DeviceTestError) as e:
        # 设备异常或DeviceTestError，直接将异常抛出，可解决错误码重复添加的问题
        raise e
    except TestAssertionError as exception:
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, str(exception), func_name, args, '')
    except TypeError as exception:
        error_msg = ErrorMessage.TestCase.Code_0203008.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except HdcCommandRejectedException as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202302.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except ShellCommandUnresponsiveException as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202304.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except AppInstallError as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202307.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except RpcNotRunningError as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.Device.Code_0202305.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    except ConnectionRefusedError as exception:
        # 设备掉线connector client连接拒绝
        error_msg = ErrorMessage.Device.Code_0202306.format(exception)
        log.error(error_msg, is_traceback=True)
        raise DeviceNotFound(error_msg) from exception
    except Exception as exception:
        _check_exception(exception)
        error_msg = ErrorMessage.TestCase.Code_0203002.format(exception)
        log.error(error_msg, is_traceback=True)
        _screenshot_and_flash_error_msg(
            ignore_fail, is_raise_exception, msg_args, func_name, args, error_msg)
    finally:
        DeccVariable.cur_case().test_method.func_ret.append("Ends")
        # 1.若执行接口出现异常，会进入_screenshot_and_flash_error_msg方法
        # 2.当被执行的接口不在teardown阶段里运行，且没有接口参数没有设置EXCEPTION=False，
        # _screenshot_and_flash_error_msg方法会重新抛出DeviceTestError异常
        # 3.若执行非teardown的接口出现异常，且回到了顶层aw，将Starts/Ends计数器清零
        if is_exception and not ignore_fail and _is_in_top_aw():
            log.debug('----------finally clear Starts/Ends--------')
            DeccVariable.cur_case().test_method.func_ret.clear()

    if is_exception:
        if _is_in_top_aw():
            DeccVariable.cur_case().test_method.func_ret.clear()
        return False

    _check_ret_in_run_checkepr(func, args, kwargs, _ret, ignore_fail,
                               is_raise_exception, msg_args)
    return _ret


def _flash_error_msg(msg_args, error_msg):
    log.info("flash error msg.")
    # 优先使用断言的自定义异常，然后再是failMsg，最后是捕获的异常
    if msg_args:
        if not DeccVariable.cur_case().test_method.error_msg or \
                not DeccVariable.cur_case().test_method.step_flash_fail_msg:
            DeccVariable.cur_case().test_method.set_error_msg(msg_args)
            DeccVariable.cur_case().test_method.step_flash_fail_msg = True
            if not DeccVariable.cur_case().is_upload_method_result:
                DeccVariable.cur_case().set_error_msg(msg_args)
    else:
        if not DeccVariable.cur_case().test_method.error_msg:
            # 更新当前步骤error_msg
            DeccVariable.cur_case().test_method.set_error_msg(error_msg)
            if not DeccVariable.cur_case().is_upload_method_result \
                    and DeccVariable.cur_case().error_msg:
                DeccVariable.cur_case().set_error_msg(msg_args)

    DeccVariable.cur_case().test_method.set_result(RunResult.FAILED)
    if DeccVariable.cur_case().case_result == RunResult.PASSED:
        DeccVariable.cur_case().set_case_result(RunResult.FAILED)


def _gen_aw_invoke_info_no_div(func, args, kwargs):
    all_args = []
    name_id = None
    if args and getattr(args[0], "__module__", None):
        try:
            _ad = args[0]
            id_strings = []
            _device = getattr(_ad, "_device", None)
            if _device:
                dev_alias = getattr(_device, "device_id", "")
                if dev_alias:
                    id_strings.append(dev_alias)
            dev_sn = getattr(_ad, "device_sn", "")
            if dev_sn:
                id_strings.append(convert_serial(dev_sn))
            name_id = ".".join(id_strings).replace(" ", ".")
        except Exception as exception:
            log.error(exception)
        args = args[1:]
    if name_id is not None:
        all_args.append(name_id)
    if args:
        for arg in args:
            all_args.append(str(arg))
    if kwargs:
        for key, value in kwargs.items():
            all_args.append("{}={}".format(key, value))
    info_items = [
        func.__module__.split(".")[-1:][0], ".", func.__name__,
        "(", ", ".join(all_args), ")"
    ]
    return "".join(info_items)


def GET_TRACEBACK(_trac=""):
    if _trac == "AW":
        return "".join(traceback.format_exception(*sys.exc_info())), \
            traceback.format_exception(*sys.exc_info())[-1].strip()
    return "".join(traceback.format_exception(*sys.exc_info()))


def ASSERT(expect, actual):
    if expect != actual:
        raise TestFailure(ErrorMessage.Assertion.Code_0204026.format(expect, actual))


def CHECK(message, expect, actual):
    if DeccVariable.cur_case() is None:
        cur_case = CurCase(log)
        DeccVariable.set_cur_case_obj(cur_case)
        return
    MESSAGE(message)
    EXPECT(expect)
    ACTUAL(actual)


def MESSAGE(arg):
    if DeccVariable.cur_case() is None:
        cur_case = CurCase(log)
        DeccVariable.set_cur_case_obj(cur_case)
        return
    DeccVariable.cur_case().cur_check_cmd.through = get_decode(arg)
    log.debug("Description: {}".format(
        DeccVariable.cur_case().cur_check_cmd.through))


def EXPECT(arg):
    if DeccVariable.cur_case() is None:
        cur_case = CurCase(log)
        DeccVariable.set_cur_case_obj(cur_case)
        return
    DeccVariable.cur_case().cur_check_cmd.expect = get_decode(arg)
    log.debug("Expected: {}".format(
        DeccVariable.cur_case().cur_check_cmd.expect))


def ACTUAL(arg):
    if DeccVariable.cur_case() is None:
        cur_case = CurCase(log)
        DeccVariable.set_cur_case_obj(cur_case)
        return
    DeccVariable.cur_case().cur_check_cmd.actual = get_decode(arg)
    log.debug("Actual: {}".format(
        DeccVariable.cur_case().cur_check_cmd.actual))


def Step(name, **kwargs):
    """记录用例操作步骤，并展示在用例报告里
    Args:
        name: str, step name
    Example:
        Step("11")
        Step("11", video="a video address")
    """
    cur_case = DeccVariable.cur_case()
    if cur_case is None:
        log.warning("current case object is none, recording step failed")
        return -1
    return cur_case.set_step_info(name, **kwargs)


def UpdateStep(index, **kwargs):
    """更新步骤记录信息
    Args:
        index: int, step index
    Example:
        index = Step("11")
        UpdateStep(index, video="a video address")
    """
    cur_case = DeccVariable.cur_case()
    if cur_case is None:
        log.warning("current case object is none, updating step failed")
        return
    cur_case.update_step_info(index, **kwargs)


def CheckPoint(checkpoint):
    Step(checkpoint)


def CONFIG():
    return DeccVariable.project.config_json


def get_report_dir(self=None):
    """
    get Path to the framework execution case log folder
    Returns: log_dir_path
    """
    if isinstance(self, TestCase):
        return self.project.task_report_dir
    return DeccVariable.project.task_report_dir


def RecordStep(name, **kwargs):
    """记录用例操作步骤，并展示在用例报告里
    name: str, step name, 作为唯一标识，用于更新记录
    Example:
        RecordStep("11", result=True)
        RecordStep("11", result=True, video="a video address")
    """
    warnings.warn("RecordStep is deprecated, use Step instead", DeprecationWarning)
    cur_case = DeccVariable.cur_case()
    if cur_case is None:
        log.warning("current case object is none, recording step failed")
        return
    cur_case.set_step_info(name, **kwargs)


class Property:

    def __init__(self):
        pass

    def add_attributes(self, key, value):
        setattr(self, key, value)
        log.debug("Property setattr {}={}".format(key, value))
