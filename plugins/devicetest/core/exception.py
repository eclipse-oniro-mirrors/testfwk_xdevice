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

class TestAssertionError(Exception):
    """
    devicetest defined assertion class
    """

    def __init__(self, error_msg):
        super(TestAssertionError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class RPCException(Exception):
    def __init__(self, error_msg):
        super(RPCException, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class RPCAPIError(RPCException):
    """Raised when remote API reports an error."""

    def __init__(self, error_msg):
        super(RPCAPIError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeccAgentError(Exception):
    def __init__(self, error_msg):
        super(DeccAgentError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceTestError(Exception):
    def __init__(self, error_msg):
        super(DeviceTestError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class BaseTestError(Exception):
    """Raised for exceptions that occured in BaseTestClass.
    """

    def __init__(self, error_msg):
        super(BaseTestError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestFailure(Exception):
    """Raised when a check has failed."""

    def __init__(self, error_msg):
        super(TestFailure, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestError(Exception):
    """Raised when a step has failed."""

    def __init__(self, error_msg):
        super(TestError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestSkip(Exception):
    """Raised when a test has been skipped."""

    def __init__(self, error_msg):
        super(TestSkip, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestTerminated(Exception):
    """Raised when a test has been stopped."""

    def __init__(self, error_msg):
        super(TestTerminated, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestAbortManual(Exception):
    """Raised when a manual abort occurs."""

    def __init__(self, error_msg):
        super(TestAbortManual, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class TestPrepareError(Exception):
    """raise exception when prepare error."""

    def __init__(self, error_msg):
        super(TestPrepareError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceNotFound(Exception):
    """raise exception when device not found."""

    def __init__(self, error_msg):
        super(DeviceNotFound, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceTestAppInstallError(Exception):
    """
    Failed to install the APP
    """

    def __init__(self, error_msg):
        super(DeviceTestAppInstallError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceTestRpcNotRunningError(Exception):
    """
    RPC not running
    """

    def __init__(self, error_msg):
        super(DeviceTestRpcNotRunningError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceTestHdcCommandRejectedException(Exception):
    """
    Failed to connect to the device:The device goes offline
    """

    def __init__(self, error_msg):
        super(DeviceTestHdcCommandRejectedException, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DeviceTestShellCommandUnresponsiveException(Exception):
    """
    Running the connector command times out
    """

    def __init__(self, error_msg):
        super(DeviceTestShellCommandUnresponsiveException,
              self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class DoesNotExistError(Exception):
    """
    Viewnode is none
    """

    def __init__(self, error_msg):
        super(DoesNotExistError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class CreateUiDriverFailError(Exception):

    def __init__(self, error_msg):
        super(CreateUiDriverFailError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class ConnectAccessibilityFailError(Exception):

    def __init__(self, error_msg):
        super(ConnectAccessibilityFailError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


class ModuleNotAttributeError(Exception):
    def __init__(self, error_msg):
        super(ModuleNotAttributeError, self).__init__(error_msg)
        self.error_msg = error_msg

    def __str__(self):
        return str(self.error_msg)


try:
    from xdevice import HdcCommandRejectedException
except ImportError:
    HdcCommandRejectedException = DeviceTestHdcCommandRejectedException
try:
    from xdevice import \
        ShellCommandUnresponsiveException
except ImportError:
    ShellCommandUnresponsiveException = \
        DeviceTestShellCommandUnresponsiveException
try:
    from xdevice import AppInstallError
except ImportError:
    AppInstallError = DeviceTestAppInstallError

try:
    from xdevice import RpcNotRunningError
except ImportError:
    RpcNotRunningError = DeviceTestRpcNotRunningError
