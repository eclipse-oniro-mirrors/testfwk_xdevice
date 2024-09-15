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
from devicetest.core.exception import DeviceTestError
from devicetest.core.report import ReportHandler
from devicetest.error import ErrorMessage
from devicetest.log.logger import DeviceTestLog as Log
from xdevice import SuiteReporter


class UploadResultHandler:

    def __init__(self, report_path):
        self.__test_runner = None
        self.__report_path = None
        self.__upload_suitereporter_lock = False
        self.report_handler = ReportHandler(report_path)

    def set_test_runner(self, test_runner):
        self.__test_runner = test_runner
        Log.info("set test runner finish")

    def get_error_msg(self, test_runner, is_cur_case_error=False):
        return ErrorMessage.Common.Code_0201004

    def flash_os_test_results(self, test_runner, test_results):
        cur_case_error_msg = self.get_error_msg(test_runner,
                                                is_cur_case_error=True)
        if not test_results:
            test_result = test_runner.record_cls_result(
                test_runner.project.execute_case_name, None, None, None, cur_case_error_msg)
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
        Log.debug("result tuple:{}".format(report_result_tuple))
        Log.info("upload suitereporter success.")

    def upload_suitereporter(self, is_stoped=False):
        try:
            self.upload_suite_reporter()
        except DeviceTestError as err:
            Log.error(err)
        except Exception:
            Log.error(ErrorMessage.Common.Code_0201003, is_traceback=True)
