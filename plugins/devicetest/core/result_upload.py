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
from devicetest.core.constants import RunResult
from devicetest.core.error_message import ErrorMessage
from devicetest.core.exception import DeviceTestError
from devicetest.core.report import ReportHandler
from devicetest.log.logger import DeviceTestLog as log
from xdevice import SuiteReporter


class UploadResultHandler:

    def __init__(self, report_path):
        self.__log = log
        self.__test_runner = None
        self.__report_path = None
        self.__upload_suitereporter_lock = False
        self.report_handler = ReportHandler(report_path)

    def set_test_runner(self, _log, test_runner):
        self.__log = _log
        self.__test_runner = test_runner
        self.__log.info("finish set test runner.")

    def get_error_msg(self, test_runner, is_cur_case_error=False):
        if test_runner.project.record.get_is_manual_stop_status():
            error_msg = ErrorMessage.Error_01300.Topic if is_cur_case_error \
                else ErrorMessage.Error_01301.Topic

        else:
            error_msg = ErrorMessage.Error_01400.Topic if is_cur_case_error \
                else ErrorMessage.Error_01404.Topic
        return error_msg

    def flash_os_test_results(self, test_runner, test_results):
        cur_case_error_msg = self.get_error_msg(test_runner,
                                                is_cur_case_error=True)
        if not test_results:
            test_result = test_runner.record_cls_result(
                test_runner.project.execute_case_name,
                error=cur_case_error_msg)
            test_results.append(test_result)
        else:
            if test_results[-1].get("result").strip() == RunResult.FAILED \
                    and not test_results[0].get("error").strip():
                test_results[0]["error"] = cur_case_error_msg
        return test_results

    def upload_suite_reporter(self, test_results=None):
        report_result_tuple = self.report_handler.generate_test_report(
            self.__test_runner, test_results)
        SuiteReporter.append_report_result(report_result_tuple)
        self.__log.debug("result tuple:{}".format(report_result_tuple))
        self.__log.info("upload suitereporter success.")

    def upload_suitereporter(self, is_stoped=False):
        try:
            self.upload_suite_reporter()
        except DeviceTestError as err:
            log.error(err)
        except Exception:
            self.__log.error(ErrorMessage.Error_01427.Message.en,
                             error_no=ErrorMessage.Error_01427.Code,
                             is_traceback=True)
