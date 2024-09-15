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

import warnings
warnings.warn("this module is deprecated, use 'devicetest.error' instead", DeprecationWarning)


class DetailErrorMassage:
    Error_01100 = {
        "Topic": "测试资源加载异常[01100]",
        "Code": "01100",
        "Message": {
            "en": "The third-party Python library or key AW of the test "
                  "suite is missing or the script syntax is incorrect. "
                  "As a result, the test suite fails to be loaded. {}",
            "ch": "测试套的Python三方库、关键AW缺失或脚本语法错误，导致测试套加载失败."
        }
    }

    Error_01101 = {
        "Topic": "测试资源加载异常[01101]",
        "Code": "01101",
        "Message": {
            "en": "An error occurred when parsing AW parameters during "
                  "script execution (parameter syntax error or method "
                  "parameter inconsistency).",
            "ch": "执行脚本过程中解析AW参数出错(参数语法错误，方法参数不一致)."
        }
    }

    Error_01102 = {
        "Topic": "测试资源加载异常[01102]",
        "Code": "01102",
        "Message": {
            "en": "The dependent file resource (video resource file) is "
                  "missing during task execution.",
            "ch": "任务执行过程中，依赖的文件资源缺失(视频资源文件)."
        }
    }

    Error_01105 = {
        "Topic": "测试资源加载异常[01105]",
        "Code": "01105",
        "Message": {
            "en": "The CPU of the mobile phone does not depend on "
                  "the HiSilicon chip during network packet capture.",
            "ch": "网络报文抓取时，依赖的手机CPU不是海思芯片."
        }
    }

    Error_01107 = {
        "Topic": "测试用例执行失败[01107]",
        "Code": "01107",
        "Message": {
            "en": "Wi-Fi is not enabled.",
            "ch": "未打开WiFi."
        }
    }

    Error_01108 = {
        "Topic": "测试资源加载异常[01108]",
        "Code": "01108",
        "Message": {
            "en": "model_aw import resource error.",
            "ch": "model_aw 引入资源时发生错误."
        }
    }

    Error_01109 = {
        "Topic": "测试资源加载异常[01109]",
        "Code": "01109",
        "Message": {
            "en": "hierachyview module import error.",
            "ch": "hierachyview 模块引入时发生错误."
        }
    }

    Error_01110 = {
        "Topic": "测试资源加载异常[01110]",
        "Code": "01110",
        "Message": {
            "en": "error, test suite not found py script.",
            "ch": "testsuite用例没有找到目标py用例."
        }
    }

    Error_01200 = {
        "Topic": "测试用例执行失败[01200]",
        "Code": "01200",
        "Message": {
            "en": "No error message is set in the script, and the actual "
                  "value of the check point is different from the expected "
                  "value. {}",
            "ch": "脚本没有设置错误提示信息，检查点的实际输入值与预期结果不一致."
        }
    }

    Error_01201 = {
        "Topic": "测试用例执行失败[01201]",
        "Code": "01201",
        "Message": {
            "en": "The manual submission result is incorrect.",
            "ch": "手动提交的步骤结果不正确."
        }
    }

    Error_01202 = {
        "Topic": "测试用例执行失败[01202]",
        "Code": "01202",
        "Message": {
            "en": "An unknown error occurred when running the setup command.",
            "ch": "执行setup遇到未知错误."
        }
    }

    Error_01203 = {
        "Topic": "测试用例执行失败[01203]",
        "Code": "01203",
        "Message": {
            "en": "An unknown error occurred when running the test command.",
            "ch": "执行test遇到未知错误."
        }
    }

    Error_01204 = {
        "Topic": "测试用例执行失败[01204]",
        "Code": "01204",
        "Message": {
            "en": "An unknown error occurred when running the teardown "
                  "command.",
            "ch": "执行teardown遇到未知错误."
        }
    }

    Error_01205 = {
        "Topic": "测试用例执行失败[01205]",
        "Code": "01205",
        "Message": {
            "en": "An unexpected error occurs during the execution of "
                  "the current case.",
            "ch": "当前用例执行出现非预期的错误."
        }
    }

    Error_01206 = {
        "Topic": "测试用例执行失败[01206]",
        "Code": "01206",
        "Message": {
            "en": "An error is reported when the connector command is executed.",
            "ch": "执行connector命令异常报错."
        }
    }

    Error_01207 = {
        "Topic": "测试用例执行失败[01207]",
        "Code": "01207",
        "Message": {
            "en": "generate test report failed.",
            "ch": "生成xml报告失败."
        }
    }

    Error_01208 = {
        "Topic": "测试用例执行失败[01208]",
        "Code": "01207",
        "Message": {
            "en": "Failed to obtain the idle port.",
            "ch": "获取connector空闲端口失败."
        }
    }

    Error_01209 = {
        "Topic": "测试用例执行失败[01209]",
        "Code": "01209",
        "Message": {
            "en": "An exception occurred when parsing parameters in the "
                  "current aw step.",
            "ch": "当前aw步骤的参数解析异常."
        }
    }

    Error_01210 = {
        "Topic": "测试用例执行失败[01210]",
        "Code": "01210",
        "Message": {
            "en": "An exception occurred when executing the current aw step.",
            "ch": "当前aw步骤的执行异常."
        }
    }

    Error_01211 = {
        "Topic": "测试用例执行失败[01211]",
        "Code": "01211",
        "Message": {
            "en": "Failed to connect to the device:The device goes offline.",
            "ch": "连接设备失败:设备掉线."
        }
    }

    Error_01212 = {
        "Topic": "测试用例执行失败[01212]",
        "Code": "01212",
        "Message": {
            "en": "Running the connector command times out.",
            "ch": "执行connector命令超时."
        }
    }

    Error_01213 = {
        "Topic": "测试用例执行失败[01213]",
        "Code": "01213",
        "Message": {
            "en": "Failed to install the App.",
            "ch": "App安装失败."
        }
    }

    Error_01214 = {
        "Topic": "测试用例执行失败[01214]",
        "Code": "01214",
        "Message": {
            "en": "with open write file content Failed.",
            "ch": "打开并写入文件内容失败."
        }
    }

    Error_01215 = {
        "Topic": "测试用例执行失败[01215]",
        "Code": "01215",
        "Message": {
            "en": "with open read file content Failed.",
            "ch": "打开并读取文件内容失败."
        }
    }

    Error_01216 = {
        "Topic": "测试用例执行失败[01216]",
        "Code": "01216",
        "Message": {
            "en": "with open read file: No such file.",
            "ch": "读文件时文件不存在."
        }
    }

    Error_01217 = {
        "Topic": "测试用例执行失败[01217]",
        "Code": "01217",
        "Message": {
            "en": "device not found:The test mobile phone is disconnected.",
            "ch": "设备未找到:测试手机断连."
        }
    }

    Error_01218 = {
        "Topic": "测试用例执行失败[01218]",
        "Code": "01218",
        "Message": {
            "en": "Failed to initialize the device object in the TestCase.",
            "ch": "TestCase初始化设备对象异常."
        }
    }
    ##########################################################################
    # root 相应接口错误码

    Error_01239 = {
        "Topic": "测试用例执行失败[01239]",
        "Code": "01239",
        "Message": {
            "en": "Can't get StatusBar height {}.",
            "ch": "无法获取状态栏高度."
        }
    }

    Error_01240 = {
        "Topic": "测试用例执行失败[01240]",
        "Code": "01240",
        "Message": {
            "en": "failed to refresh StatusBar.",
            "ch": "刷新状态栏失败."
        }
    }

    Error_01241 = {
        "Topic": "测试用例执行失败[01241]",
        "Code": "01241",
        "Message": {
            "en": "Widget don't have property {}.",
            "ch": "工具没有对应属性."
        }
    }

    Error_01242 = {
        "Topic": "测试用例执行失败[01242]",
        "Code": "01242",
        "Message": {
            "en": "can't get window named {} from device {}.",
            "ch": "无法从设备获取指定的窗口."
        }
    }

    Error_01243 = {
        "Topic": "测试用例执行失败[01243]",
        "Code": "01243",
        "Message": {
            "en": "get Focused WindowId Exception.",
            "ch": "获取焦点窗口ID异常."
        }
    }

    Error_01244 = {
        "Topic": "测试用例执行失败[01244]",
        "Code": "01244",
        "Message": {
            "en": "Unable to get the focused window name from device {}.",
            "ch": "找到的视图节点不可见."
        }
    }

    Error_01245 = {
        "Topic": "测试用例执行失败[01245]",
        "Code": "01245",
        "Message": {
            "en": "Finded viewnode with {} is not visible.",
            "ch": "找到的视图节点不可见."
        }
    }

    Error_01246 = {
        "Topic": "测试用例执行失败[01246]",
        "Code": "01246",
        "Message": {
            "en": "Not find viewnode with {}.",
            "ch": "未找到对应视图节点."
        }
    }

    Error_01247 = {
        "Topic": "测试用例执行失败[01247]",
        "Code": "01247",
        "Message": {
            "en": "cannot find viewnode with property {}.{}.",
            "ch": "找不到具有属性的视图节点."
        }
    }

    Error_01248 = {
        "Topic": "测试用例执行失败[01248]",
        "Code": "01248",
        "Message": {
            "en": "ViewNode is none.",
            "ch": "目标控件对象为None."
        }
    }

    Error_01249 = {
        "Topic": "测试用例执行失败[01249]",
        "Code": "01249",
        "Message": {
            "en": "parse View Hierarchy Exception.",
            "ch": "解析视图层次结构异常."
        }
    }

    Error_01250 = {
        "Topic": "测试用例执行失败[01250]",
        "Code": "01250",
        "Message": {
            "en": "load Window Data Exception.",
            "ch": "获取视图数据异常."
        }
    }

    Error_01251 = {
        "Topic": "测试用例执行失败[01251]",
        "Code": "01251",
        "Message": {
            "en": "get Focused Window Exception.",
            "ch": "获取焦点窗口异常."
        }
    }

    Error_01252 = {
        "Topic": "测试用例执行失败[01252]",
        "Code": "01252",
        "Message": {
            "en": "Load Windows Exception.",
            "ch": "加载Windows服务异常."
        }
    }

    Error_01253 = {
        "Topic": "测试用例执行失败[01253]",
        "Code": "01253",
        "Message": {
            "en": "stop View Server Failed.",
            "ch": "停止视图服务失败."
        }
    }

    Error_01254 = {
        "Topic": "测试用例执行失败[01254]",
        "Code": "01254",
        "Message": {
            "en": "start View Server Failed.",
            "ch": "启动视图服务失败."
        }
    }

    Error_01255 = {
        "Topic": "测试用例执行失败[01255]",
        "Code": "01255",
        "Message": {
            "en": "service call window 3 error.",
            "ch": "服务调用窗口3错误."
        }
    }

    Error_01256 = {
        "Topic": "测试用例执行失败[01256]",
        "Code": "01256",
        "Message": {
            "en": "setup Device Forward Failed.",
            "ch": "设置设备转发失败."
        }
    }

    Error_01257 = {
        "Topic": "测试用例执行失败[01257]",
        "Code": "01257",
        "Message": {
            "en": "Cannot forward to view server.",
            "ch": "无法转发到查看服务器."
        }
    }

    Error_01258 = {
        "Topic": "测试用例执行失败[01258]",
        "Code": "01258",
        "Message": {
            "en": "Could not connect to the view server.",
            "ch": "无法连接到视图服务器."
        }
    }

    Error_01259 = {
        "Topic": "测试用例执行失败[01259]",
        "Code": "01259",
        "Message": {
            "en": "Failed to create socket connection with view server.",
            "ch": "创建与视图服务器的套接字连接失败."
        }
    }

    ##########################################################################
    # 业务使用

    Error_01260 = {
        "Topic": "测试用例执行失败[01260]",
        "Code": "01260",
        "Message": {
            "en": "Assertion Error: Two objects determined by '==' are "
                  "unequal,{}",
            "ch": "断言错误: 由'=='确定的两个对象不相等."
        }
    }

    Error_01261 = {
        "Topic": "测试用例执行失败[01261]",
        "Code": "01261",
        "Message": {
            "en": "Assertion Error: Two objects determined by '!=' are "
                  "equal,{}",
            "ch": "断言错误: 由'!='确定的两个对象相等."
        }
    }

    Error_01262 = {
        "Topic": "测试用例执行失败[01262]",
        "Code": "01262",
        "Message": {
            "en": "Assertion Error: The asserted object is not false,{}",
            "ch": "断言错误: 检查的对象不为false."
        }
    }

    Error_01263 = {
        "Topic": "测试用例执行失败[01263]",
        "Code": "01263",
        "Message": {
            "en": "Assertion Error: The asserted object is not true.,{}",
            "ch": "断言错误: 检查的对象不为true."
        }
    }

    Error_01264 = {
        "Topic": "测试用例执行失败[01264]",
        "Code": "01264",
        "Message": {
            "en": "Assertion Error: The asserted object1 is not object2,{}",
            "ch": "断言错误: 断言的对象1不是对象2."
        }
    }

    Error_01265 = {
        "Topic": "测试用例执行失败[01265]",
        "Code": "01265",
        "Message": {
            "en": "Assertion Error: The asserted object1 is object2,{}",
            "ch": "断言错误: 断言的对象1是对象2."
        }
    }

    Error_01266 = {
        "Topic": "测试用例执行失败[01266]",
        "Code": "01266",
        "Message": {
            "en": "Assertion error: The asserted object is not None,{}",
            "ch": "断言错误: 断言的对象不为None."
        }
    }

    Error_01267 = {
        "Topic": "测试用例执行失败[01267]",
        "Code": "01267",
        "Message": {
            "en": "Assertion error: The asserted object is None,{}",
            "ch": "断言错误: 断言的对象为None."
        }
    }

    Error_01268 = {
        "Topic": "测试用例执行失败[01268]",
        "Code": "01268",
        "Message": {
            "en": "Assertion error: The asserted object1not in object2,{}",
            "ch": "断言错误: 断言的对象1不在对象2中."
        }
    }

    Error_01269 = {
        "Topic": "测试用例执行失败[01269]",
        "Code": "01269",
        "Message": {
            "en": "Assertion error: The asserted object1 in object2,{}",
            "ch": "断言错误: 断言的对象1在对象2中."
        }
    }

    Error_01270 = {
        "Topic": "测试用例执行失败[01270]",
        "Code": "01270",
        "Message": {
            "en": "Assertion error: The asserted object1 is not an instance "
                  "of object2,{}",
            "ch": "断言错误: 断言的对象1不是对象2的实例."
        }
    }

    Error_01271 = {
        "Topic": "测试用例执行失败[01271]",
        "Code": "01271",
        "Message": {
            "en": "Assertion error: The asserted object1 is an instance of "
                  "object2,{}",
            "ch": "断言错误: 断言的对象1是对象2的实例."
        }
    }

    Error_01272 = {
        "Topic": "测试用例执行失败[01272]",
        "Code": "01272",
        "Message": {
            "en": "Assertion error: The difference between object1 and "
                  "object2 is not within the expected range,{}",
            "ch": "断言错误: 断言的对象1与对象2的差值不在预期的范围内."
        }
    }

    Error_01273 = {
        "Topic": "测试用例执行失败[01273]",
        "Code": "01273",
        "Message": {
            "en": "Assertion error: The difference between object1 and "
                  "object2 is not within the expected range,{}",
            "ch": "断言错误: 断言的对象1与对象2的差值不在预期的范围外."
        }
    }

    Error_01274 = {
        "Topic": "测试用例执行失败[01274]",
        "Code": "01274",
        "Message": {
            "en": "Assertion error: The asserted object1 is not "
                  "greater than object2,{}",
            "ch": "断言错误: 断言的对象1小于等于对象2."
        }
    }

    Error_01275 = {
        "Topic": "测试用例执行失败[01275]",
        "Code": "01275",
        "Message": {
            "en": "Assertion error: The asserted object1 is not "
                  "greater than or equal to object2,{}",
            "ch": "断言错误: 断言的对象1小于对象2."
        }
    }

    Error_01276 = {
        "Topic": "测试用例执行失败[01276]",
        "Code": "01276",
        "Message": {
            "en": "Assertion error: The asserted object1 is not less than to "
                  "object2,{}",
            "ch": "断言错误: 断言的对象1大于等于对象2."
        }
    }

    Error_01277 = {
        "Topic": "测试用例执行失败[01277]",
        "Code": "01277",
        "Message": {
            "en": "Assertion error: The asserted object1 is not "
                  "less than or equal to object2,{}",
            "ch": "断言错误: 断言的对象1大于对象2."
        }
    }

    Error_01278 = {
        "Topic": "测试用例执行失败[01278]",
        "Code": "01278",
        "Message": {
            "en": "Assertion error: The asserted of two dict objects "
                  "unequal,{}",
            "ch": "断言错误: 断言的两个字典对象不相等."
        }
    }

    Error_01279 = {
        "Topic": "测试用例执行失败[01279]",
        "Code": "01279",
        "Message": {
            "en": "Assertion error: The asserted of two set objects "
                  "unequal,{}",
            "ch": "断言错误: 断言的两个集合对象不相等."
        }
    }

    Error_01280 = {
        "Topic": "测试用例执行失败[01280]",
        "Code": "01280",
        "Message": {
            "en": "Assertion error: The asserted of two tuple objects "
                  "unequal,{}",
            "ch": "断言错误: 断言的两个元组对象不相等."
        }
    }

    Error_01281 = {
        "Topic": "测试用例执行失败[01281]",
        "Code": "01281",
        "Message": {
            "en": "Assertion error: The asserted of two list objects "
                  "unequal,{}",
            "ch": "断言错误: 断言的两个列表对象不相等."
        }
    }

    Error_01282 = {
        "Topic": "测试用例执行失败[01282]",
        "Code": "01282",
        "Message": {
            "en": "Assertion error: The asserted of two sequence objects "
                  "unequal,{}",
            "ch": "断言错误: 断言的两个序列对象不相等."
        }
    }

    Error_01283 = {
        "Topic": "测试用例执行失败[01283]",
        "Code": "01283",
        "Message": {
            "en": "Assertion error: Assert that two multi-line strings are "
                  "unequal,{}",
            "ch": "断言错误: 断言两个多行字符串不相等."
        }
    }

    ##########################################################################

    Error_01300 = {
        "Topic": "测试任务被人工中止[01300]",
        "Code": "01300",
        "Message": {
            "en": "A user manually terminates the current task on "
                  "the DECC GUI.",
            "ch": "用户在DECC界面上手动终止当前的任务执行."
        }
    }

    Error_01301 = {
        "Topic": "测试任务被人工中止[01301]",
        "Code": "01301",
        "Message": {
            "en": "The test case is not executed(the task is manually "
                  "stopped).",
            "ch": "用例未执行(任务被手动停止)."
        }
    }

    Error_01400 = {
        "Topic": "测试任务被异常中止[01400]",
        "Code": "01400",
        "Message": {
            "en": "An unexpected error occurs in the tool.",
            "ch": "工具内部出现非预期的错误."
        }
    }

    Error_01401 = {
        "Topic": "测试任务被异常中止[01401]",
        "Code": "01401",
        "Message": {
            "en": "The connector is disconnected and fails to be reconnected for "
                  "10 consecutive times.",
            "ch": "connector连接断链，连续10次重连失败."
        }
    }

    Error_01402 = {
        "Topic": "测试任务被异常中止[01402]",
        "Code": "01402",
        "Message": {
            "en": "The Agent scocket service exits abnormally: Failed to "
                  "parse the DECC IDE command message.",
            "ch": "Agent scoket服务异常退出：解析DECC IDE命令消息失败."
        }
    }

    Error_01403 = {
        "Topic": "测试任务被异常中止[01403]",
        "Code": "01403",
        "Message": {
            "en": "The Agent scocket service exits abnormally: Failed to "
                  "decrypt the socket authentication message.",
            "ch": "Agent scoket服务异常退出：socket认证消息解密失败."
        }
    }

    Error_01404 = {
        "Topic": "测试任务被异常中止[01404]",
        "Code": "01404",
        "Message": {
            "en": "The test case is not executed(an unexpected error occurs "
                  "in the tool).",
            "ch": "用例未执行(工具内部出现非预期的错误)."
        }
    }

    Error_01405 = {
        "Topic": "测试任务被异常中止[01405]",
        "Code": "01405",
        "Message": {
            "en": "Dry-run failed: An error is during {} script query.",
            "ch": "dry-run失败：查找{}脚本出错."
        }
    }

    Error_01406 = {
        "Topic": "测试任务被异常中止[01406]",
        "Code": "01406",
        "Message": {
            "en": "Failed to start the xdevice service: Failed to load the "
                  "xdevice-extension extension module.",
            "ch": "拉起xdevice服务失败：加载xdevice-extension扩展模块失败."
        }
    }

    Error_01407 = {
        "Topic": "测试任务被异常中止[01407]",
        "Code": "01407",
        "Message": {
            "en": "Dry-run failed: The syntax format of statement in '{}'.py "
                  "is wrong when parse step parameter, please check! "
                  "statement:{}.",
            "ch": "dry-run失败：在解析step parameter时,'{}'.py中语句的语法格式错"
                  "误,请检查,语句:{}."
        }
    }

    Error_01408 = {
        "Topic": "测试任务被异常中止[01408]",
        "Code": "01408",
        "Message": {
            "en": "Dry-run failed: The syntax format of statement in '{}'.py "
                  "is wrong when parse step content, please check! "
                  "statement:{}.",
            "ch": "dry-run失败：在解析step content时,'{}'.py中语句的语法格式错误，"
                  "请检查!声明:{}."
        }
    }

    Error_01409 = {
        "Topic": "测试任务被异常中止[01409]",
        "Code": "01409",
        "Message": {
            "en": "Dry-run failed: The script '{}.py/pyd' not exist, "
                  "please check!",
            "ch": "dry-run失败：脚本'{}.py/pyd'不存在，请检查!"
        }
    }
    Error_01410 = {
        "Topic": "测试任务被异常中止[01410]",
        "Code": "01410",
        "Message": {
            "en": "Dry-run failed: Load script {} failed!",
            "ch": "dry-run失败：加载脚本{}失败!"
        }
    }

    Error_01411 = {
        "Topic": "测试任务被异常中止[01411]",
        "Code": "01411",
        "Message": {
            "en": "The Agent scocket service exits abnormally: "
                  "An error is reported when the socket message is parsed.",
            "ch": "Agent scoket服务异常退出：socket消息解析处理异常报错."
        }
    }

    Error_01412 = {
        "Topic": "测试任务被异常中止[01412]",
        "Code": "01412",
        "Message": {
            "en": "Environment configuration error: The message format of "
                  "environment configuration is wrong. Please check.",
            "ch": "环境配置异常：环境配置消息格式错误,请查一下."
        }
    }

    Error_01413 = {
        "Topic": "测试任务被异常中止[01413]",
        "Code": "01413",
        "Message": {
            "en": "Environment configuration error: The workspace path {} "
                  "delivered by the client does not exist.",
            "ch": "环境配置异常：客户端下发的工作路径xxx不存在!"
        }
    }

    Error_01414 = {
        "Topic": "测试任务被异常中止[01414]",
        "Code": "01414",
        "Message": {
            "en": "Environment configuration error: test suite type error, "
                  "not in ['Kit', 'OS'].",
            "ch": "环境配置异常：测试套件类型不在【'Kit'， 'OS'】中."
        }
    }

    Error_01415 = {
        "Topic": "测试任务被异常中止[01415]",
        "Code": "01415",
        "Message": {
            "en": "Environment configuration error: The type of the param "
                  "parameter "
                  "delivered by the client is incorrect, which is not a "
                  "known dictionary type.",
            "ch": "环境配置异常：客户端下发的param参数类型错误，不是已知的字典类型."
        }
    }

    Error_01416 = {
        "Topic": "测试任务被异常中止[01416]",
        "Code": "01416",
        "Message": {
            "en": "Dry-run failed: An unknown exception occurred during "
                  "the dry-run process.",
            "ch": "dry-run失败：dry-run过程出现未知异常."
        }
    }

    Error_01417 = {
        "Topic": "测试任务被异常中止[01417]",
        "Code": "01417",
        "Message": {
            "en": "Failed to start the Agent service task because no "
                  "environment is configured before the task is started.",
            "ch": "Agent服务启动任务失败：启动任务前没有配置环境"
        }
    }

    Error_01418 = {
        "Topic": "测试任务被异常中止[01418]",
        "Code": "01418",
        "Message": {
            "en": "An error is reported when the Agent service is started.",
            "ch": "Agent服务启动任务异常报错."
        }
    }

    Error_01419 = {
        "Topic": "测试任务被异常中止[01419]",
        "Code": "01419",
        "Message": {
            "en": "Agent server pull xdevice runner failed.",
            "ch": "Agent服务拉取xdevice服务失败."
        }
    }

    Error_01420 = {
        "Topic": "测试任务被异常中止[01420]",
        "Code": "01420",
        "Message": {
            "en": "Agent server start task retry failed.",
            "ch": "Agent服务启动任务重试失败."
        }
    }

    Error_01421 = {
        "Topic": "测试任务被异常中止[01421]",
        "Code": "01421",
        "Message": {
            "en": "Failed to update the XML Report Str.",
            "ch": "更新xml report str失败."
        }
    }

    Error_01422 = {
        "Topic": "测试任务被异常中止[01422]",
        "Code": "01422",
        "Message": {
            "en": "Failed to start xdevice agent service: An unknown "
                  "exception was encountered.",
            "ch": "启动xdevice agent服务失败：遇到未知异常."
        }
    }

    Error_01423 = {
        "Topic": "测试任务被异常中止[01423]",
        "Code": "01423",
        "Message": {
            "en": "Failed to start the xdevice agent service "
                  "because an error is reported when parsing the args "
                  "parameter.",
            "ch": "启动xdevice agent服务失败：解析args参数报错."
        }
    }

    Error_01424 = {
        "Topic": "测试任务被异常中止[01424]",
        "Code": "01424",
        "Message": {
            "en": "Failed to reclaim the xdevice agent service process.",
            "ch": "回收xdevice agent服务进程失败."
        }
    }

    Error_01425 = {
        "Topic": "测试任务被异常中止[01425]",
        "Code": "01425",
        "Message": {
            "en": "Socket message authentication failed：Decrypt failed due "
                  "to The message component, decrypted message, or key type "
                  "is incorrect.",
            "ch": "socket消息认证失败：消息组件、解密的消息、秘钥类型错误导致解密失败."
        }
    }

    Error_01426 = {
        "Topic": "测试任务被异常中止[01426]",
        "Code": "01426",
        "Message": {
            "en": "Socket message authentication failed：An unknown error "
                  "occurred during message decryption, and the socket message"
                  " authentication failed.",
            "ch": "socket消息认证失败：消息解密遇到未知错误."
        }
    }

    Error_01427 = {
        "Topic": "测试任务被异常中止[01427]",
        "Code": "01427",
        "Message": {
            "en": "devicetest upload generate test report failed.",
            "ch": "devicetest上报任务汇总报告失败."
        }
    }

    Error_01428 = {
        "Topic": "测试任务被异常中止[01428]",
        "Code": "01428",
        "Message": {
            "en": "devicetest upload generate test report failed.",
            "ch": "devicetest上报任务汇总报告失败."
        }
    }

    Error_01429 = {
        "Topic": "测试任务被异常中止[01429]",
        "Code": "01429",
        "Message": {
            "en": "Failed to obtain the list of failed cases during task "
                  "rerun. An unknown error is reported.",
            "ch": "任务重跑获取失败用例列表异常：出现未知报错."
        }
    }

    Error_01430 = {
        "Topic": "测试任务被异常中止[01430]",
        "Code": "01430",
        "Message": {
            "en": "The type of the test case list transferred by the xdevice "
                  "is incorrect.",
            "ch": "xdevice传递重试用例列表类型错误，不是列表."
        }
    }

    Error_01431 = {
        "Topic": "测试任务被异常中止[01431]",
        "Code": "01431",
        "Message": {
            "en": "Dry-run failed: The {} json configuration file of the "
                  "scrpit does not exist. Please check.",
            "ch": "dry-run失败：脚本xxx.json配置文件不存在，请检查!"
        }
    }

    Error_01432 = {
        "Topic": "测试任务被异常中止[01432]",
        "Code": "01432",
        "Message": {
            "en": "Failed to obtain the test case during task re-execution. "
                  "An error is reported when the data returned by the "
                  "xdevice is parsed.",
            "ch": "任务重跑获取失败用例异常：解析xdevice返回的数据报错."
        }
    }

    Error_01433 = {
        "Topic": "测试任务被异常中止[01433]",
        "Code": "01433",
        "Message": {
            "en": "report path is None, Please check",
            "ch": "获取任务报告失败，请检查！"
        }
    }

    Error_01434 = {
        "Topic": "测试任务被异常中止[01434]",
        "Code": "01434",
        "Message": {
            "en": "Failed to instantiate the test runner.",
            "ch": "实例化测试运行程序失败."
        }
    }

    Error_01435 = {
        "Topic": "测试任务被异常中止[01435]",
        "Code": "01435",
        "Message": {
            "en": "Set locales failed.",
            "ch": "设置本地化失败."
        }
    }

    Error_01436 = {
        "Topic": "测试任务被异常中止[01436]",
        "Code": "01436",
        "Message": {
            "en": "The DECC does not deliver the log encryption key.",
            "ch": "DECC未下发日志加密秘钥."
        }
    }

    Error_01437 = {
        "Topic": "测试任务被异常中止[01437]",
        "Code": "01437",
        "Message": {
            "en": "Failed to obtain the spt value of the configuration file, {}.",
            "ch": "获取配置文件的spt值失败."
        }
    }

    Error_01438 = {
        "Topic": "测试任务被异常中止[01438]",
        "Code": "01438",
        "Message": {
            "en": "Loop continues fail.",
            "ch": "循环测试中连续失败."
        }
    }

    ##########################################################################
    # RPC错误码
    Error_01439 = {
        "Topic": "测试用例执行失败[01439]",
        "Code": "01439",
        "Message": {
            "en": "The RPC service fails to be started.",
            "ch": "RPC服务启动失败。"
        }
    }

    Error_01440 = {
        "Topic": "测试用例执行失败[01440]",
        "Code": "01440",
        "Message": {
            "en": "The RPC process is not found.",
            "ch": "RPC进程未查询到。"
        }
    }

    Error_01441 = {
        "Topic": "测试用例执行失败[01441]",
        "Code": "01441",
        "Message": {
            "en": "Device's developer mode is false.",
            "ch": "当前设备开发者模式为关闭状态。"
        }
    }

    Error_01442 = {
        "Topic": "测试用例执行失败[01442]",
        "Code": "01442",
        "Message": {
            "en": "HDC fport tcp port fail.",
            "ch": "HDC端口转发失败。"
        }
    }

    Error_01446 = {
        "Topic": "测试用例执行失败[01446]",
        "Code": "01446",
        "Message": {
            "en": "BIN(ABC) RPC process is not found.",
            "ch": "BIN(ABC) RPC进程未查询到。"
        }
    }

    Error_01447 = {
        "Topic": "测试用例执行失败[01447]",
        "Code": "01447",
        "Message": {
            "en": "BIN(ABC) RPC listening port number is not found.",
            "ch": "BIN(ABC) RPC监听端口号未查询到。"
        }
    }

    # 脚本自定义的异常信息：上报用例结果的fail_msg用脚本自定义的异常信息
    Error_01500 = {
        "Topic": "{}[01500]",
        "Code": "01500",
        "Message": {
            "en": "",
            "ch": "脚本自定义的错误信息."
        }
    }


class ErrorMessage(DetailErrorMassage):
    """
    # 打印异常类信息
    1开头：工具报错
    2开头：测试套
    3开头：环境
    001：未知错误
    """

    class Dict(dict):
        __setattr__ = dict.__setitem__
        __getattr__ = dict.__getitem__

    @classmethod
    def add_attribute(cls):
        for _attribute in dir(DetailErrorMassage):
            if _attribute.startswith("Error_"):
                get_value = getattr(DetailErrorMassage, _attribute)
                if isinstance(get_value, dict):
                    value = cls.dict_to_object(get_value)
                    setattr(cls, _attribute, value)

    @classmethod
    def dict_to_object(cls, dict_obj):
        if not isinstance(dict_obj, dict):
            return dict_obj
        inst = cls.Dict()
        for _key, _value in dict_obj.items():
            inst[_key] = cls.dict_to_object(_value)
        return inst


# 添加类属性
ErrorMessage.add_attribute()

if __name__ == '__main__':
    print(ErrorMessage.Error_01300)
    print(ErrorMessage.Error_01424)
    print(ErrorMessage.Error_01424.Code)
    print(ErrorMessage.Error_01424.Message.ch)
