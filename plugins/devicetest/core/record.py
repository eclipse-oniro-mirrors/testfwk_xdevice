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

from devicetest.core.exception import TestTerminated
from devicetest.error import ErrorMessage


class DeviceTestRecord:
    is_aborted = False  # 初始值为False,DeviceTest过程执行异常置为True


class ProjectRecord:
    def __init__(self, log):
        # 记录工程执行状态的全局变量
        self.log = log
        self.is_aborted = False  # 初始值为False,DeviceTest过程执行异常置为True
        self.is_upload_suitereporter = False

    def is_shutdown(self, raise_exception=True):
        if self.is_aborted:
            err_msg = ErrorMessage.Common.Code_0201004
            self.log.error(err_msg)
            if raise_exception:
                raise TestTerminated(err_msg)
            return True

        return False

    def set_is_upload_suitereporter_status(self, status):
        self.is_upload_suitereporter = status
        self.log.info(
            "set is upload suitereporter status as: {}".format(status))
