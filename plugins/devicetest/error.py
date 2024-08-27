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
    """Code_0201xxx，汇总常见的、未归类的问题"""
    Code_0201001 = Error(**{"error": "File path does not exist, path: {}",
                            "category": "{}",
                            "code": "0201001"})
    Code_0201002 = Error(**{"error": "Json file does not exist, file: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0201002"})
    Code_0201003 = Error(**{"error": "generate test report failed",
                            "code": "0201003"})
    Code_0201004 = Error(**{"error": "The test task is terminated abnormally",
                            "code": "0201004",
                            "suggestions": "测试任务被异常终止"})
    Code_0201005 = Error(**{"error": "Failed to obtain the idle port",
                            "category": ErrorCategory.Environment,
                            "code": "0201005"})
    Code_0201006 = Error(**{"error": "The source image for image comparison does not exist, source: {}",
                            "category": ErrorCategory.Script,
                            "code": "0201006"})
    Code_0201007 = Error(**{"error": "The target image for image comparison does not exist, target: {}",
                            "category": ErrorCategory.Script,
                            "code": "0201007"})
    Code_0201008 = Error(**{"error": "Resource file does not exist, file: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0201008",
                            "suggestions": "测试资源文件不存在"})
    Code_0201009 = Error(**{"error": "Failed to write content to the file",
                            "category": ErrorCategory.Environment,
                            "code": "0201009"})
    Code_0201010 = Error(**{"error": "Failed to read content from the file",
                            "category": ErrorCategory.Environment,
                            "code": "0201010"})
    Code_0201011 = Error(**{"error": "Unsupported system environment",
                            "category": ErrorCategory.Environment,
                            "code": "0201011"})
    Code_0201012 = Error(**{"error": "Syntax error in test specifier '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0201012"})
    Code_0201013 = Error(**{"error": "Invalid test case name '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0201013"})
    Code_0201014 = Error(**{"error": "Can't find prepare script '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0201014"})
    Code_0201015 = Error(**{"error": "prepare script's setup step execution may be error",
                            "category": ErrorCategory.Script,
                            "code": "0201015"})
    Code_0201016 = Error(**{"error": "prepare script's teardown step execution may be error",
                            "category": ErrorCategory.Script,
                            "code": "0201016"})
    Code_0201017 = Error(**{"error": "Failed to instantiate the test runner",
                            "code": "0201017"})


class _DeviceErr:
    """Code_0202xxx，归类rpc、uitest、测试设备等问题"""
    Code_0202001 = Error(**{"error": "[{}] Reconnect to device rpc service is more than {} times, raise",
                            "category": ErrorCategory.Environment,
                            "code": "0202001"})
    Code_0202002 = Error(**{"error": "Receive 0 byte, harmony abc rpc server is disconnected!",
                            "category": ErrorCategory.Environment,
                            "code": "0202002"})
    Code_0202003 = Error(**{"error": "Receive 0 byte, harmony rpc server is disconnected!",
                            "category": ErrorCategory.Environment,
                            "code": "0202003"})
    Code_0202004 = Error(**{"error": "Receive 0 byte, rpc server is disconnected!",
                            "category": ErrorCategory.Environment,
                            "code": "0202004"})
    Code_0202005 = Error(**{"error": "install harmony {} rpc failed, reason: {}",
                            "code": "0202005"})
    Code_0202006 = Error(**{"error": "accessibility pid is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0202006"})
    Code_0202007 = Error(**{"error": "Fail to create inner UiDriver",
                            "code": "0202007"})
    Code_0202008 = Error(**{"error": "Fail to create UiDriver",
                            "code": "0202008"})
    Code_0202009 = Error(**{"error": "Fail to connect AAMS",
                            "code": "0202009"})

    # Code_02023xx，测试设备
    Code_0202301 = Error(**{"error": "webview init failed",
                            "code": "0202301"})
    Code_0202302 = Error(**{"error": "Fail to connect to device, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0202302",
                            "suggestions": "无法连接设备或向设备发送指令，设备可能已断开连接"})
    Code_0202303 = Error(**{"error": "Connector command execution timeout, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0202303",
                            "suggestions": "设备调试命令运行超时"})
    Code_0202304 = Error(**{"error": "Connector command execution timeout, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0202304",
                            "suggestions": "设备调试命令运行超时"})
    Code_0202305 = Error(**{"error": "device rpc process is not found",
                            "category": ErrorCategory.Environment,
                            "code": "0202305"})
    Code_0202306 = Error(**{"error": "device cannot be found or is offline",
                            "category": ErrorCategory.Environment,
                            "code": "0202306"})
    Code_0202307 = Error(**{"error": "Failed to install test app, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0202307"})


class _TestCaseErr:
    """Code_0203xxx，归类用例、用例执行等问题"""
    Code_0203001 = Error(**{"error": "Can't load file {}, error: {}",
                            "category": ErrorCategory.Script,
                            "code": "0203001",
                            "suggestions": "1、测试用例导入模块失败；2、若导入的模块没有被使用，则删除对应的代码行"})
    Code_0203002 = Error(**{"error": "{}",
                            "category": ErrorCategory.Script,
                            "code": "0203002"})
    Code_0203003 = Error(**{"error": "Step {} result TestError!",
                            "category": ErrorCategory.Script,
                            "code": "0203003"})
    Code_0203004 = Error(**{"error": "The self.tests variable of the test case is incorrectly assigned, "
                                     "current assigned: {}",
                            "category": ErrorCategory.Script,
                            "code": "0203004",
                            "suggestions": "测试用例的self.tests变量赋值异常，需将它赋值为用例文件里定义的测试方法"})
    Code_0203005 = Error(**{"error": "传参错误！请用list列表传递待重试运行的用例信息",
                            "code": "0203005"})
    Code_0203006 = Error(**{"error": "ImportError occurred, error: {}",
                            "category": ErrorCategory.Script,
                            "code": "0203006",
                            "suggestions": "Python三方库、AW接口等载入异常，导致用例执行失败"})
    Code_0203007 = Error(**{"error": "Failed to initialize the device object in the TestCase",
                            "code": "0203007"})
    Code_0203008 = Error(**{"error": "The parameter type is incorrect, error: {}",
                            "code": "0203008",
                            "suggestions": "参数类型错误"})
    Code_0203009 = Error(**{"error": "No device has assigned for test source",
                            "code": "0203009",
                            "suggestions": "测试用例未分配到设备资源"})
    Code_0203010 = Error(**{"error": "No config file for test source '{}'",
                            "category": ErrorCategory.Script,
                            "code": "0203010"})
    Code_0203011 = Error(**{"error": "No test list to run",
                            "category": ErrorCategory.Script,
                            "code": "0203011"})
    Code_0203012 = Error(**{"error": "No test list found",
                            "category": ErrorCategory.Script,
                            "code": "0203012"})
    Code_0203013 = Error(**{"error": "The field of [py_file] in file {}.json only support one item, now is {}",
                            "category": ErrorCategory.Script,
                            "code": "0203013",
                            "suggestions": "测试用例json的py_file字段只能配置一个用例py"})
    Code_0203014 = Error(**{"error": "The field of [testsuite] in file testsuite json is not set",
                            "category": ErrorCategory.Script,
                            "code": "0203014",
                            "suggestions": "测试套json的testsuite字段未配置测试套py"})


class _AssertionErr:
    """Code_0204xxx，断言错误提示"""
    Code_0204001 = Error(**{"error": "{}",
                            "category": ErrorCategory.Script,
                            "code": "0204001",
                            "suggestions": "自定义断言错误提示语"})
    Code_0204002 = Error(**{"error": "断言错误：由'=='条件确定的两个对象的值不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204002"})
    Code_0204003 = Error(**{"error": "断言错误：由'!='条件确定的两个对象的值相等",
                            "category": ErrorCategory.Script,
                            "code": "0204003"})
    Code_0204004 = Error(**{"error": "断言错误：检查对象不为false",
                            "category": ErrorCategory.Script,
                            "code": "0204004"})
    Code_0204005 = Error(**{"error": "断言错误：检查对象不为true",
                            "category": ErrorCategory.Script,
                            "code": "0204005"})
    Code_0204006 = Error(**{"error": "断言错误：两个对象的id不相同",
                            "category": ErrorCategory.Script,
                            "code": "0204006"})
    Code_0204007 = Error(**{"error": "断言错误：两个对象的id相同",
                            "category": ErrorCategory.Script,
                            "code": "0204007"})
    Code_0204008 = Error(**{"error": "断言错误：检查对象不为None",
                            "category": ErrorCategory.Script,
                            "code": "0204008"})
    Code_0204009 = Error(**{"error": "断言错误：检查对象为None",
                            "category": ErrorCategory.Script,
                            "code": "0204009"})
    Code_0204010 = Error(**{"error": "断言错误：检查对象不在对象容器中",
                            "category": ErrorCategory.Script,
                            "code": "0204010"})
    Code_0204011 = Error(**{"error": "断言错误：检查对象在对象容器中",
                            "category": ErrorCategory.Script,
                            "code": "0204011"})
    Code_0204012 = Error(**{"error": "断言错误：检查对象不是另一对象的实例",
                            "category": ErrorCategory.Script,
                            "code": "0204012"})
    Code_0204013 = Error(**{"error": "断言错误：检查对象是另一对象的实例",
                            "category": ErrorCategory.Script,
                            "code": "0204013"})
    Code_0204014 = Error(**{"error": "断言错误：",
                            "category": ErrorCategory.Script,
                            "code": "0204014"})
    Code_0204015 = Error(**{"error": "断言错误：检查对象的值（四舍五入比较）几乎不等于另一对象的值",
                            "category": ErrorCategory.Script,
                            "code": "0204015"})
    Code_0204016 = Error(**{"error": "断言错误：检查对象的值（四舍五入比较）几乎等于另一对象的值",
                            "category": ErrorCategory.Script,
                            "code": "0204016"})
    Code_0204017 = Error(**{"error": "断言错误：检查对象的值小于另一对象的值",
                            "category": ErrorCategory.Script,
                            "code": "0204017"})
    Code_0204018 = Error(**{"error": "断言错误：检查对象的值大于等于另一对象的值",
                            "category": ErrorCategory.Script,
                            "code": "0204018"})
    Code_0204019 = Error(**{"error": "断言错误：检查对象的值大于另一对象的值",
                            "category": ErrorCategory.Script,
                            "code": "0204019"})
    Code_0204020 = Error(**{"error": "断言错误：两个字典对象不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204020"})
    Code_0204021 = Error(**{"error": "断言错误：两个集合对象不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204021"})
    Code_0204022 = Error(**{"error": "断言错误：两个元组对象不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204022"})
    Code_0204023 = Error(**{"error": "断言错误：两个列表对象不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204023"})
    Code_0204024 = Error(**{"error": "断言错误：两个序列对象不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204024"})
    Code_0204025 = Error(**{"error": "断言错误：两个多行字符串不相等",
                            "category": ErrorCategory.Script,
                            "code": "0204025"})
    Code_0204026 = Error(**{"error": "断言错误：Expect: {}, Actual: {}",
                            "category": ErrorCategory.Script,
                            "code": "0204026"})


class ErrorMessage:
    Common: _CommonErr = _CommonErr()
    Device: _DeviceErr = _DeviceErr()
    TestCase: _TestCaseErr = _TestCaseErr()
    Assertion: _AssertionErr = _AssertionErr()
