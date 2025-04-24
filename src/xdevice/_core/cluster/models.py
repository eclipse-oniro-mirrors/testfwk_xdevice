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

import uuid
from datetime import datetime
from typing import Dict, List, Union

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from _core.constants import State
from _core.environment.device_state import DeviceAllocationState


class Device(SQLModel):
    id: Union[int, None] = Field(default=None, primary_key=True)
    ip: str = Field(index=True)
    sn: str = Field(index=True)
    os: str
    type: str
    model: str
    version: str
    worker_url: str = Field(description="worker地址")
    state: str = Field(index=True, description="设备状态")


class TestDevice(Device, table=True):
    usage_state: str = Field(default=DeviceAllocationState.available, description="占用状态")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间",
                                  sa_column_kwargs={"onupdate": datetime.now})


class Project(BaseModel):
    url: str = Field(description="工程地址")
    mode: str = Field(description="工程模式（git/svn/http/local）")
    branch: str = Field(default="", description="分支名称")
    username: str = Field(default="", description="用户名")
    password: str = Field(default="", description="密码")
    relative_path: str = Field(default="", description="相对路径")


class TaskStopParam(BaseModel):
    task_id: str
    block_id: str


class TaskTemplate(BaseModel):
    project: Project
    cases: List[str] = []
    devices: List[Dict[str, Union[int, str]]] = []


class TaskInfo(TaskTemplate):
    task_id: str
    block_id: str = ""


class Task(SQLModel):
    id: str = Field(primary_key=True, description="任务编号")
    state: str = Field(default=State.Waiting, index=True, description="运行状态")
    begin_time: Union[datetime, None] = Field(default=None, description="开始时间")
    end_time: Union[datetime, None] = Field(default=None, description="结束时间")
    error_message: str = Field(default="", description="报错信息")
    report_url: str = Field(default="", description="报告地址")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")


class TestTask(Task, table=True):
    info: str = Field(description="任务模板信息")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间",
                                  sa_column_kwargs={"onupdate": datetime.now})


class TestBlock(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, description="任务块编号")
    task_id: str = Field(index=True, description="任务编号")
    info: str = Field(description="任务块信息")
    environment: str = Field(default="", description="环境描述")
    state: str = Field(default=State.Waiting, index=True, description="运行状态")
    begin_time: Union[datetime, None] = Field(default=None, description="开始时间")
    end_time: Union[datetime, None] = Field(default=None, description="结束时间")
    worker_url: str = Field(default="", description="worker地址")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")
    update_time: datetime = Field(default_factory=datetime.now, description="更新时间",
                                  sa_column_kwargs={"onupdate": datetime.now})


class ResponseMsg(BaseModel):
    status: str = "ok"
    message: str = ""
