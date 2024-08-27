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

import re
from collections import namedtuple

__all__ = ["Error", "ErrorCategory", "ErrorMessage"]


class ErrorCategory:
    Environment = "Environment"
    Framework = "Framework"
    Script = "Script"


class Error(namedtuple("Error", ["code", "error", "category", "suggestions"],
                       defaults=[ErrorCategory.Framework, ""])):
    """
    错误码:
    1~2位，01-99，插件编号：01-xdevice、02-devicetest、03-ohos、...
    3~4位，01-99，保留位，可自由分配，如将环境问题细分为hdc问题、设备问题、...
    5~7位，000-999，错误编号
    示例：
    [Framework-0101123] error message [Suggestions] fix suggestions
    解析：
    Framework是错误类别，0101123是错误代码，error message是错误信息，Suggestions是修改建议（可选）
    """

    __slots__ = ()

    def __repr__(self):
        msg = "[{}-{}] {}".format(self.category, self.code, self.error)
        if self.suggestions:
            msg += " [Suggestions] {}".format(self.suggestions)
        return msg

    def format(self, *args, **kwargs):
        # 错误出现嵌套的情况，返回原始的错误
        for arg in args:
            arg_str = str(arg)
            if re.search(r'\[.*[a-zA-Z0-9]+].*(?:\[Suggestions].*)?', arg_str) is not None:
                return arg_str

        return self.__str__().format(*args, **kwargs)


class _CommonErr:
    """Code_0101xxx，汇总常见的、未归类的问题"""
    Code_0101001 = Error(**{"error": "Unsupported system environment",
                            "code": "0101001"})
    Code_0101002 = Error(**{"error": "File path does not exist, path: {}",
                            "category": "{}",
                            "code": "0101002"})
    Code_0101003 = Error(**{"error": "Test kit {} does not exist",
                            "code": "0101003",
                            "suggestions": "1、kit名称错误；2、未安装kit依赖的模块"})
    Code_0101004 = Error(**{"error": "Test kit {} has no attribute of device_name",
                            "code": "0101004"})
    Code_0101005 = Error(**{"error": "History report path does not exist, path: {}",
                            "code": "0101005"})
    Code_0101006 = Error(**{"error": "The combined parameters which key '{}' has no value",
                            "category": ErrorCategory.Environment,
                            "code": "0101006",
                            "suggestions": "按照格式“key1:value1;key2:value2”使用组合参数"})
    Code_0101007 = Error(**{"error": "no retry case exists",
                            "code": "0101007"})
    Code_0101008 = Error(**{"error": "session '{}' is invalid",
                            "category": ErrorCategory.Environment,
                            "code": "0101008"})
    Code_0101009 = Error(**{"error": "no previous executed command",
                            "category": ErrorCategory.Environment,
                            "code": "0101009"})
    Code_0101010 = Error(**{"error": "session '{}' has no executed command",
                            "category": ErrorCategory.Environment,
                            "code": "0101010"})
    Code_0101011 = Error(**{"error": "wrong input task id '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0101011"})
    Code_0101012 = Error(**{"error": "Unsupported command action '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0101012",
                            "suggestions": "此方法用作处理run指令"})
    Code_0101013 = Error(**{"error": "Unsupported execution type '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0101013",
                            "suggestions": "当前支持设备测试device_test和主机测试host_test"})
    Code_0101014 = Error(**{"error": "Test source '{}' or its json does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0101014",
                            "suggestions": "1、确认是否存在对应的测试文件或用例json；2、检查user_config.xml的testcase路径配置；"
                                           "3、确保xdevice框架程序工作目录为脚本工程目录"})
    Code_0101015 = Error(**{"error": "Task file does not exist, file name: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0101015",
                            "suggestions": "需将任务json放在config目录下。如run acts全量运行acts测试用例，"
                                           "需将acts.json放在config目录下"})
    Code_0101016 = Error(**{"error": "No test driver to execute",
                            "category": ErrorCategory.Script,
                            "code": "0101016",
                            "suggestions": "用例json需要配置测试驱动"})
    Code_0101017 = Error(**{"error": "Test source '{}' has no test driver specified",
                            "category": ErrorCategory.Environment,
                            "code": "0101017",
                            "suggestions": "用例json需要配置测试驱动"})
    Code_0101018 = Error(**{"error": "Test source '{}' can't find the specified test driver '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0101018",
                            "suggestions": "1、用例json驱动名称填写错误；2、驱动插件未安装"})
    Code_0101019 = Error(**{"error": "Test source '{}' can't find the suitable test driver '{}'",
                            "category": ErrorCategory.Environment,
                            "code": "0101019",
                            "suggestions": "1、用例json驱动名称填写错误；2、驱动插件未安装"})
    Code_0101020 = Error(**{"error": "report path must be an empty folder",
                            "category": ErrorCategory.Environment,
                            "code": "0101020",
                            "suggestions": "测试报告路径需为一个空文件夹"})
    Code_0101021 = Error(**{"error": "Test source '{}' required device does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0101021",
                            "suggestions": "测试用例的设备条件不满足"})
    Code_0101022 = Error(**{"error": "no test file, list, dict, case or task were found",
                            "category": ErrorCategory.Environment,
                            "code": "0101022",
                            "suggestions": "未发现用例"})
    Code_0101023 = Error(**{"error": "test source is none",
                            "category": ErrorCategory.Script,
                            "code": "0101023"})
    Code_0101024 = Error(**{"error": "Test file '{}' does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0101024"})
    Code_0101025 = Error(**{"error": "RSA encryption error occurred, {}",
                            "code": "0101025"})
    Code_0101026 = Error(**{"error": "RSA decryption error occurred, {}",
                            "code": "0101026"})
    Code_0101027 = Error(**{"error": "Json file does not exist, file: {}",
                            "code": "0101027"})
    Code_0101028 = Error(**{"error": "Json file load error, file: {}, error: {}",
                            "category": ErrorCategory.Script,
                            "code": "0101028"})
    Code_0101029 = Error(**{"error": "'{}' under '{}' should be dict",
                            "category": ErrorCategory.Script,
                            "code": "0101029"})
    Code_0101030 = Error(**{"error": "'type' key does not exist in '{}' under '{}'",
                            "category": ErrorCategory.Script,
                            "code": "0101030"})
    Code_0101031 = Error(**{"error": "The parameter {} {} is error",
                            "category": ErrorCategory.Environment,
                            "code": "0101031"})


class _InterfaceImplementErr:
    """Code_0102xxx，汇总接口实现的问题"""
    Code_0102001 = Error(**{"error": "@Plugin must be specify type and id attributes. such as @Plugin('plugin_type') "
                                     "or @Plugin(type='plugin_type', id='plugin_id')",
                            "code": "0102001"})
    Code_0102002 = Error(**{"error": "'{}' attribute is not allowed for plugin {}",
                            "code": "0102002"})
    Code_0102003 = Error(**{"error": "__init__ method must be no arguments for plugin {}",
                            "code": "0102003"})
    Code_0102004 = Error(**{"error": "'{}' method is not allowed for plugin {}",
                            "code": "0102004"})
    Code_0102005 = Error(**{"error": "{} plugin must be implement as {}",
                            "code": "0102005"})
    Code_0102006 = Error(**{"error": "Can not find the plugin {}",
                            "code": "0102006"})
    Code_0102007 = Error(**{"error": "Parser {} must be implement as IParser",
                            "code": "0102007"})


class _UserConfigErr:
    """Code_0103xxx，汇总user_config.xml配置有误的问题"""
    Code_0103001 = Error(**{"error": "user_config.xml does not exist",
                            "category": ErrorCategory.Environment,
                            "code": "0103001",
                            "suggestions": "1、确保框架程序运行目录为工程根目录；2、工程根目录存在配置文件config/user_config.xml"})
    Code_0103002 = Error(**{"error": "Parsing the user_config.xml failed, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0103002",
                            "suggestions": "检查user_config.xml配置文件的格式"})
    Code_0103003 = Error(**{"error": "Parsing the user_config.xml from parameter(-env) failed, error: {}",
                            "category": ErrorCategory.Environment,
                            "code": "0103003",
                            "suggestions": "检查-env运行参数配置内容的格式"})
    Code_0103004 = Error(**{"error": "The alias of device {} is the same as that of device {}",
                            "category": ErrorCategory.Environment,
                            "code": "0103004",
                            "suggestions": "设备别名不允许同名"})


class ErrorMessage:
    Common: _CommonErr = _CommonErr()
    InterfaceImplement: _InterfaceImplementErr = _InterfaceImplementErr()
    UserConfig: _UserConfigErr = _UserConfigErr()


if __name__ == "__main__":
    # 用法1，使用原始类，无需格式化报错内容
    _err_101 = Error(**{"error": "error 101", "code": "101"})
    print(_err_101)

    # 用法2，使用构造方法，按format格式化报错内容
    _err_102 = Error(**{"error": "{}, path: {}", "code": "102", "suggestions": "sss"})
    print(_err_102.format("error 102", "test path"))
    print(_err_102.code)

    # 测试错误嵌套的情况
    # 如：[Framework-102] [Framework-102] error 102, path: test path [Suggestions] sss, path: test path [Suggestions] sss
    err_msg1 = "[Framework-102] error 102, path: test path"
    print(_err_102.format(err_msg1, "test path1"))
    err_msg1 = "[Framework-102] error 102, path: test path [Suggestions] sss"
    print(_err_102.format(err_msg1, "test path2"))
