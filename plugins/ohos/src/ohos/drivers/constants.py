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
import subprocess
import threading
import time

from xdevice import convert_mac
from xdevice import ConfigConst
from xdevice import FilePermission
from xdevice import ParamError
from xdevice import get_config_value
from xdevice import platform_logger
from ohos.config.config_manager import OHOSUserConfigManager
from ohos.error import ErrorMessage

LOG = platform_logger("DriverConstant")
TIME_OUT = 300 * 1000


def get_xml_output(config, json_config):
    xml_output = config.testargs.get("xml-output")
    if not xml_output:
        if get_config_value('xml-output', json_config.get_driver(), False):
            xml_output = get_config_value('xml-output',
                                          json_config.get_driver(), False)
        else:
            xml_output = "false"
    else:
        xml_output = xml_output[0]
    xml_output = str(xml_output).lower()
    return xml_output


def get_nfs_server(request):
    config_manager = OHOSUserConfigManager(
        config_file=request.get(ConfigConst.configfile, ""),
        env=request.get(ConfigConst.test_environment, ""))
    remote_info = config_manager.get_user_config("testcases/server",
                                                 filter_name="NfsServer")
    if not remote_info:
        err_msg = ErrorMessage.Config.Code_0302018
        LOG.error(err_msg)
        raise ParamError(err_msg)
    return remote_info


def init_remote_server(lite_instance, request=None):
    config_manager = OHOSUserConfigManager(
        config_file=request.get(ConfigConst.configfile, ""),
        env=request.get(ConfigConst.test_environment, ""))
    linux_dict = config_manager.get_user_config("testcases/server")

    if linux_dict:
        setattr(lite_instance, "linux_host", linux_dict.get("ip"))
        setattr(lite_instance, "linux_port", linux_dict.get("port"))
        setattr(lite_instance, "linux_directory", linux_dict.get("dir"))

    else:
        raise ParamError(ErrorMessage.Config.Code_0302019)


def create_empty_result_file(filepath, filename, error_message):
    error_message = str(error_message)
    error_message = error_message.replace("\"", "&quot;")
    error_message = error_message.replace("<", "&lt;")
    error_message = error_message.replace(">", "&gt;")
    error_message = error_message.replace("&", "&amp;")
    if filename.endswith(".hap"):
        filename = filename.split(".")[0]
    if not os.path.exists(filepath):
        file_open = os.open(filepath, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                            FilePermission.mode_755)
        with os.fdopen(file_open, "w") as file_desc:
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime())
            file_desc.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            file_desc.write('<testsuites tests="0" failures="0" '
                            'disabled="0" errors="0" timestamp="%s" '
                            'time="0" name="%s">\n' % (time_stamp, filename))
            file_desc.write(
                '  <testsuite name="%s" tests="0" failures="0" '
                'disabled="0" errors="0" time="0.0" '
                'unavailable="1" message="%s">\n' %
                (filename, error_message))
            file_desc.write('  </testsuite>\n')
            file_desc.write('</testsuites>\n')
            file_desc.flush()
    return


def get_result_savepath(testsuit_path, result_rootpath):
    findkey = "%stests%s" % (os.sep, os.sep)
    filedir, _ = os.path.split(testsuit_path)
    pos = filedir.find(findkey)
    if -1 != pos:
        subpath = filedir[pos + len(findkey):]
        pos1 = subpath.find(os.sep)
        if -1 != pos1:
            subpath = subpath[pos1 + len(os.sep):]
            result_path = os.path.join(result_rootpath, "result", subpath)
        else:
            result_path = os.path.join(result_rootpath, "result")
    else:
        result_path = os.path.join(result_rootpath, "result")

    if not os.path.exists(result_path):
        os.makedirs(result_path)

    LOG.info("Result save path = %s" % result_path)
    return result_path


class ResultManager(object):
    def __init__(self, testsuit_path, result_rootpath, device,
                 device_testpath):
        self.testsuite_path = testsuit_path
        self.result_rootpath = result_rootpath
        self.device = device
        self.device_testpath = device_testpath
        self.testsuite_name = os.path.basename(self.testsuite_path)
        self.is_coverage = False

    def set_is_coverage(self, is_coverage):
        self.is_coverage = is_coverage

    def get_test_results(self, error_message=""):
        # Get test result files
        filepath = self.obtain_test_result_file()
        if not os.path.exists(filepath):
            create_empty_result_file(filepath, self.testsuite_name,
                                      error_message)

        # Get coverage data files
        if self.is_coverage:
            self.obtain_coverage_data()

        return filepath

    def obtain_test_result_file(self):
        result_savepath = get_result_savepath(self.testsuite_path,
                                              self.result_rootpath)
        if self.testsuite_path.endswith('.hap'):
            filepath = os.path.join(result_savepath, "%s.xml" % str(
                self.testsuite_name).split(".")[0])

            remote_result_name = ""
            if self.device.is_file_exist(os.path.join(self.device_testpath,
                                                      "testcase_result.xml")):
                remote_result_name = "testcase_result.xml"
            elif self.device.is_file_exist(os.path.join(self.device_testpath,
                                                        "report.xml")):
                remote_result_name = "report.xml"

            if remote_result_name:
                self.device.pull_file(
                    os.path.join(self.device_testpath, remote_result_name),
                    filepath)
            else:
                LOG.error("%s no report file", self.device_testpath)

        else:
            filepath = os.path.join(result_savepath, "%s.xml" %
                                    self.testsuite_name)
            remote_result_file = os.path.join(self.device_testpath,
                                              "%s.xml" % self.testsuite_name)

            if self.device.is_file_exist(remote_result_file):
                self.device.pull_file(remote_result_file, result_savepath)
            else:
                LOG.error("%s not exists", remote_result_file)
        return filepath

    def is_exist_target_in_device(self, path, target):
        command = "ls -l %s | grep %s" % (path, target)

        check_result = False
        stdout_info = self.device.execute_shell_command(command)
        if stdout_info != "" and stdout_info.find(target) != -1:
            check_result = True
        return check_result

    def obtain_coverage_data(self):
        java_cov_path = os.path.abspath(
            os.path.join(self.result_rootpath, "..", "coverage/data/exec"))
        dst_target_name = "%s.exec" % self.testsuite_name
        src_target_name = "jacoco.exec"
        if self.is_exist_target_in_device(self.device_testpath,
                                          src_target_name):
            if not os.path.exists(java_cov_path):
                os.makedirs(java_cov_path)
            self.device.pull_file(
                os.path.join(self.device_testpath, src_target_name),
                os.path.join(java_cov_path, dst_target_name))

        cxx_cov_path = os.path.abspath(
            os.path.join(self.result_rootpath, "..", "coverage/data/cxx",
                         self.testsuite_name))
        target_name = "obj"
        if self.is_exist_target_in_device(self.device_testpath, target_name):
            if not os.path.exists(cxx_cov_path):
                os.makedirs(cxx_cov_path)
            src_file = os.path.join(self.device_testpath, target_name)
            self.device.pull_file(src_file, cxx_cov_path)


class JavaThread(threading.Thread):
    def __init__(self, name, log_path, command, execute_jar_path, handler=None, wait_time=0):
        super().__init__()
        self.name = name
        self.log_path = log_path
        self.command = command
        self.handler = handler
        self.wait_time = wait_time
        self.jar_path = execute_jar_path
        self.jar_process = None
        self.finished = threading.Event()

    def cancel(self):
        """Stop the timer if it hasn't finished yet"""
        self.finished.set()

    def run_java_test(self):
        LOG.info('start to run java testcase')
        LOG.debug('run java command: {}'.format(convert_mac(self.command)))
        self.jar_process = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                            cwd=self.jar_path)
        jar_log_open = os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                               FilePermission.mode_755)
        with os.fdopen(jar_log_open, "a+") as file_data:
            for line in iter(self.jar_process.stdout.readline, b''):
                line = line.decode('GBK')
                file_data.write(line)
                if self.handler:
                    self.handler.__read__(line.replace('\r', ''))
        self.jar_process.stdout.close()
        self.jar_process.wait()

    def run(self):
        self.finished.wait(self.wait_time)
        if not self.finished.is_set():
            self.run_java_test()
        self.finished.set()

    def stop(self):
        LOG.info("Stop java process")
        self.kill_proc_and_subproc(self.jar_process)

    def kill_proc_and_subproc(self, proc):
        """ Stops a process started and subprocess
        started by process by kill_proc_and_subproc.
        """
        try:
            cmd = "taskkill /T /F /PID {}".format(str(proc.pid))
            subprocess.Popen(cmd.split(),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             shell=False)

        except Exception as _err:
            LOG.debug("kill subprocess exception error:{}".format(_err))
