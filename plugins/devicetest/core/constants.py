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

class DTConstants:
    FAILED = 'failed'
    PASSED = 'passed'


class RunSection:
    SETUP = "SETUP"
    TEST = "TEST"
    TEARDOWN = "TEARDOWN"


class RunStatus:
    INITING = "Initing"
    RUNNING = "Running"
    STOPPED = "Stopped"
    FINISHED = "Finished"


class RunResult:
    PASSED = "Passed"
    FAILED = "Failed"
    BLOCKED = "Blocked"
    NORUN = "NORUN"


class FileAttribute:
    TESTCASE_PREFIX = "TC_"
    TESTCASE_POSFIX_PY = ".py"
    TESTCASE_POSFIX_PYC = ".pyc"
    TESTCASE_POSFIX_PYD = ".pyd"


class DeviceConstants:
    RECONNECT_TIMES = 3  # 断链，默认重连次数
    HOST = os.environ.get('AP_HOST', "127.0.0.1")
    PORT = os.environ.get('AP_PORT', 9999)
    OH_DEVICETEST_BUNDLE_NAME = "com.ohos.devicetest."
    RES_VERSION = "002"


class DeviceTestMode:
    MODE = "device_test_mode"
    HYPIUM_PERF_TEST = "hypium_perf_test"
