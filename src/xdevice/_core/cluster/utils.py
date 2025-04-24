#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) Huawei Device Co., Ltd. 2025. All right reserved.
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

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tarfile
import time
import zipfile
from enum import Enum
from typing import List

import psutil
import requests
import urllib3

from _core.constants import CaseResult, Cluster, ConfigConst
from _core.error import Error, ErrorMessage
from _core.executor.bean import SuiteResult
from _core.report.suite_reporter import SuiteReporter
from _core.utils import get_local_ip
from xdevice import Variables
from xdevice import platform_logger

LOG = platform_logger("Cluster")
urllib3.disable_warnings()


class MatchPattern(Enum):
    contains = 0
    equals = 1
    ends_with = 2
    starts_with = 3


class MatchException:

    def __init__(self, error: Error, keyword: str, pattern: MatchPattern):
        self.error = error
        self.keyword = keyword
        self.pattern = pattern


class SVN:

    def __init__(self, url, username, password, project_path):
        self.url = url.replace(" ", "%20")
        self.password = password
        self.project_path = project_path
        self.usr_pwd = f"--username {username} --password {password}"

    def cleanup(self):
        cmd = f"svn cleanup {self.project_path}"
        self.execute_svn_command(cmd)

    def revert(self):
        cmd = f"svn revert -R {self.project_path}"
        self.execute_svn_command(cmd)

    def checkout(self):
        cmd = f"svn checkout --non-interactive {self.url} {self.project_path} {self.usr_pwd}"
        self.execute_svn_command(cmd)

    def update(self):
        self.cleanup()
        self.revert()
        cmd = f"svn update --non-interactive {self.project_path} {self.usr_pwd}"
        self.execute_svn_command(cmd)

    def execute_svn_command(self, cmd: str):
        if Utils.which("svn") is None:
            raise Exception(ErrorMessage.Cluster.Code_0104022.format("svn"))
        log_cmd = cmd.replace(self.password, Cluster.stars)
        exceptions = [
            MatchException(
                ErrorMessage.Cluster.Code_0104014,
                "svn: E",
                MatchPattern.starts_with
            )
        ]
        Utils.execute_command_with_logback(cmd, log_cmd=log_cmd, exceptions=exceptions)
        LOG.info("svn工程下载或更新完成")


class Utils:

    @staticmethod
    def delete_file(pth: str):
        ret = True
        try:
            if os.path.isdir(pth):
                shutil.rmtree(pth)
            if os.path.isfile(pth):
                os.remove(pth)
        except Exception as e:
            LOG.error(e)
            ret = False
        return ret

    @staticmethod
    def hash_message(message: str):
        return hashlib.sha1(message.encode("utf-8")).hexdigest()

    @staticmethod
    def kill_process_and_child(pid):
        """终止进程及其子进程"""
        try:
            process = psutil.Process(pid)
            children = process.children(recursive=True)[::-1]
            if len(children) > 0:
                # 递归查找子进程
                for child in children:
                    Utils.kill_process_and_child(child.pid)
        except psutil.NoSuchProcess:
            pass
        # 终止进程
        Utils.kill_process_by_pid(pid)

    @staticmethod
    def kill_process_by_pid(pid):
        """使用进程id终止进程"""
        cmd = "taskkill /t /f /pid %d" if os.name == "nt" else "kill -9 %d"
        Utils.execute_command(cmd % pid, timeout=5)

    @staticmethod
    def kill_process_by_pobj(p_obj):
        """使用进程对象终止进程"""
        if p_obj.is_alive():
            try:
                p_obj.terminate()
            except PermissionError:
                Utils.kill_process_by_pid(p_obj.pid)
        p_obj.join()

    @staticmethod
    def match_exception(line: str, exceptions: List[MatchException] = None):
        if exceptions is None:
            return
        for exp in exceptions:
            if not isinstance(exp, MatchException):
                continue
            k, p = exp.keyword, exp.pattern
            if p == MatchPattern.contains and k in line \
                    or p == MatchPattern.equals and k == line \
                    or p == MatchPattern.ends_with and line.endswith(k) \
                    or p == MatchPattern.starts_with and line.startswith(k):
                # 抛出指定异常信息
                raise Exception(exp.error.format(line))

    @staticmethod
    def start_a_subprocess(cmd: str, cwd: str = None):
        """使用subprocess拉起子进程执行命令"""
        if cwd is not None and not os.path.exists(cwd):
            raise Exception("current directory does not exist")
        if os.name != "nt":
            cmd = shlex.split(cmd)
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd)

    @staticmethod
    def execute_command(cmd: str, cwd: str = None, timeout: float = 10):
        """执行命令，适用于执行时间较短和输出内容较少的命令"""
        LOG.info(f"execute command: {cmd}")
        output = ""
        proc = None
        try:
            proc = Utils.start_a_subprocess(cmd, cwd=cwd)
            output, _ = proc.communicate(timeout=timeout)
            output = output.decode()
        except subprocess.TimeoutExpired as e:
            proc.kill()
            output = str(e)
        except UnicodeDecodeError:
            output = output.decode("gb2312")
        output = output.replace("\r", "")
        LOG.info(f"output: {output}")
        return output

    @staticmethod
    def execute_command_with_logback(cmd: str, cwd: str = None, timeout: float = None, log_cmd: str = None,
                                     exceptions: List[MatchException] = None):
        """执行命令，并记录其运行输出
        cmd: execute command
        cwd: execute command in directory
        timeout: execute command with timeout(seconds)
        log_cmd: display command in log
        exceptions: match exceptions
        """
        is_timeout = False
        start_time = time.time()
        proc = Utils.start_a_subprocess(cmd, cwd=cwd)
        LOG.info(f"execute command: {cmd if log_cmd is None else log_cmd}")
        if timeout is not None:
            LOG.info(f"execute timeout: {timeout}")
        LOG.info(f"process id: {proc.pid}")
        try:
            while True:
                # 程序退出码
                exit_code = proc.poll()
                if exit_code is not None:
                    break
                if timeout is not None and time.time() - start_time >= timeout:
                    is_timeout = True
                    proc.kill()
                    break
                line = proc.stdout.readline().strip()
                try:
                    if not line:
                        continue
                    line = line.decode("utf-8", "ignore")
                    LOG.debug(line)
                    Utils.match_exception(line, exceptions=exceptions)
                except UnicodeDecodeError:
                    LOG.debug(line.decode("gb2312"))
                except Exception as e:
                    LOG.error(e)
        finally:
            proc.kill()
        return exit_code, is_timeout

    @staticmethod
    def create_zip(src: str, out: str, exclude: List[str] = None, include: List[str] = None):
        """创建zip压缩文件
        src: 目标路径（文件或目录）
        out: 生成压缩文件路径
        exclude: 过滤文件列表，可用正则表达式，如["path/*"]
        include: 添加文件列表，可用正则表达式，如["path/*"]
        @return: 成功返回True，反之返回False
        """
        if not os.path.exists(src):
            return False
        with zipfile.ZipFile(out, "w") as zip_out:
            if os.path.isfile(src):
                zip_out.write(src, os.path.basename(src), zipfile.ZIP_DEFLATED)
            if os.path.isdir(src):
                if exclude:
                    exclude = re.compile("|".join(exclude))
                if include:
                    include = re.compile("|".join(include))
                for top, _, files in os.walk(src):
                    if not files:
                        continue
                    for file_name in files:
                        file_path = os.path.join(top, file_name)
                        if file_path == out:
                            continue
                        temp_path = file_path.replace(src + os.sep, "").replace("\\", "/")
                        if exclude and re.match(exclude, temp_path) is not None:
                            continue
                        if include and re.match(include, temp_path) is None:
                            continue
                        zip_out.write(file_path, temp_path, zipfile.ZIP_DEFLATED)
        return True

    @staticmethod
    def extract_tgz(src: str, to_path: str):
        """解压tar.gz压缩文件
        src: 压缩文件路径
        to_path: 压缩文件解压路径
        @return: 成功返回True，反之返回False
        """
        ret = False
        if not tarfile.is_tarfile(src):
            return ret
        os.makedirs(to_path, exist_ok=True)
        with tarfile.open(src) as tgz_file:
            for file in tgz_file.getnames():
                tgz_file.extract(file, to_path)
            ret = True
        return ret

    @staticmethod
    def extract_zip(src: str, to_path: str):
        """解压zip压缩文件
        src: 压缩文件路径
        to_path: 压缩文件解压路径
        @return: 成功返回True，反之返回False
        """
        ret = False
        if not zipfile.is_zipfile(src):
            return ret
        os.makedirs(to_path, exist_ok=True)
        with zipfile.ZipFile(src) as zip_file:
            infolist = zip_file.infolist()
            # 检测点1：检测文件个数是否大于预期值
            file_count = len(infolist)
            if file_count >= 100 * 10000:
                raise IOError(ErrorMessage.Cluster.Code_0104023.format(src, file_count))
            # 检测点2：检查第一层解压文件总大小是否超过设定的上限值5GB
            total_size = sum(info.file_size for info in infolist)
            if total_size > 5 * (1 << 30):
                raise IOError(ErrorMessage.Cluster.Code_0104024.format(src, total_size))
            # 检查点3：检查第一层解压文件总大小是否超过磁盘剩余空间
            if total_size >= psutil.disk_usage(to_path).free:
                raise IOError(ErrorMessage.Cluster.Code_0104025.format(src, total_size))
            # 所有检查点均通过，解压所有文件
            for filename in zip_file.namelist():
                zip_file.extract(filename, to_path)
            ret = True
        return ret

    @staticmethod
    def which(cmd: str):
        return shutil.which(cmd) or shutil.which(cmd + ".exe")


def create_empty_result(report_path, case_name: str, error_message: str):
    """创建空的用例结果xml"""
    LOG.info(f"case name: {case_name}, error message: {error_message}")
    result_path = os.path.join(report_path, "result")
    os.makedirs(result_path, exist_ok=True)

    suite_result = SuiteResult()
    suite_result.suite_name = case_name
    suite_result.stacktrace = error_message
    suite_reporter = SuiteReporter(
        [(suite_result, [])], case_name, result_path,
        message=error_message, result_kind=CaseResult.unavailable)
    suite_reporter.create_empty_report()


def do_request(url, headers=None, body=None, method="POST", **kwargs):
    if headers is None:
        headers = {}
    if body is None:
        body = {}
    timeout = kwargs.get("timeout", (10, 60))
    verify = kwargs.get("verify", False)

    rsp = None
    try:
        rsp = requests.request(method, url, json=body, headers=headers, timeout=timeout, verify=verify)
        code = rsp.status_code
        rsp_msg = rsp.content.decode()
    except Exception as e:
        code = 400
        rsp_msg = json.dumps({"status": "failed", "message": str(e)})
    finally:
        if rsp is not None:
            rsp.close()
    return code, rsp_msg


def console_create_task(template_file):
    """提供接口在xdevice命令行中创建测试任务"""
    if not os.path.exists(template_file):
        LOG.error(ErrorMessage.Cluster.Code_0104027.format(template_file))
        return False
    try:
        with open(template_file, encoding="utf-8") as json_file:
            body = json.load(json_file)
        from .models import TaskTemplate
        TaskTemplate.model_validate(body)
    except Exception as e:
        LOG.error(ErrorMessage.Cluster.Code_0104028)
        LOG.error(e)
        return False
    cluster = Variables.config.cluster
    url = cluster.get(ConfigConst.control_service_url) + "/controller/v1/task/create"
    LOG.info(f"create the controller task with body: {body}")
    code, rsp_msg = do_request(url, body=body)
    LOG.info(f"create the controller task response code: {code}")
    LOG.info(f"create the controller task response body: {rsp_msg}")
    if code == 201 and json.loads(rsp_msg).get("status") == "ok":
        LOG.info("create the controller task successfully")
    else:
        LOG.error(ErrorMessage.Cluster.Code_0104029.format(rsp_msg))
    return True


def console_list_devices():
    cluster = Variables.config.cluster
    url = cluster.get(ConfigConst.control_service_url) + "/controller/v1/device/list-all"
    code, rsp_msg = do_request(url, method="GET")
    if code != 200:
        LOG.error(ErrorMessage.Cluster.Code_0104030.format(rsp_msg))
        return
    print("Controller devices:")
    result = json.loads(rsp_msg).get("result", [])
    if not result:
        print("No data")
        return
    line = "{:<3}  {:<15}  {:<32}  {:<12}  {:<10}  {:<10}  {:<15}"
    print(line.format("ID", "IP", "SN", "OS", "Type", "State", "Usage"))
    for r in result:
        print(line.format(r.get("id"), r.get("ip"), r.get("sn"), r.get("os"),
                          r.get("type"), r.get("state"), r.get("usage_state")))


def console_list_task(task_id: str = ""):
    if task_id:
        uri = f"/controller/v1/task/{task_id}/list"
    else:
        uri = "/controller/v1/task/list-all"
    cluster = Variables.config.cluster
    url = cluster.get(ConfigConst.control_service_url) + uri
    code, rsp_msg = do_request(url, method="GET")
    if code != 200:
        LOG.error(ErrorMessage.Cluster.Code_0104031.format(rsp_msg))
        return
    print("Controller tasks:")
    result = json.loads(rsp_msg).get("result", [])
    if not result:
        print("No data")
        return
    line = "{:<26}  {:<10}  {}"
    print(line.format("TaskID", "State", "ReportUrl"))
    for r in result:
        print(line.format(r.get("id"), r.get("state"), r.get("report_url")))


def report_worker_device(sn, model, version, device_os, device_type, device_state):
    cluster = Variables.config.cluster
    if cluster.get(ConfigConst.service_mode) != Cluster.worker:
        return
    service_port = cluster.get(ConfigConst.service_port) or Cluster.service_port
    url = cluster.get(ConfigConst.control_service_url) + "/controller/v1/device/add"
    local_ip = get_local_ip()
    body = [{
        "ip": local_ip,
        "sn": sn,
        "os": device_os if device_os != "default" else "device",
        "type": device_type if device_type != "default" else "phone",
        "model": model,
        "version": version,
        "worker_url": f"http://{local_ip}:{service_port}",
        "state": device_state.value if isinstance(device_state, Enum) else device_state
    }]
    LOG.info(f"report worker device: {body}")
    code, rsp_msg = do_request(url, body=body)
    LOG.info(f"report worker device response code: {code}")
    LOG.info(f"report worker device response body: {rsp_msg}")
    if code == 200:
        LOG.info("report worker device successfully")
    else:
        LOG.error(ErrorMessage.Cluster.Code_0104032.format(rsp_msg))


def upload_task_end(task_id, block_id, report_path):
    cluster = Variables.config.cluster
    url = cluster.get(ConfigConst.control_service_url) + "/controller/v1/task/upload-end"
    data = {"task_id": task_id, "block_id": block_id}
    LOG.info(f"upload task end: {data}")
    if os.path.exists(report_path):
        filename = block_id + ".zip"
        report_zip = os.path.join(report_path, filename)
        Utils.create_zip(
            report_path,
            report_zip,
            exclude=["log/task_log.log"],
            include=["details/*", "log/*", "result/*"]
        )
        with open(report_zip, "rb") as file_fd:
            files = {"file": (filename, file_fd, "application/zip")}
            rsp = requests.post(url, data=data, files=files, timeout=30)
    else:
        rsp = requests.post(url, data=data, timeout=30)
    code, rsp_msg = rsp.status_code, rsp.content.decode()
    rsp.close()
    LOG.info(f"upload task end response code: {code}")
    LOG.info(f"upload task end response body: {rsp_msg}")
    if code == 200:
        LOG.info("upload task end successfully")
    else:
        LOG.error(ErrorMessage.Cluster.Code_0104033.format(rsp_msg))
