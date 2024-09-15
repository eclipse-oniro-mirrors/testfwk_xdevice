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
import os
import sys
import time
import re

from xdevice import DeviceTestType
from xdevice import FilePermission
from xdevice import HcpTestMode
from xdevice import convert_mac
from xdevice import ExecuteTerminate
from xdevice import platform_logger
from ohos.error import ErrorMessage
from ohos.exception import LiteDeviceTimeout
from ohos.exception import LiteDeviceConnectError
from ohos.exception import LiteDeviceExecuteCommandError

__all__ = ["generate_report", "LiteHelper"]

CPP_TEST_STANDARD_SIGN = "[==========]"
CPP_TEST_END_SIGN = "Gtest xml output finished"
CPP_SYS_STANDARD_SIGN = "OHOS #"
CPP_ERR_MESSAGE = "[ERR]No such file or directory: "
CTEST_STANDARD_SIGN = "Start to run test suite"
AT_CMD_ENDS = "OK"
CTEST_END_SIGN = "All the test suites finished"
CPP_TEST_STOP_SIGN = "Test Stop"
CPP_TEST_MOUNT_SIGN = "not mount properly"

_START_JSUNIT_RUN_MARKER = "[start] start run suites"
_END_JSUNIT_RUN_MARKER = "[end] run suites end"
INSTALL_END_MARKER = "resultMessage is install success !"
PRODUCT_PARAMS_START = "To Obtain Product Params Start"
PRODUCT_PARAMS_END = "To Obtain Product Params End"

PATTERN = re.compile(r'\x1B(\[([0-9]{1,2}(;[0-9]{1,2})*)?m)*')
TIMEOUT = 90
STATUS_OK_CODE = 200
LOG = platform_logger("DmlibLite")


def check_open_source_test(result_output):
    if result_output.find(CPP_TEST_STANDARD_SIGN) == -1 and \
            ("test pass" in result_output.lower() or
             "test fail" in result_output.lower() or
             "tests pass" in result_output.lower() or
             "tests fail" in result_output.lower()):
        return True
    return False


def check_read_test_end(result=None, input_command=None):
    temp_result = result.replace("\n", "")
    index = result.find(input_command) + len(input_command)
    result_output = result[index:]
    if input_command.startswith("./"):
        if result_output.find(CPP_TEST_STANDARD_SIGN) != -1:
            if result_output.count(CPP_TEST_STANDARD_SIGN) == 2 or \
                    result_output.find(CPP_TEST_END_SIGN) != -1:
                return True
        if check_open_source_test(result_output):
            return True
        if result_output.find(_START_JSUNIT_RUN_MARKER) >= 1 and \
                result_output.find(_END_JSUNIT_RUN_MARKER) >= 1:
            return True

        if result_output.find(INSTALL_END_MARKER) != -1:
            return True
        if (result_output.find(CPP_TEST_MOUNT_SIGN) != -1
                and result_output.find(CPP_TEST_STOP_SIGN) != -1):
            LOG.info("Find test stop")
            return True
        if "%s%s" % (CPP_ERR_MESSAGE, input_command[2:]) in result_output:
            LOG.error("Execute file not exist, result is %s" % result_output,
                      error_no="00402")
            raise LiteDeviceExecuteCommandError(ErrorMessage.Common.Code_0301005)
    elif input_command.startswith("zcat"):
        return False
    elif input_command == "uname":
        is_linux_uname = "Linux" in result_output and "# " in result_output
        is_liteos_uname = "OHOS #" in result_output or "# " in result_output
        if is_linux_uname or is_liteos_uname:
            return True
    elif input_command.startswith("chmod +x") and input_command.find("query.bin"):
        if PRODUCT_PARAMS_END in result_output:
            return True
    else:
        if "OHOS #" in result_output or "# " in result_output:
            if input_command == "reboot" or input_command == "reset":
                return False
            if input_command.startswith("mount"):
                if "Mount nfs finished." not in result_output:
                    return False
            return True
    return False


def generate_report(receiver, result):
    if result and receiver:
        if result:
            receiver.__read__(result)
            receiver.__done__()


def get_current_time():
    current_time = time.time()
    local_time = time.localtime(current_time)
    data_head = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
    millisecond = (current_time - int(current_time)) * 1000
    return "%s.%03d" % (data_head, millisecond)


class LiteHelper:
    @staticmethod
    def execute_remote_cmd_with_timeout(telnet, command="", timeout=TIMEOUT,
                                        receiver=None):
        """
        Executes command on the device.

        Parameters:
            telnet:
            command: the command to execute
            timeout: timeout for read result
            receiver: parser handler
        """
        from xdevice import Binder
        time.sleep(2)
        start_time = time.time()
        status = True
        error_message = ""
        result = ""
        if not telnet:
            raise LiteDeviceConnectError(ErrorMessage.Device.Code_0303018)

        telnet.write(command.encode('ascii') + b"\n")
        while time.time() - start_time < timeout:
            data = telnet.read_until(bytes(command, encoding="utf8"),
                                     timeout=1)
            data = PATTERN.sub('', data.decode('gbk', 'ignore')).replace(
                "\r", "")
            result = "{}{}".format(result, data)
            if command in result:
                break

        expect_result = [bytes(CPP_TEST_STANDARD_SIGN, encoding="utf8"),
                         bytes(CPP_SYS_STANDARD_SIGN, encoding="utf8"),
                         bytes(CPP_TEST_END_SIGN, encoding="utf8"),
                         bytes(CPP_TEST_STOP_SIGN, encoding="utf8")]
        while time.time() - start_time < timeout:
            if not Binder.is_executing():
                raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
            _, _, data = telnet.expect(expect_result, timeout=1)
            data = PATTERN.sub('', data.decode('gbk', 'ignore')).replace(
                "\r", "")
            result = "{}{}".format(result, data)
            if receiver and data:
                receiver.__read__(data)
            if check_read_test_end(result, command):
                break
        else:
            error_message = "execute %s timed out %s " % (command, timeout)
            status = False

        if receiver:
            receiver.__done__()

        if not status and command.startswith("uname"):
            raise LiteDeviceTimeout(ErrorMessage.Device.Code_0303014.format(command))

        return result, status, error_message

    @staticmethod
    def read_local_output_test(com=None, command=None, timeout=TIMEOUT,
                               receiver=None):
        input_command = command
        start_time = time.time()
        # 增加对执行测试套命令时
        if HcpTestMode.hcp_mode and input_command.startswith("./") and input_command.find(".bin") and (
                "--gtest_list_tests" not in input_command):
            device_log_file = getattr(sys, "device_log_file", "")
            LOG.info("device_log_file:{}".format(device_log_file))
            result, status, error_message = LiteHelper.parser_hcp_test_suite_execute_log(com, start_time, timeout,
                                                                                         input_command, device_log_file)
        else:
            # 非测试套执行命令
            result, status, error_message = LiteHelper.parser_common_execute(com, start_time, timeout, input_command,
                                                                             receiver)

        if receiver:
            receiver.__done__()

        if not status and command.startswith("uname"):
            raise LiteDeviceTimeout(ErrorMessage.Device.Code_0303014.format(command))
        return result, status, error_message

    @staticmethod
    def parser_hcp_test_suite_execute_log(com, start_time, timeout, input_command, device_log_file):
        from xdevice import Binder
        result = ""
        error_message = ""
        status = True
        # 增加对执行测试套命令时
        device_log_file_open = os.open(device_log_file, os.O_WRONLY |
                                       os.O_CREAT | os.O_APPEND,
                                       FilePermission.mode_755)
        try:
            with os.fdopen(device_log_file_open, "a") as file_name:
                while time.time() - start_time < timeout:
                    if not Binder.is_executing():
                        raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
                    if com.in_waiting == 0:
                        continue
                    data = com.read(com.in_waiting).decode('gbk', errors='ignore')
                    data = PATTERN.sub('', data).replace("\r", "")
                    data = convert_mac(data)
                    file_name.write(data)
                    file_name.flush()
                    time_diff = time.time() - start_time
                    if timeout - 60 <= time_diff:
                        if LiteHelper.check_string_in_file(device_log_file, CPP_TEST_END_SIGN):
                            break
                    if CPP_TEST_END_SIGN in data or "Gtest xml" in data or "output finished" in data:
                        LOG.info("parser hcptest end:{}".format(data))
                        break
                else:
                    error_message = "execute {} timed out {} ".format(input_command, timeout)
                    status = False
        except (UnicodeDecodeError, IOError, OSError) as exception:
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03403")
            LOG.exception(exception, exc_info=True, error_no="03403")
            raise exception
        except Exception as exception:
            exception_error = "run parser hcptest suite execute log error:{}".format(exception)
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03403")
            LOG.exception(exception_error, exc_info=True, error_no="03403")
            raise exception
        finally:
            LOG.debug("run parser hcptest end")
        return " ", status, error_message

    @staticmethod
    def check_string_in_file(file_path, target_string):
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if target_string in line:
                        LOG.info("{} is exist!".format(target_string))
                        return True
            return False
        except FileNotFoundError:
            LOG.info("{} doesn't exist!".format(target_string))
            return False

    @staticmethod
    def parser_common_execute(com, start_time, timeout, input_command, receiver):
        from xdevice import Binder
        result = ""
        error_message = ""
        status = True
        while time.time() - start_time < timeout:
            if not Binder.is_executing():
                raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
            if com.in_waiting == 0:
                continue
            data = com.read(com.in_waiting).decode('gbk', errors='ignore')
            data = PATTERN.sub('', data).replace("\r", "")
            result = "{}{}".format(result, data)
            if receiver and data:
                receiver.__read__(data)
            if check_read_test_end(result, input_command):
                break
        else:
            error_message = "execute %s timed out %s " % (input_command, timeout)
            status = False
        return result, status, error_message

    @staticmethod
    def read_local_output_ctest(com=None, command=None, timeout=TIMEOUT,
                                receiver=None):
        result = ""
        input_command = command

        start = time.time()
        from xdevice import Binder
        while True:
            if not Binder.is_executing():
                raise ExecuteTerminate(ErrorMessage.Common.Code_0301013)
            data = com.readline().decode('gbk', errors='ignore')
            data = PATTERN.sub('', data)
            if isinstance(input_command, list):
                if len(data.strip()) > 0:
                    data = "{} {}".format(get_current_time(), data)
                    if data and receiver:
                        receiver.__read__(data.replace("\r", ""))
                    result = "{}{}".format(result, data.replace("\r", ""))
                    if re.search(r"\d+\s+Tests\s+\d+\s+Failures\s+\d+\s+"
                                 r"Ignored", data):
                        start = time.time()
                    if CTEST_END_SIGN in data:
                        break
                if (int(time.time()) - int(start)) > timeout:
                    break
            else:
                result = "{}{}".format(
                    result, data.replace("\r", "").replace("\n", "").strip())
                if AT_CMD_ENDS in data:
                    return result, True, ""
                if (int(time.time()) - int(start)) > timeout:
                    return result, False, ""

        if receiver:
            receiver.__done__()
        LOG.info('Info: execute command success')
        return result, True, ""

    @staticmethod
    def read_local_output(com=None, command=None, case_type="",
                          timeout=TIMEOUT, receiver=None):
        if case_type == DeviceTestType.ctest_lite:
            return LiteHelper.read_local_output_ctest(com, command,
                                                      timeout, receiver)
        else:
            return LiteHelper.read_local_output_test(com, command,
                                                     timeout, receiver)

    @staticmethod
    def execute_local_cmd_with_timeout(com, **kwargs):
        """
        Execute command on the serial and read all the output from the serial.
        """
        args = kwargs
        command = args.get("command", None)
        input_command = command
        case_type = args.get("case_type", "")
        timeout = args.get("timeout", TIMEOUT)
        receiver = args.get("receiver", None)
        if not com:
            raise LiteDeviceConnectError(ErrorMessage.Device.Code_0303010)

        LOG.info("local_{} execute command shell {} with "
                 "timeout {}s".format(com.port, convert_mac(command), str(timeout)))

        if isinstance(command, str):
            command = command.encode("utf-8")
            if command[-2:] != b"\r\n":
                command = command.rstrip() + b'\r\n'
                com.write(command)
        else:
            com.write(command)
        return LiteHelper.read_local_output(
            com, command=input_command, case_type=case_type, timeout=timeout,
            receiver=receiver)

    @staticmethod
    def execute_local_command(com, command):
        """
        Execute command on the serial and read all the output from the serial.
        """
        if not com:
            raise LiteDeviceConnectError(ErrorMessage.Device.Code_0303010)

        LOG.info(
            "local_%s execute command shell %s" % (com.port, convert_mac(command)))
        command = command.encode("utf-8")
        if command[-2:] != b"\r\n":
            command = command.rstrip() + b'\r\n'
            com.write(command)
