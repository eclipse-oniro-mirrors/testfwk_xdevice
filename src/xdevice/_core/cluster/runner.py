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

import base64
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import unquote

import requests
from filelock import FileLock

from _core.constants import Cluster, FilePermission
from _core.error import ErrorMessage
from xdevice import platform_logger
from .models import TaskInfo
from .utils import SVN, Utils, create_empty_result

LOG = platform_logger("Cluster")
thread_pool = ThreadPoolExecutor()


class Runner:

    def __init__(self, task_info: TaskInfo):
        self.task_info = task_info

        self.case_names = self.task_info.cases
        self.task_id = self.task_info.task_id
        self.project_path = ""
        self.report_path = ""

    def mark_cases_error(self, case_names, error_message):
        for case_name in case_names:
            create_empty_result(self.report_path, case_name, error_message)

    def run(self):
        pass

    def prepare_project(self):
        """准备测试工程"""
        project = self.task_info.project
        url = project.url.strip()
        mode = project.mode.strip().lower()
        branch = project.branch.strip()
        username = project.username.strip()
        password = base64.b64decode(project.password).decode()
        relative_path = project.relative_path.strip()

        if mode == "local":
            self.project_path = url
        elif mode == "git":
            self.__prepare_git_project(url, username, password, branch)
        elif mode == "svn":
            self.__prepare_svn_project(url, username, password)
        elif mode == "http":
            self.__download_file(url)
        else:
            raise Exception(ErrorMessage.Cluster.Code_0104002.format(mode))

        if not self.project_path or not os.path.exists(self.project_path):
            raise Exception(ErrorMessage.Cluster.Code_0104003.format(self.project_path))
        if relative_path:
            project_relative_path = os.path.join(self.project_path, relative_path)
            if not os.path.exists(project_relative_path):
                raise Exception(ErrorMessage.Cluster.Code_0104004.format(project_relative_path))
            self.project_path = relative_path

    def __prepare_git_project(self, url, username, password, branch):
        """准备git测试工程"""
        if not url:
            raise Exception(ErrorMessage.Cluster.Code_0104005)
        if not username:
            raise Exception(ErrorMessage.Cluster.Code_0104006)
        if not password:
            raise Exception(ErrorMessage.Cluster.Code_0104007)
        if not branch:
            raise Exception(ErrorMessage.Cluster.Code_0104008)
        LOG.info("准备git测试工程，等待获取文件锁")
        with FileLock(os.path.join(Cluster.project_root_path, ".lock_file")):
            LOG.info("准备git测试工程，已获取文件锁")
            local_path = self.__find_project_record(url, "git", branch=branch)
            if os.path.exists(local_path):
                cmd = "git pull -f"
                exit_code, _ = Utils.execute_command_with_logback(cmd, cwd=local_path)
            else:
                head, tail = "", ""
                if url.startswith("http://"):
                    head, tail = "http://", url[7:]
                elif url.startswith("https://"):
                    head, tail = "https://", url[8:]
                if not head:
                    raise Exception(ErrorMessage.Cluster.Code_0104009.format(url))
                usr_pwd_url = head + f"{username}:{password}@" + tail
                cmd = f"git clone {usr_pwd_url} -b {branch} {local_path}"
                cwd = Cluster.project_root_path
                log_cmd = cmd.replace(password, Cluster.stars)
                exit_code, _ = Utils.execute_command_with_logback(cmd, cwd=cwd, log_cmd=log_cmd)
                if exit_code == 0:
                    self.__make_project_record(local_path, f"{url} -branch {branch}")
        LOG.info("准备git测试工程，已释放文件锁")
        if exit_code != 0:
            raise Exception(ErrorMessage.Cluster.Code_0104010)
        LOG.info("准备git测试工程完成")
        self.project_path = local_path

    def __prepare_svn_project(self, url, username, password):
        """准备svn测试工程"""
        if not url:
            raise Exception(ErrorMessage.Cluster.Code_0104011)
        if not username:
            raise Exception(ErrorMessage.Cluster.Code_0104012)
        if not password:
            raise Exception(ErrorMessage.Cluster.Code_0104013)
        LOG.info("")
        LOG.info("查找svn工程下载记录，等待获取文件锁")
        with FileLock(os.path.join(Cluster.project_root_path, ".lock_file")):
            LOG.info("查找svn工程下载记录，已获取文件锁")
            local_path = self.__find_project_record(url, "svn")
        LOG.info("查找svn工程下载记录，已释放文件锁")

        LOG.info("准备svn测试工程，等待获取文件锁")
        with FileLock(os.path.join(local_path, ".lock_file")):
            LOG.info("准备svn测试工程，已获取文件锁")
            svn = SVN(url, username, password, local_path)
            if self.__get_svn_info(local_path) is None:
                self.__clean_project(local_path)
                LOG.info("正在检出工程文件到本地，请等待...")
                svn.checkout()
            else:
                LOG.info("正在更新工程文件到本地，请等待...")
                svn.update()
            # 增加更新间隔时间
            time.sleep(5)
        LOG.info("准备svn测试工程，已释放文件锁")
        LOG.info("准备svn测试工程完成")
        self.project_path = local_path

    def __download_file(self, url):
        """下载测试文件"""
        if not url:
            raise Exception(ErrorMessage.Cluster.Code_0104015)
        with FileLock(os.path.join(Cluster.project_root_path, ".lock_file")):
            file_name = url.rstrip("/").split("/")[-1]
            save_path = self.__find_project_record(url, "http")
            save_file = os.path.join(save_path, file_name)
            self.project_path = save_path
            LOG.info(f"download file from {url}")
            rsp = requests.get(url, stream=True, timeout=10, verify=False)
            try:
                if rsp.status_code != 200:
                    raise Exception(ErrorMessage.Cluster.Code_0104016.format(rsp.content.decode()))
                rsp_headers = rsp.headers
                file_size = int(rsp_headers.get("Content-Length", "0"))
                if file_size > 0:
                    LOG.info(f"download file size: {file_size}")
                if os.path.exists(save_file):
                    actual_size = os.path.getsize(save_file)
                    LOG.info(f"exist file: {save_file}")
                    LOG.info(f"exist file size: {actual_size}")
                    # 没有给出文件大小或大小一致
                    if file_size == 0 or file_size == actual_size:
                        return
                    LOG.info("different file size, delete the file and download it again")
                    os.remove(save_file)
                save_file_fd = os.open(save_file, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
                with os.fdopen(save_file_fd, "wb+") as s_file:
                    for chunk in rsp.iter_content(chunk_size=4096):
                        s_file.write(chunk)
                    s_file.flush()
                if file_size != 0 and file_size != os.path.getsize(save_file):
                    raise Exception(ErrorMessage.Cluster.Code_0104017)
                LOG.info(f"download file success, path: {save_file}")

                flag1 = (file_name.endswith(".tar.gz") or file_name.endswith(".tgz")) \
                        and not Utils.extract_tgz(save_file, save_path)
                flag2 = file_name.endswith(".zip") \
                        and not Utils.extract_zip(save_file, save_path)
                if not flag1 or not flag2:
                    raise Exception(ErrorMessage.Cluster.Code_0104018.format(save_file))
            finally:
                rsp.close()

    def __find_project_record(self, repo_url: str, manage_mode: str, branch="master"):
        """查找工程下载记录"""
        local_path = ""
        repo_url = repo_url.rstrip("/")
        record_url = repo_url
        if manage_mode == "git":
            record_url = f"{repo_url} -branch {branch}"
        LOG.info(f"工程类型: {manage_mode}，地址: {repo_url}")

        for timestamp_file in os.listdir(Cluster.project_root_path):
            timestamp_path = os.path.join(Cluster.project_root_path, timestamp_file)
            if os.path.isfile(timestamp_path):
                continue
            LOG.info("")
            LOG.info(f"当前目录：{timestamp_path}")
            record_txt = os.path.join(timestamp_path, "project_record.txt")
            if os.path.exists(record_txt):
                LOG.info("发现工程下载记录文件")
                with open(record_txt, encoding="utf-8") as record_file:
                    record = record_file.readline().strip()
                LOG.info(f"记录文件的内容：'{record}'")
                if record == record_url:
                    # 本地URL和下发的一致
                    LOG.info("记录文件内容与现仓库地址相符，查找到工程在本地的拷贝的路径")
                    local_path = timestamp_path
                    break
                else:
                    LOG.info("记录文件内容与现仓库地址不相符")
            else:
                LOG.info("缺失下载记录文件")
                if manage_mode in ["http", "git"]:
                    continue
                LOG.info("检查是否为svn工程的拷贝")
                url = self.__get_svn_info(timestamp_path)
                if url is None:
                    LOG.info("不是svn工程的拷贝")
                    continue
                LOG.info(f"是svn工程的拷贝，对应的svn仓库地址：{url}")
                self.__make_project_record(timestamp_path, url)
                if url == record_url:
                    LOG.info("检查结果与现仓库地址相符，查找到工程在本地的拷贝的路径")
                    local_path = timestamp_path
                    break
        # 未找到下载记录，新建目录
        if local_path == "":
            section = repo_url.split("/")[-1].replace(" ", "")
            ret = re.search(r'(.*)\.(?:git|tar\.gz|tgz|zip)$', section)
            if ret:
                section = ret.group(1)
            timestamp = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time()))
            local_path = os.path.join(Cluster.project_root_path, f"{timestamp}_{section}")
            if manage_mode in ["http", "svn"]:
                os.makedirs(local_path, exist_ok=True)
                self.__make_project_record(local_path, record_url)
            time.sleep(1)
        return local_path

    @staticmethod
    def __make_project_record(project_path, record_url):
        record_txt = os.path.join(project_path, "project_record.txt")
        if os.path.exists(record_txt):
            LOG.info(f"修改下载记录：{record_txt}")
        else:
            LOG.info(f"新建下载记录：{record_txt}")
        txt_fd = os.open(record_txt, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, FilePermission.mode_644)
        with os.fdopen(txt_fd, "w", encoding="utf-8") as record_file:
            record_file.write(record_url)

    @staticmethod
    def __clean_project(project_path):
        LOG.info(f"clean project files, path: {project_path}")
        if os.name == "nt":
            # 清理目录时，.svn文件夹可能会被TSVNCache.exe进程占用
            Utils.execute_command("taskkill /f /t /im TSVNCache.exe")
        for file in os.listdir(project_path):
            if file in ["project_record.txt", ".lock_file"]:
                continue
            temp_path = os.path.join(project_path, file)
            Utils.delete_file(temp_path)

    @staticmethod
    def __get_svn_info(path):
        repository = None
        Utils.execute_command(f"svn cleanup {path}")
        output = Utils.execute_command("svn info", cwd=path).strip("\n")
        if output.find("Revision") != -1:
            for line in output.split("\n"):
                if line.startswith("URL"):
                    # 处理含中文字符的svn地址
                    repository = unquote(line.split(" ")[1], encoding="utf-8")
                    break
        if repository is None:
            LOG.info(f"execute svn info's output: {output}")
        return repository

    def find_testcase_json(self):
        """查找用例json"""
        case_names = self.case_names
        in_path = os.path.join(self.project_path, "testcases")
        results = {case_name: "" for case_name in case_names}
        set_case_names = set(case_names)
        for top, _, filenames in os.walk(in_path):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue
                case_name = filename[:-5]
                case_path = os.path.join(top, filename)
                # 任务为指定用例编号
                if not case_names:
                    results.update({case_name: case_path})
                    continue
                # 任务指定了用例编号
                if case_name in set_case_names:
                    results.update({case_name: case_path})
                    set_case_names.remove(case_name)
            # 任务指定了用例编号，并找到了所有用例json的路径，退出循环
            if case_names and not set_case_names:
                break
        return results
