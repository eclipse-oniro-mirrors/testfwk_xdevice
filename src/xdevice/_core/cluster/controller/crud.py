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
import json
import uuid
from typing import List, Sequence, Tuple

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlmodel import Session, select

from _core.constants import State
from _core.environment.device_state import DeviceState
from _core.utils import get_cst_time
from .db import engine
from ..models import TestTask, TestBlock, TestDevice, Device, TaskTemplate


class DBDevice:

    @staticmethod
    def create_device(session: Session, devices: List[Device]):
        for device in devices:
            ip, sn = device.ip, device.sn
            if not ip or not sn:
                continue
            statement = select(TestDevice).where(TestDevice.ip == ip).where(TestDevice.sn == sn)
            db_device = session.exec(statement).first()
            if db_device:
                db_device.os = device.os
                db_device.type = device.type
                db_device.model = device.model
                db_device.version = device.version
                db_device.worker_url = device.worker_url
                db_device.state = device.state
            else:
                db_device = TestDevice.model_validate(device)
            session.add(db_device)
            session.commit()

    @staticmethod
    def get_ip_number_of_online_devices(expect_cnt: int) -> List[Tuple[str, int]]:
        """按ip统计环境上在线的设备数量
        @return [('ip1', 1), ('ip2', 2), ...]
        """
        statement = select(
            TestDevice.ip,
            func.count(TestDevice.sn)
        ).where(TestDevice.state == DeviceState.ONLINE.value).group_by(TestDevice.ip)
        results = []
        with Session(engine) as session:
            for result in session.exec(statement).all():
                if result[1] >= expect_cnt:
                    results.append(result)
        return results

    @staticmethod
    def get_device_by_id(session: Session, device_id: int):
        return session.get(TestDevice, device_id)

    @staticmethod
    def get_online_devices_by_ip(ip: str) -> Sequence[TestDevice]:
        statement = select(TestDevice) \
            .where(TestDevice.ip == ip) \
            .where(TestDevice.state == DeviceState.ONLINE.value)
        with Session(engine) as session:
            return session.exec(statement).all()

    @staticmethod
    def get_all_devices(session: Session):
        return session.exec(select(TestDevice)).all()

    @staticmethod
    def set_device_state(session: Session, device_id: int, state: str) -> bool:
        device = DBDevice.get_device_by_id(session, device_id)
        if not device or device.state == state:
            return False
        device.state = state
        session.add(device)
        session.commit()
        return True

    @staticmethod
    def set_device_usage_state(session: Session, device_id: int, state: str) -> bool:
        device = DBDevice.get_device_by_id(session, device_id)
        if not device or device.usage_state == state:
            return False
        device.usage_state = state
        session.add(device)
        session.commit()
        return True


class DBBlock:

    @staticmethod
    def create_block(block: TestBlock):
        with Session(engine) as session:
            session.add(block)
            session.commit()
            session.refresh(block)

    @staticmethod
    def get_block_by_id(session: Session, block_id: str):
        return session.get(TestBlock, uuid.UUID(block_id))

    @staticmethod
    def get_blocks_by_task_id(session: Session, task_id: str) -> Sequence[TestBlock]:
        statement = select(TestBlock).where(TestBlock.task_id == task_id)
        return session.exec(statement).all()

    @staticmethod
    def get_waiting_blocks() -> Sequence[TestBlock]:
        statement = select(TestBlock).where(TestBlock.state == State.Waiting).order_by(TestBlock.update_time)
        with Session(engine) as session:
            return session.exec(statement).all()

    @staticmethod
    def set_block_begin(session: Session, block: TestBlock):
        block.begin_time = get_cst_time()
        block.state = State.Running
        session.add(block)
        session.commit()

    @staticmethod
    def set_block_end(session: Session, block: TestBlock, state: str = State.Completed):
        cur_time = get_cst_time()
        if not block.begin_time:
            block.begin_time = cur_time
        block.end_time = cur_time
        if state == State.Stopping:
            block.state = state
        else:
            block.state = State.Stopped if block.state == State.Stopping else State.Completed
        session.add(block)
        session.commit()


class DBTask:

    @staticmethod
    def create_task(session: Session, template: TaskTemplate):
        template.cases = list(set(template.cases))
        template.project.password = base64.b64encode(template.project.password.encode()).decode()
        task = TestTask(
            id=get_cst_time().strftime("%Y-%m-%d-%H-%M-%S-%f"),
            info=json.dumps(jsonable_encoder(template))
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    @staticmethod
    def get_all_tasks(session: Session):
        return session.exec(select(TestTask)).all()

    @staticmethod
    def get_task_by_id(session: Session, task_id: str):
        return session.get(TestTask, task_id)

    @staticmethod
    def get_one_waiting_task(session: Session) -> TestTask:
        statement = select(TestTask).where(TestTask.state == State.Waiting)
        return session.exec(statement).first()

    @staticmethod
    def set_task_begin(session: Session, task: TestTask):
        task.begin_time = get_cst_time()
        task.state = State.Running
        session.add(task)
        session.commit()

    @staticmethod
    def set_task_end(session: Session, task: TestTask, error_message: str = "",
                     report_url: str = "", state: str = State.Completed):
        cur_time = get_cst_time()
        if not task.begin_time:
            task.begin_time = cur_time
        task.end_time = cur_time
        if error_message:
            task.error_message = error_message
        if report_url:
            task.report_url = report_url
        task.state = State.Stopped if task.state == State.Stopping else state
        session.add(task)
        session.commit()
