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
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from _core.constants import Cluster, ConfigConst
from _core.error import ErrorMessage
from xdevice import Variables
from xdevice import platform_logger
from .controller.api import router as controller_router
from .controller.db import create_db_and_tables
from .controller.main import start_controller
from .worker.api import router as worker_router
from .worker.main import start_worker

LOG = platform_logger("Cluster")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # do things before app start
    create_db_and_tables()
    yield
    # do things before app exit


def cluster_main():
    # 创建路径
    os.makedirs(Cluster.project_root_path, exist_ok=True)
    os.makedirs(Cluster.report_root_path, exist_ok=True)
    # 获取配置
    cluster = Variables.config.cluster
    control_service_url = cluster.get(ConfigConst.control_service_url)
    if not control_service_url:
        raise Exception(ErrorMessage.Cluster.Code_0104001)
    service_mode = cluster.get(ConfigConst.service_mode)
    service_port = int(cluster.get(ConfigConst.service_port))
    # 启动服务
    if service_mode == Cluster.worker:
        LOG.info("cluster service mode is worker")
        app = FastAPI()
        app.include_router(worker_router)
        start_worker()
    else:
        LOG.info("cluster service mode is controller")
        app = FastAPI(lifespan=lifespan)
        app.include_router(controller_router)
        start_controller()

    th = threading.Thread(
        target=uvicorn.run,
        args=(app,),
        kwargs={"host": "0.0.0.0", "port": service_port}
    )
    th.daemon = True
    th.start()
