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

import multiprocessing
import os
import queue
import time
from typing import Dict

from _core.constants import Cluster
from xdevice import platform_logger
from .task_runner import WorkerRunner
from ..runner import thread_pool
from ..utils import Utils, upload_task_end

LOG = platform_logger("Worker")


class TaskExecutionMeta:
    """正在运行的任务信息"""

    def __init__(self, group_id, process, task_info, description):
        self.group_id = group_id  # 任务标识
        self.process = process  # 任务进程
        self.task_info = task_info  # 任务信息
        self.description = description  # 任务描述


class TaskQueueMeta:

    def __init__(self, group_id: str, action: str, params: dict):
        self.group_id = group_id  # 任务标识
        self.action = action  # 请求动作，create/stop
        self.params = params  # 请求信息


class TaskManager:

    def __init__(self):
        self.executing_task: Dict[str, TaskExecutionMeta] = {}
        self.task_queue = queue.SimpleQueue()

    def __new__(cls, *args, **kwargs):
        if not hasattr(TaskManager, "_instance"):
            TaskManager._instance = object.__new__(cls)
        return TaskManager._instance

    def add_executing_task(self, group_id, meta):
        self.executing_task.update({group_id: meta})

    def del_executing_task(self, group_id):
        meta = self.get_task(group_id)
        if meta is None:
            LOG.info(f"{group_id} task meta is none")
            return
        self.executing_task.pop(group_id)
        LOG.info(f"{group_id} task meta was removed")

    def get_task(self, group_id):
        return self.executing_task.get(group_id)

    def get_task_process(self, group_id):
        meta = self.get_task(group_id)
        return None if meta is None else meta.process

    def put_pending_msg(self, msg):
        """添加任务下发/停止信息"""
        if not isinstance(msg, TaskQueueMeta):
            LOG.warning("pending msg must be an instance of TaskQueueMeta")
            return
        self.task_queue.put(msg)
        LOG.info("put pending msg")

    def loop_task_queue(self):
        """处理任务消息队列"""
        while True:
            try:
                msg = self.task_queue.get()
                if not isinstance(msg, TaskQueueMeta):
                    continue
                group_id = msg.group_id
                action = msg.action
                params = msg.params
                if action == "create":
                    self.handle_task_create(group_id, params)
                if action == "stop":
                    self.handle_task_stop(group_id)
            except Exception as e:
                LOG.error(e, exc_info=True)

    def handle_task_create(self, group_id, task_info):
        """创建任务进程"""
        LOG.info(f"{group_id} request to create a new task process")
        try:
            process = multiprocessing.Process(target=WorkerRunner(task_info).run)
            process.daemon = True
            process.start()
            time.sleep(1)
            LOG.info(f"{group_id} process id is {process.pid}")
            desc = f"taskID:{task_info.get('task_id')},blockID:{task_info.get('block_id')}"
            meta = TaskExecutionMeta(group_id, process, task_info, desc)
            self.add_executing_task(group_id, meta)
        except Exception as e:
            LOG.error(e, exc_info=True)

    def handle_task_stop(self, group_id):
        """停止任务进程"""
        LOG.info(f"{group_id} request to stop task process")
        process = self.get_task_process(group_id)
        if process is None:
            return
        proc_id = process.pid
        LOG.info(f"{group_id} process id is {proc_id}, kill it")
        try:
            Utils.kill_process_and_child(proc_id)
        except Exception as e:
            LOG.error(e, exc_info=True)
        finally:
            Utils.kill_process_by_pobj(process)
        LOG.info(f"{group_id} process has been killed")
        self.handle_task_end(group_id)

    def handle_task_end(self, group_id):
        """清理任务进程"""
        LOG.info(f"{group_id} task end")
        meta = self.get_task(group_id)
        task_info = meta.task_info
        task_id = task_info.get("task_id")
        block_id = task_info.get("block_id")
        report_path = os.path.join(Cluster.report_root_path, task_id, block_id)
        # 上传测试报告
        thread_pool.submit(upload_task_end, task_id, block_id, report_path)
        self.del_executing_task(group_id)

    def run(self):
        """定期扫描执行任务的状态"""
        while True:
            time.sleep(5)
            try:
                if not self.executing_task:
                    continue
                for group_id in list(self.executing_task.keys()):
                    meta = self.get_task(group_id)
                    process = meta.process
                    if process is None:
                        continue
                    if process.is_alive():
                        LOG.info(f"{group_id} process is running. {meta.description}")
                    else:
                        LOG.info(f"{group_id} process end. pid: {process.pid}")
                        self.handle_task_end(group_id)
            except Exception as e:
                LOG.error(e)


task_manager = TaskManager()
