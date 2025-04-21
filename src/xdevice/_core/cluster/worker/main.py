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

import threading

from .task_manager import task_manager


def start_worker():
    th1 = threading.Thread(target=task_manager.run)
    th1.daemon = True
    th1.name = "LoopTest"
    th1.start()

    th2 = threading.Thread(target=task_manager.loop_task_queue)
    th2.daemon = True
    th2.name = "LoopTaskQueue"
    th2.start()
