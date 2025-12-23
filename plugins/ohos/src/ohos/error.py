#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2024 Huawei Device Co., Ltd.
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

from xdevice import Error, ErrorCategory


class _CommonErr:
    """Code_0301xxx，汇总常见的、未归类的错误"""
    Code_0301001 = Error(**{"error": "Test source '{}' does not exist",
                            "category": ErrorCategory.Script,
                            "code": "0301001"})
    Code_0301002 = Error(**{"error": "Test case '{}' does not exist",
                            "category": ErrorCategory.Script,
                            "code": "0301002"})
    Code_0301003 = Error(**{"error": "Not find ace test app file",
                            "category": ErrorCategory.Script,
                            "code": "0301003"})
    Code_0301004 = Error(**{"error": "Can't not find HarmonySdk, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0301004"})
    Code_0301005 = Error(**{"error": "Execute file does not exist",
                            "category": ErrorCategory.Script,
                            "code": "0301005"})
    Code_0301006 = Error(**{"error": "litehdc.exe not found",
                            "category": ErrorCategory.Environment,
                            "code": "0301006"})
    Code_0301007 = Error(**{"error": "Can not find acetools, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0301007",
                            "suggestions": "Install acetools"})
    Code_0301008 = Error(**{"error": "Please check jar file params",
                            "category": ErrorCategory.Script,
                            "code": "0301008"})
    Code_0301009 = Error(**{"error": "Test failed",
                            "category": ErrorCategory.Script,
                            "code": "0301009"})
    Code_0301010 = Error(**{"error": "HJSUnit test run error happened",
                            "code": "0301010"})
    Code_0301011 = Error(**{"error": "Execute timeout",
                            "category": ErrorCategory.Environment,
                            "code": "0301011"})
    Code_0301012 = Error(**{"error": "Execute_arkuix_command exception, reason: {}",
                            "code": "0301012"})
    Code_0301013 = Error(**{"error": "Execute terminates",
                            "code": "0301013"})
    Code_0301014 = Error(**{"error": "Error generating log report",
                            "code": "0301014"})
    Code_0301015 = Error(**{"error": "The json file '{}' does not exist",
                            "category": ErrorCategory.Script,
                            "code": "0301015"})


class _ConfigErr:
    """Code_0302xxx，用例json、user_config.xml配置问题"""
    Code_0302001 = Error(**{"error": "Neither package nor module is found in config file",
                            "category": ErrorCategory.Script,
                            "code": "0302001"})
    Code_0302002 = Error(**{"error": "Can't find package in config file",
                            "category": ErrorCategory.Script,
                            "code": "0302002"})
    Code_0302003 = Error(**{"error": "Can't find bundle-name in config file",
                            "category": ErrorCategory.Script,
                            "code": "0302003"})
    Code_0302004 = Error(**{"error": "MountKit setup request is None",
                            "category": ErrorCategory.Script,
                            "code": "0302004"})
    Code_0302005 = Error(**{"error": "The source of MountKit can't be empty in Test.json",
                            "category": ErrorCategory.Script,
                            "code": "0302005"})
    Code_0302006 = Error(**{"error": "Failed to obtain the spt value of the configuration file",
                            "category": ErrorCategory.Script,
                            "code": "0302006"})
    Code_0302007 = Error(**{"error": "The config for deploy kit is invalid with timeout: {}, burn_file: {}",
                            "category": ErrorCategory.Script,
                            "code": "0302007"})
    Code_0302008 = Error(**{"error": "The config for rootfs kit is invalid. checksum: {}, "
                                     "hash file name: {} device label: {}",
                            "category": ErrorCategory.Script,
                            "code": "0302008"})
    Code_0302009 = Error(**{"error": "The config for query kit is invalid with query: {}",
                            "category": ErrorCategory.Script,
                            "code": "0302009"})
    Code_0302010 = Error(**{"error": "The request of queryKit is None",
                            "category": ErrorCategory.Script,
                            "code": "0302010"})
    Code_0302011 = Error(**{"error": "The config for deploy tool kit is invalid, device label: {} time out: {}",
                            "category": ErrorCategory.Script,
                            "code": "0302011"})
    Code_0302012 = Error(**{"error": "The json file '{}' parse error",
                            "category": ErrorCategory.Script,
                            "code": "0302012"})
    Code_0302013 = Error(**{"error": "The sts_version: {} is invalid",
                            "category": ErrorCategory.Script,
                            "code": "0302013"})
    Code_0302014 = Error(**{"error": "The sts version {} does match the rule",
                            "category": ErrorCategory.Environment,
                            "code": "0302014"})
    Code_0302015 = Error(**{"error": "The device security patch version {} is invalid",
                            "category": ErrorCategory.Environment,
                            "code": "0302015"})
    Code_0302016 = Error(**{"error": "The device SPL version {} does not match the sts version {}",
                            "category": ErrorCategory.Environment,
                            "code": "0302016"})
    Code_0302017 = Error(**{"error": "Load Error",
                            "category": ErrorCategory.Script,
                            "code": "0302017"})
    Code_0302018 = Error(**{"error": "The name of remote nfs server does not match",
                            "category": ErrorCategory.Environment,
                            "code": "0302018"})
    Code_0302019 = Error(**{"error": "Nfs server does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0302019",
                            "suggestions": "Please check user_config.xml"})
    Code_0302020 = Error(**{"error": "Device label should be ipcamera or wifiiot, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302020"})
    Code_0302021 = Error(**{"error": "Device com or ip cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302021"})
    Code_0302022 = Error(**{"error": "The name of remote device {} does not match",
                            "category": ErrorCategory.Environment,
                            "code": "0302022"})
    Code_0302023 = Error(**{"error": "Nfs server miss ip or directory",
                            "category": ErrorCategory.Environment,
                            "code": "0302023"})
    Code_0302024 = Error(**{"error": "The value found for property {} is {}, not same with the expected {}",
                            "code": "0302024"})
    Code_0302025 = Error(**{"error": "Remote device ip not in right format",
                            "category": ErrorCategory.Environment,
                            "code": "0302025",
                            "suggestions": "Please check user_config.xml"})
    Code_0302026 = Error(**{"error": "Device label cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302026"})
    # lite devices
    Code_0302027 = Error(**{"error": "WatchGT local label does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0302027"})
    Code_0302028 = Error(**{"error": "WatchGT local com cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302028"})
    Code_0302029 = Error(**{"error": "WatchGT local com does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0302029"})
    Code_0302030 = Error(**{"error": "Wifiiot local com cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302030"})
    Code_0302031 = Error(**{"error": "Wifiiot com type cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302031"})
    Code_0302032 = Error(**{"error": "Wifiiot need cmd com and deploy com at the same time, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302032"})
    Code_0302033 = Error(**{"error": "Ipcamera local com cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302033"})
    Code_0302034 = Error(**{"error": "Ipcamera remote port should be a number, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302034"})
    Code_0302035 = Error(**{"error": "Ipcamera remote port cannot be empty, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0302035"})
    Code_0302036 = Error(**{"error": "The config of serial port {} to deploy is invalid",
                            "category": ErrorCategory.Environment,
                            "code": "0302036"})
    Code_0302037 = Error(**{"error": "Failed to get device env",
                            "category": ErrorCategory.Environment,
                            "code": "0302037"})


class _DeviceErr:
    """Code_0303xxx，设备问题"""
    Code_0303001 = Error(**{"error": "Local path cannot be none",
                            "category": ErrorCategory.Environment,
                            "code": "0303001"})
    Code_0303002 = Error(**{"error": "Local path does not exist, path: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303002"})
    Code_0303003 = Error(**{"error": "Remote path does not exist, path: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303003"})
    Code_0303004 = Error(**{"error": "Push file failed! Local: '{}', Remote: '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0303004"})
    Code_0303005 = Error(**{"error": "Install package failed! Package path cannot be none",
                            "category": ErrorCategory.Environment,
                            "code": "0303005"})
    Code_0303006 = Error(**{"error": "Install package failed! {}",
                            "code": "0303006"})
    Code_0303007 = Error(**{"error": "Failed to install {} on {}. {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303007"})
    Code_0303008 = Error(**{"error": "Connect remote lite device failed, host is {}, port is {}, error is {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303008"})
    Code_0303009 = Error(**{"error": "Connect {} serial failed, error is {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303009",
                            "suggestions": "Please make sure this port is not occupied"})
    Code_0303010 = Error(**{"error": "Local device is not connected",
                            "category": ErrorCategory.Environment,
                            "code": "0303010"})
    Code_0303011 = Error(**{"error": "Failed to get server environment",
                            "category": ErrorCategory.Environment,
                            "code": "0303011"})
    Code_0303012 = Error(**{"error": "Execute_oh_js_local_command exception, reason: {}",
                            "code": "0303012"})
    Code_0303013 = Error(**{"error": "{} shell {} timeout[{}s]",
                            "category": ErrorCategory.Environment,
                            "code": "0303013"})
    Code_0303014 = Error(**{"error": "Execute command timeout: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0303014"})
    Code_0303015 = Error(**{"error": "Harmony rpc init failed. Reason: Device's developer mode is false",
                            "category": ErrorCategory.Environment,
                            "code": "0303015",
                            "suggestions": "需要打开测试设备的开发者模式"})
    Code_0303016 = Error(**{"error": "Harmony {} rpc start failed. Reason: {}",
                            "code": "0303016"})
    Code_0303017 = Error(**{"error": "Channel EOF",
                            "category": ErrorCategory.Environment,
                            "code": "0303017"})
    Code_0303018 = Error(**{"error": "Remote device is not connected",
                            "category": ErrorCategory.Environment,
                            "code": "0303018"})
    Code_0303019 = Error(**{"error": "{} port set_up wifiiot failed",
                            "category": ErrorCategory.Environment,
                            "code": "0303019"})
    Code_0303020 = Error(**{"error": "Failed to mount the device",
                            "category": ErrorCategory.Environment,
                            "code": "0303020"})
    Code_0303021 = Error(**{"error": "The harmony device developer mode needs to be opened",
                            "category": ErrorCategory.Environment,
                            "code": "0303021",
                            "suggestions": "需要打开测试设备的开发者模式"})
    Code_0303022 = Error(**{"error": "hdc fport failed after retry, raise",
                            "category": ErrorCategory.Environment,
                            "code": "0303022"})
    Code_0303023 = Error(**{"error": "The harmony device rpc({}) process is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303023"})
    Code_0303024 = Error(**{"error": "The harmony device rpc({}) port is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303024"})
    Code_0303025 = Error(**{"error": "UI RPC process is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303025"})
    Code_0303026 = Error(**{"error": "UI RPC listening port is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303026"})
    Code_0303027 = Error(**{"error": "HAP RPC process is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303027"})
    Code_0303028 = Error(**{"error": "HAP RPC listening port is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0303028"})
    Code_0303029 = Error(**{"error": "UI PROXY init failed: {}!",
                            "category": ErrorCategory.Environment,
                            "code": "0303029"})
    Code_0303030 = Error(**{"error": "HAP PROXY init failed: {}!",
                            "category": ErrorCategory.Environment,
                            "code": "0303030"})
    Code_0303031 = Error(**{"error": "AI PROXY init failed: {}!",
                            "category": ErrorCategory.Environment,
                            "code": "0303031"})
    Code_0303032 = Error(**{"error": "HAP PROXY handle message failed!",
                            "category": ErrorCategory.Environment,
                            "code": "0303032"})


class _HdcErr:
    """Code_0304xxx，hdc工具使用问题"""
    Code_0304001 = Error(**{"error": "HdcMonitor connect to server({}:{}) failed, please check",
                            "category": ErrorCategory.Environment,
                            "code": "0304001"})
    Code_0304002 = Error(**{"error": "Got a unhappy response from hdc server, sync req: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0304002"})
    Code_0304003 = Error(**{"error": "Remote path is too long",
                            "category": ErrorCategory.Environment,
                            "code": "0304003"})
    Code_0304004 = Error(**{"error": "Receiving too much data",
                            "category": ErrorCategory.Environment,
                            "code": "0304004"})
    Code_0304005 = Error(**{"error": "Hdc cmd rejected, response: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0304005"})
    Code_0304006 = Error(**{"error": "Cannot detect hdc monitor",
                            "category": ErrorCategory.Environment,
                            "code": "0304006"})
    Code_0304007 = Error(**{"error": "Cannot connect to hdc server",
                            "category": ErrorCategory.Environment,
                            "code": "0304007"})


class ErrorMessage:
    Common: _CommonErr = _CommonErr()
    Config: _ConfigErr = _ConfigErr()
    Device: _DeviceErr = _DeviceErr()
    Hdc: _HdcErr = _HdcErr()
