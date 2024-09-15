#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2023 Huawei Device Co., Ltd.
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
from _core.logger import add_task_file_handler
from _core.logger import remove_task_file_handler
from _core.logger import add_encrypt_file_handler
from _core.logger import remove_encrypt_file_handler
from _core.report.encrypt import check_pub_key_exist
from _core.report.reporter_helper import ReportConstant


__all__ = ["RuntimeLogs"]


class RuntimeLogs:

    @staticmethod
    def start_task_log(log_path):
        tool_file_name = ReportConstant.task_run_log
        tool_log_file = os.path.join(log_path, tool_file_name)
        add_task_file_handler(tool_log_file)

    @staticmethod
    def start_encrypt_log(log_path):
        if check_pub_key_exist():
            encrypt_file_name = "task_log.ept"
            encrypt_log_file = os.path.join(log_path, encrypt_file_name)
            add_encrypt_file_handler(encrypt_log_file)

    @staticmethod
    def stop_task_logcat():
        remove_task_file_handler()

    @staticmethod
    def stop_encrypt_log():
        if check_pub_key_exist():
            remove_encrypt_file_handler()
