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
import os
import time
from typing import Dict, List, Sequence, Tuple, Union

from fastapi.encoders import jsonable_encoder
from sqlmodel import Session

from _core.constants import AdvanceDeviceOption, Cluster, State
from _core.context.option_util import get_device_options
from _core.environment.device_state import DeviceAllocationState, DeviceState
from _core.error import ErrorMessage
from _core.executor.request import TestSource
from _core.report.__main__ import renew_report
from _core.report.reporter_helper import ReportConstant
from _core.testkit.json_parser import JsonParser
from xdevice import platform_logger
from . import crud
from .db import engine
from ..models import TaskInfo, TestBlock, TestDevice
from ..runner import Runner
from ..utils import Utils, create_empty_result, do_request

LOG = platform_logger("Controller")


def generate_task_report(task_id: str, start_time: str):
    LOG.info(f"generate task {task_id} report")
    report_path = os.path.join(Cluster.report_root_path, task_id)
    worker_logs = os.path.join(report_path, Cluster.worker_logs)
    if os.path.exists(worker_logs):
        for filename in os.listdir(worker_logs):
            if not filename.endswith(".zip"):
                continue
            # 解压worker回传的测试报告
            zip_file = os.path.join(worker_logs, filename)
            Utils.extract_zip(zip_file, report_path)
    try:
        renew_report(report_path, start_time)
    except Exception as e:
        LOG.error(e)
    report_url = os.path.join(report_path, ReportConstant.summary_vision_report)
    return report_url


def mark_block_end(block_id: str):
    LOG.info(f"block {block_id} is end")
    with Session(engine) as session:
        block = crud.DBBlock.get_block_by_id(session, block_id)
        if not block:
            return
        crud.DBBlock.set_block_end(session, block)
        # 设备占用状态更改为“空闲”
        devices_json = json.loads(block.info).get("devices")
        update_devices_usage_state(session, devices_json, DeviceAllocationState.available)
        # 检查该任务的所有任务块的执行状态
        task_id = block.task_id
        if not _is_task_blocks_finished(session, task_id):
            return
    mark_task_end(task_id)


def _is_task_blocks_finished(session: Session, task_id: str):
    """检查该任务的所有任务块是否均已完成"""
    blocks = crud.DBBlock.get_blocks_by_task_id(session, task_id)
    for block in blocks:
        if block.state not in [State.Completed, State.Stopped]:
            return False
    return True


def mark_task_end(task_id: str, error_message: str = "", state: str = State.Completed):
    LOG.info(f"task {task_id} is end")
    with Session(engine) as session:
        task = crud.DBTask.get_task_by_id(session, task_id)
        if not task:
            return
        # 生成任务的测试报告
        start_time = task.begin_time.strftime(ReportConstant.time_format)
        report_url = generate_task_report(task_id, start_time)
        crud.DBTask.set_task_end(session, task, error_message, report_url, state)


def stop_task_blocks(task_id: str):
    with Session(engine) as session:
        blocks = crud.DBBlock.get_blocks_by_task_id(session, task_id)
        for block in blocks:
            if block.state == State.Completed:
                continue
            new_state = State.Stopped
            if block.state == State.Running:
                code, rsp_msg = stop_worker_task(block.task_id, str(block.id), block.worker_url)
                if code == 200 and rsp_msg.get("status") == "ok":
                    new_state = State.Stopping
                devices_json = json.loads(block.info).get("devices")
                update_devices_usage_state(session, devices_json, DeviceAllocationState.available)
            crud.DBBlock.set_block_end(session, block, new_state)


def send_worker_task(task_info: dict, worker_url: str):
    url = worker_url + "/worker/v1/task/send"
    LOG.info(f"send worker task with body: {task_info}")
    code, rsp_msg = do_request(url, body=task_info)
    LOG.info(f"send worker task response code: {code}")
    LOG.info(f"send worker task response body: {rsp_msg}")
    return code, json.loads(rsp_msg)


def stop_worker_task(task_id: str, block_id: str, worker_url: str):
    url = worker_url + "/worker/v1/task/stop"
    body = {"task_id": task_id, "block_id": block_id}
    LOG.info(f"stop worker task with body: {body}")
    code, rsp_msg = do_request(url, body=body)
    LOG.info(f"stop worker task response code: {code}")
    LOG.info(f"stop worker task response body: {rsp_msg}")
    return code, json.loads(rsp_msg)


def update_devices_state(session: Session, devices: List[Dict[str, Union[int, str]]], state: str):
    for device in devices:
        device_id = device.get("id")
        if not device_id:
            continue
        crud.DBDevice.set_device_state(session, device_id, state)


def update_devices_usage_state(session: Session, devices: List[Dict[str, Union[int, str]]], state: str):
    for device in devices:
        device_id = device.get("id")
        if not device_id:
            continue
        crud.DBDevice.set_device_usage_state(session, device_id, state)


class BlockHandler:

    def __init__(self):
        self._cur_blk = None
        self._cur_blk_info = None
        self._cur_blk_cases = []
        self._cur_blk_environment = []
        self._cur_blk_id = ""
        self._cur_blk_report_path = ""

    def mark_cases_error(self, error_message: str):
        for case_name in self._cur_blk_cases:
            create_empty_result(self._cur_blk_report_path, case_name, error_message)

    def run(self):
        while True:
            time.sleep(30)
            try:
                waiting_blocks = crud.DBBlock.get_waiting_blocks()
                if not waiting_blocks:
                    continue
                self._traverse_waiting_blocks(waiting_blocks)
            except Exception as e:
                LOG.error(e)

    def _traverse_waiting_blocks(self, blocks: Sequence[TestBlock]):
        """遍历排队任务块"""
        for block in blocks:
            self._cur_blk = block
            self._cur_blk_info = json.loads(block.info)
            self._cur_blk_cases = self._cur_blk_info.get("cases")
            self._cur_blk_environment = json.loads(block.environment)
            self._cur_blk_id = str(block.id)
            self._cur_blk_report_path = os.path.join(Cluster.report_root_path, block.task_id)
            expect_cnt = len(self._cur_blk_environment)
            ip_device_cnt = crud.DBDevice.get_ip_number_of_online_devices(expect_cnt)
            if not ip_device_cnt:
                error = ErrorMessage.Cluster.Code_0104019.format(expect_cnt)
                self.mark_cases_error(error)
                mark_block_end(self._cur_blk_id)
                continue
            self._traverse_ip_devices(ip_device_cnt)

    def _traverse_ip_devices(self, ip_device_cnt: List[Tuple[str, int]]):
        exist_matched_devices = False
        for ip, _ in ip_device_cnt:
            same_ip_online_devices = crud.DBDevice.get_online_devices_by_ip(ip)
            if not same_ip_online_devices:
                continue
            # 预占用设备列表
            pre_occupied_devices = []
            for env in self._cur_blk_environment:
                # 临时预占用设备
                tmp_occupied_devices = None
                for device in same_ip_online_devices:
                    if device in pre_occupied_devices \
                            or not self._is_device_matched(device, env):
                        continue
                    if device.usage_state == DeviceAllocationState.available:
                        pre_occupied_devices.append(device)
                        break
                    tmp_occupied_devices = device
                if tmp_occupied_devices is not None:
                    pre_occupied_devices.append(tmp_occupied_devices)

            required_devices_cnt = len(self._cur_blk_environment)
            if len(pre_occupied_devices) < required_devices_cnt:
                # 匹配下一个ip环境上的设备
                break
            # 到这里，用例已成功配置需求设备，挑选空闲的设备下发测试用例
            exist_matched_devices = True
            devices = []
            for pre_occupied_device in pre_occupied_devices:
                if pre_occupied_device.usage_state != DeviceAllocationState.available:
                    continue
                devices.append(pre_occupied_device)
                if len(devices) == required_devices_cnt:
                    break
            if len(devices) == required_devices_cnt:
                # 存在足量的空闲设备，向worker下发任务块
                devices_json = jsonable_encoder(devices)
                with Session(engine) as session:
                    task_info_json = self._cur_blk_info
                    task_info_json.update({
                        "block_id": self._cur_blk_id,
                        "devices": devices_json
                    })
                    worker_url = devices[0].worker_url
                    # 设备占用状态改为“占用”
                    update_devices_usage_state(session, devices_json, DeviceAllocationState.allocated)
                    code, rsp_msg = send_worker_task(task_info_json, worker_url)
                    if code == 200 and rsp_msg.get("status") == "ok":
                        # 刷新任务块信息
                        self._cur_blk.info = json.dumps(task_info_json)
                        self._cur_blk.worker_url = worker_url
                        # 标记任务块开始执行
                        crud.DBBlock.set_block_begin(session, self._cur_blk)
                    else:
                        # 任务下发失败，设备状态改为“离线”
                        update_devices_state(session, devices_json, DeviceState.OFFLINE.value)
                        # 设备占用状态改为“空闲”
                        update_devices_usage_state(session, devices_json, DeviceAllocationState.available)
                break
            # 预占用设备列表里的设备，均不处于空闲可用状态，匹配下一个ip环境上的设备，或排队等待设备
            LOG.info(f"test block {self._cur_blk_id} waiting for devices available")

        if not exist_matched_devices:
            self.mark_cases_error(ErrorMessage.Cluster.Code_0104020)
            mark_block_end(self._cur_blk_id)

    @staticmethod
    def _is_device_matched(device: TestDevice, required_props: Dict[str, str]):
        """用例json里配置的type和label，与输入的设备信息做匹配"""
        expect_device_os = required_props.get("type")
        expect_device_label = required_props.get("label")
        if expect_device_os != device.os \
                or expect_device_label and expect_device_label != device.type:
            return False
        return True


class TaskHandler(Runner):

    def __init__(self, task_info: TaskInfo):
        super().__init__(task_info)

        self.report_path = os.path.join(Cluster.report_root_path, self.task_id)
        self._env_and_cases = []

    def run(self):
        os.makedirs(self.report_path, exist_ok=True)
        try:
            self.prepare_project()
            found_cases = self._classify_testcase_by_environment()
            if not found_cases:
                mark_task_end(self.task_id)
                return
            self.case_names = found_cases
            self._split_test_block()
        except Exception as e:
            error_message = str(e)
            LOG.error(error_message)
            self.mark_cases_error(self.case_names, error_message)
            mark_task_end(self.task_id, error_message=error_message)

    def _classify_testcase_by_environment(self):
        """按环境约束归类测试用例"""
        found_cases = []
        for case_name, json_file in self.find_testcase_json().items():
            if not json_file:
                if self.case_names:
                    self.mark_cases_error([case_name], ErrorMessage.Common.Code_0101014.format(case_name))
                continue

            try:
                json_parser = JsonParser(json_file)
            except Exception as e:
                self.mark_cases_error([case_name], str(e))
                continue
            driver_type = json_parser.get_driver_type()
            if not driver_type:
                self.mark_cases_error([case_name], ErrorMessage.Common.Code_0101017.format(case_name))
                continue

            environment = []
            test_source = TestSource(json_file, "", json_file, case_name, driver_type, case_name, "")
            device_options = get_device_options({"device_sn": ""}, test_source)
            for device_option in device_options:
                extend_value = device_option.extend_value
                required_manager = device_option.required_manager
                label = device_option.label
                if AdvanceDeviceOption.type not in extend_value:
                    extend_value.update({AdvanceDeviceOption.type: required_manager})
                if label and AdvanceDeviceOption.label not in extend_value:
                    extend_value.update({AdvanceDeviceOption.label: label})
                for k in list(extend_value.keys()):
                    if k not in [AdvanceDeviceOption.type, AdvanceDeviceOption.label]:
                        extend_value.pop(k)
                environment.append(extend_value)
            if not environment:
                self.mark_cases_error([case_name], ErrorMessage.Cluster.Code_0104021)
                continue
            found_cases.append(case_name)
            self._add_env_and_case(environment, case_name)
        return found_cases

    def _add_env_and_case(self, environment: List[Dict[str, str]], case_name: str):
        matched_item = None
        for item in self._env_and_cases:
            cur_environment = item.get("environment")
            if not self._is_env_matched(cur_environment, environment):
                continue
            matched_item = item
        if matched_item:
            matched_item.get("cases").append(case_name)
            return
        self._env_and_cases.append({"environment": environment, "cases": [case_name]})

    @staticmethod
    def _is_env_matched(env1: List[Dict[str, str]], env2: List[Dict[str, str]]):
        if len(env1) != len(env2):
            return False
        for env in zip(env1, env2):
            if env[0].get(AdvanceDeviceOption.type) != env[1].get(AdvanceDeviceOption.type) \
                    or env[0].get(AdvanceDeviceOption.label) != env[1].get(AdvanceDeviceOption.label):
                return False
        return True

    def _split_test_block(self):
        """按块大小10对用例分块"""
        for item in self._env_and_cases:
            environment, cases = item.get("environment"), item.get("cases")
            if len(cases) <= 10:
                self._create_test_block(environment, cases)
                continue
            for case_names in self._group_list(cases):
                self._create_test_block(environment, case_names)

    def _create_test_block(self, environment: List[Dict[str, str]], case_names: List[str]):
        """创建分块记录"""
        info = TaskInfo(
            project=self.task_info.project,
            cases=case_names,
            task_id=self.task_id
        )
        block = TestBlock(
            info=json.dumps(jsonable_encoder(info)),
            task_id=self.task_id,
            environment=json.dumps(environment)
        )
        crud.DBBlock.create_block(block)
        LOG.info(f"{self.task_id} create test block. id: {block.id}, environment: {environment}")

    @staticmethod
    def _group_list(cases: List[str], size: int = 10):
        """
        cases: 待分组的用例列表
        size: 分组大小
        """
        cases_len = len(cases)
        for i in range(0, cases_len, size):
            yield cases[i:] if i + size > cases_len else cases[i:i + size]
