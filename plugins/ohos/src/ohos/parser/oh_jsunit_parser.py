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

from ohos.parser import *
from ohos.executor.bean import StackStateRecorder
from ohos.parser.constants import StatusCodes

__all__ = ["OHJSUnitTestParser", "OHJSUnitTestListParser"]

LOG = platform_logger("OHJSUnitTestParser")


class OHJSUnitPrefixes(Enum):
    SUM = "OHOS_REPORT_SUM: "
    STATUS = "OHOS_REPORT_STATUS: "
    STATUS_CODE = "OHOS_REPORT_STATUS_CODE: "
    RESULT = "OHOS_REPORT_RESULT: "
    CODE = "OHOS_REPORT_CODE: "
    TEST_FINISHED_RESULT_MSG = "TestFinished-ResultMsg: "
    COVERAGE_PATH = "OHOS_REPORT_COVERAGE_PATH: "
    WORKER_STATUS = "OHOS_REPORT_WORKER_STATUS: "


class OHJSUnitItemConstants(Enum):
    CLASS = "class"
    TEST = "test"
    NUM_TESTS = "numtests"
    STACK = "stack"
    STREAM = "stream"
    SUITE_CONSUMING = "suiteconsuming"
    CONSUMING = "consuming"
    APP_DIED = "App died"


@Plugin(type=Plugin.PARSER, id=CommonParserType.oh_jsunit)
class OHJSUnitTestParser(IParser):

    def __init__(self):
        self.state_machine = StackStateRecorder()
        self.suites_name = ""
        self.listeners = []
        self.current_key = None
        self.current_value = None
        self.start_time = get_cst_time()
        self.suite_start_time = get_cst_time()
        self.test_time = 0
        self.test_run_finished = False
        self.cur_sum = -1
        self.runner = None
        self.result_data = ""
        self.listener_result_info_tuple = None

        # message from test output, the 'TestFinished-ResultMsg'
        self.__test_finish_result_msg = ""

    def get_suite_name(self):
        return self.suites_name

    def get_listeners(self):
        return self.listeners

    def __process__(self, lines):
        for line in lines:
            line = str(line).strip().rstrip("\r")
            LOG.debug(line)
            self.parse(line)

    def parse(self, line):
        if not str(line).strip():
            return
        if OHJSUnitPrefixes.SUM.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.SUM.value):]
            self.handle_sum_line(new_line)
        elif OHJSUnitPrefixes.STATUS.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.STATUS.value):]
            self.handle_status_line(new_line)
        elif OHJSUnitPrefixes.STATUS_CODE.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.STATUS_CODE.value):]
            self.submit_current_key_value()
            self.parse_status_code(new_line)
        elif OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value):]
            self._handle_result_msg(new_line)
        elif OHJSUnitPrefixes.COVERAGE_PATH.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.COVERAGE_PATH.value):]
            self._handle_coverage_path_msg(new_line)

    def _handle_coverage_path_msg(self, line):
        value = line[len(OHJSUnitPrefixes.COVERAGE_PATH.value):].strip()
        self.runner.coverage_data_path = "{}".format(value)

    def handle_sum_line(self, line):
        value = line[len(OHJSUnitPrefixes.SUM.value):].split("=", 1)[0]
        self.cur_sum = int(value)

    def handle_status_line(self, line):
        self.parse_key(line, len(OHJSUnitPrefixes.STATUS.value))
        if self.cur_sum > 0 and \
                self.current_key == OHJSUnitItemConstants.CLASS.value:
            current_suite = self.state_machine.suite(reset=True)
            current_suite.test_num = self.cur_sum
            current_suite.suite_name = self.current_value
            self.state_machine.current_suite = current_suite
            self.cur_sum = -1
            self.current_key = None
            self.current_value = None
            self.state_machine.running_test_index = 0
            self.suite_start_time = get_cst_time()
            for listener in self.get_listeners():
                suite = copy.copy(current_suite)
                listener.__started__(LifeCycle.TestSuite, suite)
        else:
            if self.current_key == OHJSUnitItemConstants.SUITE_CONSUMING.value:
                self.test_time = int(self.current_value)
                self.handle_suite_end()
            elif self.current_key == OHJSUnitItemConstants.CONSUMING.value:
                self.test_time = int(self.current_value)
                self.handle_case_end()
            else:
                self.submit_current_key_value()
                self.parse_key(line, len(OHJSUnitPrefixes.STATUS.value))

    def submit_current_key_value(self):
        if self.current_key and self.current_value:
            status_value = self.current_value
            test_info = self.state_machine.test()
            if self.current_key == OHJSUnitItemConstants.CLASS.value:
                test_info.test_class = status_value
            elif self.current_key == OHJSUnitItemConstants.TEST.value:
                test_info.test_name = status_value
            elif self.current_key == OHJSUnitItemConstants.NUM_TESTS.value:
                test_info.num_tests = int(status_value)
            elif self.current_key == OHJSUnitItemConstants.STREAM.value:
                test_info.stacktrace = status_value
            self.current_key = None
            self.current_value = None

    def parse_key(self, line, key_start_pos):
        key_value = line[key_start_pos:].split("=", 1)
        if len(key_value) == 2:
            self.current_key = key_value[0]
            self.current_value = key_value[1]

    def parse_status_code(self, line):
        value = line[len(OHJSUnitPrefixes.STATUS_CODE.value):]
        test_info = self.state_machine.test()
        test_info.code = int(value)
        if test_info.code != StatusCodes.IN_PROGRESS:
            if self.check_legality(test_info.test_class) and \
                    self.check_legality(test_info.test_name):
                self.report_result(test_info)

    def clear_current_test_info(self):
        self.state_machine.current_test = None

    def report_result(self, test_info):
        if not test_info.test_name or not test_info.test_class:
            LOG.info("Invalid instrumentation status bundle")
            return
        if test_info.code == StatusCodes.START.value:
            self.start_time = get_cst_time()
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                listener.__started__(LifeCycle.TestCase, result)
            return
        if test_info.code == StatusCodes.FAILURE.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.FAILED.value
        elif test_info.code == StatusCodes.ERROR.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.FAILED.value
        elif test_info.code == StatusCodes.SUCCESS.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.PASSED.value

    @classmethod
    def output_stack_trace(cls, test_info):
        if check_pub_key_exist():
            return
        if test_info.stacktrace:
            stack_lines = test_info.stacktrace.split(r"\r\n")
            LOG.error("Stacktrace information is:")
            for line in stack_lines:
                line.strip()
                if line:
                    LOG.error(line)

    @staticmethod
    def check_legality(name):
        if not name or name == "null":
            return False
        return True

    def __done__(self):
        pass

    def handle_case_end(self):
        test_info = self.state_machine.test()
        if not test_info.test_name or not test_info.test_class:
            LOG.warning("Test case name or class is invalid. test_name: {}, test_class: {}"
                        .format(test_info.test_name, test_info.test_class))
            return
        if test_info.run_time == 0 or test_info.run_time < self.test_time:
            test_info.run_time = self.test_time
        test_info.is_completed = True
        for listener in self.get_listeners():
            result = copy.copy(test_info)
            result.code = test_info.code
            listener.__ended__(LifeCycle.TestCase, result)
            if not self._is_target_listener(listener):
                continue
            if self.runner.retry_times > 1 and result.code == ResultCode.FAILED.value:
                listener.tests.pop(test_info.index)
        self.clear_current_test_info()

    def handle_suite_end(self):
        if self.state_machine.is_suite_empty():
            return
        suite_result = self.state_machine.pop_last_suite()
        suite_result.run_time = get_delta_time_ms(self.suite_start_time)
        if suite_result.run_time == 0:
            suite_result.run_time = self.test_time
        suite_result.is_completed = True
        for listener in self.get_listeners():
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def handler_suites_end(self):
        suite_result = None
        if not self.state_machine.is_suite_empty():
            suite_result = self.state_machine.suite()
            if not suite_result.is_completed:
                self.handle_suite_end()
            self.state_machine.pop_last_suite()
        for listener in self.get_listeners():
            if self._is_target_listener(listener):
                self._cal_result(listener)
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuites, suite, suites_name=self.suites_name,
                               message=self.__test_finish_result_msg)

    def _cal_result(self, report_listener):
        result_len = len(report_listener.result)  # List[Tuple]
        suites_len = len(report_listener.suites)
        if result_len > suites_len:
            ids_in_suites = [_id for _id in report_listener.suites.keys()]
            ids_in_result = [_id for _id in report_listener.suite_distributions.keys()]
            #  对比差异id
            diff_id_list = list(set(ids_in_result).symmetric_difference(set(ids_in_suites)))
            for diff_id in diff_id_list:  # 根据id进行遍历
                cur_suite = report_listener.suites.get(diff_id)
                pos = report_listener.suite_distributions.get(cur_suite.index)
                case_result_list = report_listener.result[pos]
                report_listener.result[pos][1].extend(case_result_list)
        self._handle_lacking_one_testcase(report_listener)
        self._handle_lacking_whole_suite(report_listener)

    def _handle_lacking_one_testcase(self, report_listener):
        for suite in report_listener.suites.values():
            test_des_list = self.runner.expect_tests_dict.get(
                suite.suite_name, [])
            pos = report_listener.suite_distributions.get(suite.index)
            list_in_result = report_listener.result[pos][1]
            if len(test_des_list) == len(list_in_result):
                continue
            interval = len(test_des_list) - len(list_in_result)
            if len(test_des_list) > 0:
                LOG.info("{} tests in {} had missed".format(
                    interval, suite.suite_name))
            else:
                LOG.info("The count of tests in '{}' is incorrect! {} tests "
                         "from dry run and {} tests have run."
                         "".format(suite.suite_name, len(test_des_list),
                                   len(list_in_result)))
            for test_des in test_des_list:
                is_contain = False
                for case in list_in_result:
                    if case.test_name == test_des.test_name:
                        is_contain = True
                        break
                if not is_contain:
                    test_result = self.state_machine.test(reset=True)
                    test_result.test_class = test_des.class_name
                    test_result.test_name = test_des.test_name
                    test_result.stacktrace = self.__test_finish_result_msg or "error_msg: mark blocked"
                    test_result.num_tests = 1
                    test_result.run_time = 0
                    test_result.current = \
                        self.state_machine.running_test_index + 1
                    test_result.code = ResultCode.BLOCKED.value
                    list_in_result.append(test_result)
                    LOG.debug("Add {}#{}".format(test_des.class_name,
                                                 test_des.test_name))

    def _handle_lacking_whole_suite(self, report_listener):
        all_suite_set = set(self.runner.expect_tests_dict.keys())
        un_suite_set = set()
        if len(all_suite_set) > len(report_listener.suites):
            suite_name_set = set()
            for suite in report_listener.suites.values():
                suite_name_set.add(suite.suite_name)
            un_suite_set = all_suite_set.difference(suite_name_set)
        if un_suite_set:
            LOG.info("{} suites have missed".format(len(un_suite_set)))
        for name in un_suite_set:
            self.state_machine.running_test_index = 0
            test_des_list = self.runner.expect_tests_dict.get(
                name, [])
            current_suite = self.state_machine.suite(reset=True)
            current_suite.test_num = len(test_des_list)
            current_suite.suite_name = name
            for listener in self.get_listeners():
                suite = copy.copy(current_suite)
                listener.__started__(LifeCycle.TestSuite, suite)

            for test in test_des_list:
                test_result = self.state_machine.test(reset=True)
                test_result.test_class = test.class_name
                test_result.test_name = test.test_name
                test_result.stacktrace = self.__test_finish_result_msg or "error_msg: mark blocked"
                test_result.num_tests = 1
                test_result.run_time = 0
                test_result.current = self.state_machine.running_test_index + 1
                test_result.code = ResultCode.BLOCKED.value
                test_result = copy.copy(test_result)
                for listener in self.get_listeners():
                    listener.__started__(LifeCycle.TestCase, test_result)
                test_result = copy.copy(test_result)
                for listener in self.get_listeners():
                    listener.__ended__(LifeCycle.TestCase, test_result)

                self.state_machine.running_test_index += 1
            current_suite.run_time = self.test_time
            current_suite.is_completed = True
            for listener in self.get_listeners():
                suite = copy.copy(current_suite)
                listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def notify_task_finished(self):
        self.handler_suites_end()

    def _handle_result_msg(self, line):
        is_app_died = OHJSUnitItemConstants.APP_DIED.value in line
        if is_app_died:
            self.__test_finish_result_msg = line.replace(OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value, '')
        if is_app_died and not self.state_machine.is_suite_empty():
            test_result = self.state_machine.test()
            suite = self.state_machine.suite()
            if not test_result.is_completed:
                if self.check_legality(test_result.test_class) and \
                        self.check_legality(test_result.test_name):
                    self.report_result(test_result)
                    self.clear_current_test_info()
            if not suite.is_completed:
                self.handle_suite_end()

    @classmethod
    def _is_target_listener(cls, listener):
        return listener.__class__.__name__ == "StackReportListener"


@Plugin(type=Plugin.PARSER, id=CommonParserType.oh_jsunit_list)
class OHJSUnitTestListParser(IParser):

    def __init__(self):
        self.tests = []
        self.json_str = ""
        self.tests_dict = dict()
        self.result_data = ""

    def __process__(self, lines):
        for line in lines:
            line = str(line).strip().rstrip("\r")
            self.result_data = "{}{}".format(self.result_data, line)
            self.parse(line)

    def __done__(self):
        LOG.debug("OHJSTestListParser data:")
        LOG.debug(self.result_data)
        self.result_data = ""

    def parse(self, line):
        if "{" in line or "}" in line:
            self.json_str = "%s%s" % (self.json_str, line)
            return
        if "dry run finished" in line:
            suite_dict_list = json.loads(self.json_str).get("suites", [])
            for suite_dict in suite_dict_list:
                for class_name, test_name_dict_list in suite_dict.items():
                    self.tests_dict.update({class_name.strip(): []})
                    for test_name_dict in test_name_dict_list:
                        for test_name in test_name_dict.values():
                            test = TestDescription(class_name.strip(),
                                                   test_name.strip())
                            self.tests_dict.get(
                                class_name.strip()).append(test)
                            self.tests.append(test)


@Plugin(type=Plugin.PARSER, id=CommonParserType.worker)
class OHJSWorkParser(IParser):
    def __init__(self):
        self.state_machine = StackStateRecorder()
        self.suites_name = ""
        self.listeners = []
        self.current_key = None
        self.current_value = None
        self.start_time = get_cst_time()
        self.suite_start_time = get_cst_time()
        self.test_time = 0
        self.cur_sum = 0
        self.runner = None
        self.worker_suites = dict()
        self.worker_cases = dict()
        self.all_result_dict = dict()
        self.temp_class = None
        self.temp_test = None

        # message from test output, the 'TestFinished-ResultMsg'
        self.__test_finish_result_msg = ""

    def __process__(self, lines):
        for line in lines:
            line = str(line).strip().rstrip("\r")
            LOG.debug(line)
            self.parse(line)

    def parse(self, line):
        if not str(line).strip():
            return
        if OHJSUnitPrefixes.SUM.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.SUM.value):]
            self.handle_sum_line(new_line)
        elif OHJSUnitPrefixes.STATUS.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.STATUS.value):]
            self.handle_status_line(new_line)
        elif OHJSUnitPrefixes.STATUS_CODE.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.STATUS_CODE.value):]
            self.submit_current_key_value()
            self.parse_status_code(new_line)
        elif OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value in line:
            new_line = line[line.index(OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value):]
            self._handle_result_msg(new_line)
        elif OHJSUnitPrefixes.WORKER_STATUS.value in line:
            self.parse_key(line, len(OHJSUnitPrefixes.WORKER_STATUS.value))
            self._handle_all_result()

    def submit_current_key_value(self):
        if self.current_key and self.current_value:
            status_value = self.current_value
            test_info = self.state_machine.test()
            if self.current_key == "class":
                test_info.test_class = status_value
            elif self.current_key == "test":
                test_info.test_name = status_value
            elif self.current_key == "numtests":
                test_info.num_tests = int(status_value)
            elif self.current_key == "Error":
                self.handle_test_run_failed(status_value)
            elif self.current_key == "stack":
                test_info.stacktrace = status_value
            elif self.current_key == "stream":
                pass
            self.current_key = None
            self.current_value = None

    def parse_status_code(self, line):
        value = line[len(OHJSUnitPrefixes.STATUS_CODE.value):]
        test_info = self.state_machine.test()
        test_info.code = int(value)
        if test_info.code != StatusCodes.IN_PROGRESS:
            if self.check_legality(test_info.test_class) and \
                    self.check_legality(test_info.test_name):
                self.report_result(test_info)

    @staticmethod
    def check_legality(name):
        if not name or name == "null":
            return False
        return True

    def report_result(self, test_info):
        if not test_info.test_name or not test_info.test_class:
            LOG.info("Invalid instrumentation status bundle")
            return
        if test_info.code == StatusCodes.START.value:
            self.start_time = get_cst_time()
            for listener in self.get_listeners():
                result = copy.copy(test_info)
                if self._is_target_listener(listener):
                    continue
                listener.__started__(LifeCycle.TestCase, result)
        if test_info.code == StatusCodes.FAILURE.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.FAILED.value
        elif test_info.code == StatusCodes.ERROR.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.FAILED.value
        elif test_info.code == StatusCodes.SUCCESS.value:
            self.state_machine.running_test_index += 1
            test_info.current = self.state_machine.running_test_index
            run_time = get_delta_time_ms(self.start_time)
            test_info.run_time = run_time
            test_info.code = ResultCode.PASSED.value

    def parse_key(self, line, key_start_pos):
        key_value = line[key_start_pos:].split("=", 1)
        if len(key_value) == 2:
            self.current_key = key_value[0]
            self.current_value = key_value[1]

    def handle_sum_line(self, line):
        value = line[len(OHJSUnitPrefixes.SUM.value):].split("=", 1)[0]
        self.cur_sum = int(value)

    def handle_status_line(self, line):
        self.parse_key(line, len(OHJSUnitPrefixes.STATUS.value))
        if self.cur_sum > 0 and self.current_key == OHJSUnitItemConstants.CLASS.value:
            current_suite = self.state_machine.suite(reset=True)
            self.worker_suites.update({self.current_value: current_suite})
            current_suite.test_num = self.cur_sum
            current_suite.suite_name = self.current_value
            self.state_machine.current_suite = current_suite
            self.cur_sum = -1
            self.current_key = None
            self.current_value = None
            self.state_machine.running_test_index = 0
            for listener in self.get_listeners():
                suite = copy.copy(current_suite)
                if self._is_target_listener(listener):
                    continue
                listener.__started__(LifeCycle.TestSuite, suite)
        else:
            if self.current_key == OHJSUnitItemConstants.SUITE_CONSUMING.value:
                self.test_time = int(self.current_value)
                self.handle_suite_end()
            elif self.current_key == OHJSUnitItemConstants.CONSUMING.value:
                # test case end
                self.test_time = int(self.current_value)
                self.handle_case_end()
            else:
                # test case
                self.submit_current_key_value()
                self.parse_key(line, len(OHJSUnitPrefixes.STATUS.value))

    def _handle_result_msg(self, line):
        is_app_died = OHJSUnitItemConstants.APP_DIED.value in line
        if is_app_died:
            self.__test_finish_result_msg = line.replace(OHJSUnitPrefixes.TEST_FINISHED_RESULT_MSG.value, '')
        if is_app_died and not self.state_machine.is_suite_empty():
            test_result = self.state_machine.test()
            suite = self.state_machine.suite()
            if not test_result.is_completed:
                if self.check_legality(test_result.test_class) and \
                        self.check_legality(test_result.test_name):
                    self.report_result(test_result)
                    self.clear_current_test_info()
            if not suite.is_completed:
                self.handle_suite_end()

    def handle_suite_end(self):
        if self.state_machine.is_suite_empty():
            return
        suite_result = self.state_machine.pop_last_suite()
        suite_result.run_time = get_delta_time_ms(self.suite_start_time)
        if suite_result.run_time == 0:
            suite_result.run_time = self.test_time
        suite_result.is_completed = True
        for listener in self.get_listeners():
            if self._is_target_listener(listener):
                continue
            suite = copy.copy(suite_result)
            listener.__ended__(LifeCycle.TestSuite, suite, is_clear=True)

    def handle_case_end(self):
        test_info = self.state_machine.test()
        if not test_info.test_name or not test_info.test_class:
            LOG.warning("Test case name or class is invalid. test_name: {}, test_class: {}"
                        .format(test_info.test_name, test_info.test_class))
            return
        if test_info.run_time == 0 or test_info.run_time < self.test_time:
            test_info.run_time = self.test_time
        for listener in self.get_listeners():
            if self._is_target_listener(listener):
                continue
            result = copy.copy(test_info)
            result.code = test_info.code
            listener.__ended__(LifeCycle.TestCase, result)

        test_info.is_completed = True
        key_tuple = (test_info.test_class, test_info.test_name)
        self.worker_cases.update({key_tuple: test_info})
        self.clear_current_test_info()

    def __done__(self):
        pass

    @classmethod
    def _is_target_listener(cls, listener):
        return listener.__class__.__name__ == "StackReportListener"

    @classmethod
    def _is_log_listener(cls, listener):
        return listener.__class__.__name__ == "LogListener"

    def get_listeners(self):
        return self.listeners

    def clear_current_test_info(self):
        self.state_machine.current_test = None

    def notify_task_finished(self):
        self.handler_suites_end()

    def handler_suites_end(self):
        target_listener = None
        for listener in self.get_listeners():
            if self._is_target_listener(listener):
                target_listener = listener
                break
        self.handle_suite_result(target_listener)
        suite_result = None
        if not self.state_machine.is_suite_empty():
            suite_result = self.state_machine.suite()
            if not suite_result.is_completed:
                self.handle_suite_end()
            self.state_machine.pop_last_suite()
        target_listener.__ended__(LifeCycle.TestSuites, suite_result, suites_name=self.suites_name,
                                  message=self.__test_finish_result_msg)

    def handle_suite_result(self, target_listener):
        for suite_name, test_info_list in self.all_result_dict.items():
            current_suite = self.state_machine.suite(reset=True)
            current_suite.suite_name = suite_name
            self.state_machine.running_test_index = 0

            name_list = self.runner.expect_tests_dict.get(suite_name, [])
            expect_case_name_list = [test_des.test_name for test_des in name_list]
            current_suite.test_num = len(expect_case_name_list) \
                if len(expect_case_name_list) > 0 else len(test_info_list)

            target_listener.__started__(LifeCycle.TestSuite, current_suite)
            for test_name, status in test_info_list:
                case = self.state_machine.test(reset=True)
                case.test_name = test_name
                case.test_class = suite_name
                case.code = ResultCode(status).value
                case.num_tests = len(expect_case_name_list)
                case.run_time = 0
                case.current = \
                    self.state_machine.running_test_index + 1
                self.state_machine.running_test_index += 1

                target_listener.__started__(LifeCycle.TestCase, case)
                target_listener.__ended__(LifeCycle.TestCase, case)
                if case.test_name in expect_case_name_list:
                    expect_case_name_list.remove(case.test_name)
                else:
                    LOG.debug("Extra casa {}#{}".format(suite_name, case.test_name))
            if expect_case_name_list:
                for case_name in expect_case_name_list:
                    test_result = self.state_machine.test(reset=True)
                    test_result.test_class = suite_name
                    test_result.test_name = case_name
                    test_result.stacktrace = self.__test_finish_result_msg or "error_msg: mark blocked"
                    test_result.num_tests = 1
                    test_result.run_time = 0
                    test_result.current = \
                        self.state_machine.running_test_index + 1
                    test_result.code = ResultCode.BLOCKED.value
                    LOG.debug("Add {}#{}".format(suite_name,
                                                 case_name))
            target_listener.__ended__(LifeCycle.TestSuite, current_suite, is_clear=True)

    def _handle_all_result(self):
        if not self.current_key or not self.current_value:
            return
        if self.current_key == "class":
            self.temp_class = self.current_value
            if self.current_value not in self.all_result_dict.keys():
                self.all_result_dict.update({self.current_value: []})
        elif self.current_key == "test":
            self.temp_test = self.current_value
        elif self.current_key == "CODE":
            code = self._covert_code(self.current_value)
            self.all_result_dict.get(self.temp_class).append((self.temp_test, code))
            self.temp_class = None
            self.temp_test = None

    @classmethod
    def _covert_code(cls, code):
        if code == str(StatusCodes.FAILURE.value):
            return ResultCode.FAILED.value
        elif code == str(StatusCodes.ERROR.value):
            return ResultCode.FAILED.value
        elif code == str(StatusCodes.SUCCESS.value):
            return ResultCode.PASSED.value
        else:
            return ResultCode.FAILED.value
