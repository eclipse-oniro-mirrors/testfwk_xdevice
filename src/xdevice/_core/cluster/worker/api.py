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

from fastapi import APIRouter

from xdevice import platform_logger
from .task_manager import task_manager, TaskQueueMeta
from ..models import ResponseMsg, TaskInfo, TaskStopParam
from ..utils import Utils

LOG = platform_logger("Worker")
router = APIRouter(prefix="/worker/v1", tags=["worker"])


@router.post("/task/send", response_model=ResponseMsg)
def send_task(info: TaskInfo):
    resp = ResponseMsg()
    try:
        group_id = Utils.hash_message(info.task_id + info.block_id)
        LOG.info(f"receive task as: {group_id}")
        info_json = info.model_dump()
        LOG.debug(f"receive message: {info_json}")
        if task_manager.get_task(group_id) is None:
            msg = TaskQueueMeta(group_id, "create", info_json)
            task_manager.put_pending_msg(msg)
        else:
            LOG.info(f"{group_id} already in task manager")
    except Exception as e:
        resp.status = "failed"
        resp.message = str(e)
    return resp


@router.post("/task/stop", response_model=ResponseMsg)
def stop_task(param: TaskStopParam):
    group_id = Utils.hash_message(param.task_id + param.block_id)
    if task_manager.get_task(group_id) is None:
        return ResponseMsg(status="failed", message="task is not running")
    try:
        msg = TaskQueueMeta(group_id, "stop", param.model_dump())
        task_manager.put_pending_msg(msg)
    except Exception as e:
        return ResponseMsg(status="failed", message=str(e))
    return ResponseMsg()
