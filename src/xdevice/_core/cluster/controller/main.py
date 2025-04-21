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

import json
import threading
import time

from sqlmodel import Session

from xdevice import platform_logger
from . import crud
from .db import engine
from .handler import BlockHandler, TaskHandler
from ..models import TaskInfo
from ..runner import thread_pool

LOG = platform_logger("Controller")


def loop_task():
    while True:
        time.sleep(5)
        try:
            with Session(engine) as session:
                task = crud.DBTask.get_one_waiting_task(session)
                if not task:
                    continue
                task_info_json = json.loads(task.info)
                task_info_json.update({
                    "task_id": task.id
                })
                task_handler = TaskHandler(TaskInfo(**task_info_json))
                thread_pool.submit(task_handler.run)
                crud.DBTask.set_task_begin(session, task)
        except Exception as e:
            LOG.error(e)


def start_controller():
    th1 = threading.Thread(target=loop_task)
    th1.daemon = True
    th1.name = "LoopTestTask"
    th1.start()

    th2 = threading.Thread(target=BlockHandler().run)
    th2.daemon = True
    th2.name = "LoopTestBlock"
    th2.start()
