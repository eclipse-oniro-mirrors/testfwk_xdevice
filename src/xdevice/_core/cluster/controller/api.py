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

import os
from typing import List, Union

from fastapi import APIRouter, File, Form, UploadFile

from _core.constants import Cluster, FilePermission, State
from _core.environment.device_state import DeviceAllocationState
from . import crud
from .db import SessionDep
from .handler import mark_block_end, mark_task_end, stop_task_blocks
from ..models import Device, Task, TestDevice, TaskTemplate, ResponseMsg


class RespCreateTask(ResponseMsg):
    task_id: str


class RespListTask(ResponseMsg):
    result: List[Task] = []


class RespListDevices(ResponseMsg):
    result: List[TestDevice] = []


router = APIRouter(prefix="/controller/v1", tags=["controller"])


@router.post("/device/add", response_model=ResponseMsg)
def add_devices(session: SessionDep, devices: List[Device]):
    crud.DBDevice.create_device(session, devices)
    return ResponseMsg(message="devices added")


@router.post("/device/{device_id}/free", response_model=ResponseMsg)
def free_device(session: SessionDep, device_id: int):
    device = crud.DBDevice.get_device_by_id(session, device_id)
    if not device:
        return ResponseMsg(status="failed", message="device not found")
    if device.usage_state == DeviceAllocationState.available:
        return ResponseMsg(message="device is available, no need to free")
    device.usage_state = DeviceAllocationState.available
    session.add(device)
    session.commit()
    return ResponseMsg()


@router.get("/device/list-all", response_model=RespListDevices)
def list_devices(session: SessionDep):
    devices = crud.DBDevice.get_all_devices(session)
    resp = RespListDevices(result=devices)
    if not devices:
        resp.status = "failed"
        resp.message = "No data"
    return resp


@router.post("/task/create", status_code=201, response_model=RespCreateTask)
def create_task(session: SessionDep, template: TaskTemplate):
    task = crud.DBTask.create_task(session, template)
    return RespCreateTask(message="task created", task_id=task.id)


@router.post("/task/{task_id}/stop", response_model=ResponseMsg)
def stop_task(session: SessionDep, task_id: str):
    task = crud.DBTask.get_task_by_id(session, task_id)
    if not task:
        return ResponseMsg(status="failed", message="task not found")
    task_state = task.state
    if task_state == State.Waiting:
        mark_task_end(task_id, State.Stopped)
        return ResponseMsg(message="task stopped")
    if task_state == State.Running:
        task.state = State.Stopping
        session.add(task)
        session.commit()
        stop_task_blocks(task_id)
        return ResponseMsg(message="stop the task immediately")
    if task_state == State.Stopped:
        return ResponseMsg(status="failed", message="task stopped")
    if task_state == State.Stopping:
        return ResponseMsg(status="failed", message="the task is being stopped")
    if task_state == State.Completed:
        return ResponseMsg(status="failed", message="task completed")
    return ResponseMsg()


@router.get("/task/{task_id}/list", response_model=RespListTask)
def list_task(session: SessionDep, task_id: str):
    task = crud.DBTask.get_task_by_id(session, task_id)
    resp = RespListTask()
    if task:
        resp.result = [task]
    else:
        resp.status = "failed"
        resp.message = "task not found"
    return resp


@router.get("/task/list-all", response_model=RespListTask)
def list_tasks(session: SessionDep):
    tasks = crud.DBTask.get_all_tasks(session)
    resp = RespListTask(result=tasks)
    if not tasks:
        resp.status = "failed"
        resp.message = "No data"
    return resp


@router.post("/task/upload-end", response_model=ResponseMsg)
async def upload_task_end(task_id: str = Form(...), block_id: str = Form(...),
                          file: Union[UploadFile, None] = File(default=None)):
    resp = ResponseMsg()
    if file is not None:
        resp.message = "report file is uploaded"
        save_path = os.path.join(Cluster.report_root_path, task_id, Cluster.worker_logs)
        os.makedirs(save_path, exist_ok=True)
        save_file = os.path.join(save_path, file.filename)
        if os.path.exists(save_file):
            os.remove(save_file)
        try:
            save_file_fd = os.open(save_file, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
            with os.fdopen(save_file_fd, "wb+") as s_file:
                while True:
                    data = await file.read(4096)
                    if not data:
                        break
                    s_file.write(data)
                s_file.flush()
        except Exception as e:
            resp.status = "failed"
            resp.message = str(e)
    # 标记任务块完成
    mark_block_end(block_id)
    return resp
