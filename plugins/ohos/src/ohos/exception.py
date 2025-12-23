#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2022 Huawei Device Co., Ltd.
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
from xdevice import HdcError
from xdevice import RpcNotRunningError

__all__ = ["LiteDeviceConnectError", "LiteDeviceTimeout", "LiteParamError",
           "LiteDeviceError", "LiteDeviceExecuteCommandError",
           "LiteDeviceMountError", "LiteDeviceReadOutputError", "OHOSRpcNotRunningError", "HDCFPortError",
           "OHOSRpcStartFailedError", "OHOSRpcPortNotFindError", "OHOSRpcProcessNotFindError",
           "OHOSDeveloperModeNotTrueError", "OHOSProxyInitFailed", "OHOSRpcHandleError"]


class LiteDeviceError(Exception):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteDeviceConnectError(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceConnectError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteDeviceTimeout(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceTimeout, self).__init__(
            error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteParamError(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteParamError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteDeviceExecuteCommandError(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceExecuteCommandError, self).__init__(
            error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteDeviceMountError(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceMountError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class LiteDeviceReadOutputError(LiteDeviceError):
    def __init__(self, error_msg, error_no=""):
        super(LiteDeviceReadOutputError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class HDCFPortError(HdcError):
    def __init__(self, error_msg: str, error_no: str = ""):
        super(HDCFPortError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)


class OHOSRpcNotRunningError(RpcNotRunningError):
    def __init__(self, error_msg, error_no="", device=None):
        super(RpcNotRunningError, self).__init__(error_msg, error_no)
        if device:
            self.print_info(device)

    @staticmethod
    def print_info(device):
        device.log.info("#############################################"
                        "RpcNotRunningError"
                        "#############################################")
        OHOSRpcNotRunningError.develop_mode(device)
        OHOSRpcNotRunningError.memery_info(device)
        device.log.info("#############################################"
                        "RpcNotRunningError"
                        "#############################################")

    @staticmethod
    def develop_mode(device):
        if not device.is_root:
            device.log.info(f"{device.device_sn} is not root!")
            ret = device.execute_shell_command("uitest --version")
            if "inaccessible or not found" in ret:
                device.log.info(f"{device.device_sn} developer mode is False!")
            else:
                device.log.info(f"{device.device_sn} developer mode is True!")
        else:
            device.log.info(f"{device.device_sn} is root!")
            status = device.execute_shell_command("param get const.security.developermode.state")
            if status and status.strip() == "true":
                result = True
            else:
                result = False
            device.log.info(f"{device.device_sn} developer mode is {result}!")

    @staticmethod
    def memery_info(device):
        ret = device.execute_shell_command("free -h")
        device.log.info(f"{device.device_sn} memery info \n {ret}!")

    def __str__(self):
        return str(self.error_msg)


class OHOSRpcStartFailedError(OHOSRpcNotRunningError):
    def __init__(self, error_msg, error_no="", device=None):
        super(OHOSRpcStartFailedError, self).__init__(error_msg, error_no, device)


class OHOSRpcPortNotFindError(OHOSRpcNotRunningError):
    def __init__(self, error_msg, error_no="", device=None):
        super(OHOSRpcPortNotFindError, self).__init__(error_msg, error_no, device)


class OHOSRpcProcessNotFindError(OHOSRpcNotRunningError):
    def __init__(self, error_msg, error_no="", device=None):
        super(OHOSRpcProcessNotFindError, self).__init__(error_msg, error_no, device)


class OHOSDeveloperModeNotTrueError(OHOSRpcNotRunningError):
    def __init__(self, error_msg, error_no="", device=None):
        super(OHOSDeveloperModeNotTrueError, self).__init__(error_msg, error_no, device)


class OHOSProxyInitFailed(RpcNotRunningError):
    def __init__(self, error_msg, error_no=""):
        super(RpcNotRunningError, self).__init__(error_msg, error_no)


class OHOSRpcHandleError(Exception):
    def __init__(self, error_msg, error_no=""):
        super(OHOSRpcHandleError, self).__init__(error_msg, error_no)
        self.error_msg = error_msg
        self.error_no = error_no

    def __str__(self):
        return str(self.error_msg)
