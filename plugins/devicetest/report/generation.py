#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2022 Huawei Device Co., Ltd.
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
import logging
import os
from jinja2 import Environment, FileSystemLoader

from devicetest.utils.file_util import create_dir
from xdevice import FilePermission, platform_logger
from xdevice import Variables

log = platform_logger(name="ReporterHelper")
# 常用的logger
log_names = ["AppTest", "DeviceTest", "Device", "Hdc", "Utils", "TestRunner", "WindowsTest"]


class BufferHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.buffer = []
        self.thread = None

    def emit(self, record):
        if record.thread != self.thread:
            return
        msg = self.format(record)
        if record.levelno == logging.ERROR:
            msg = "<div class=\"error\">{}</div>".format(msg)
        if record.levelno == logging.WARNING:
            msg = "<div class=\"warning\">{}</div>".format(msg)
        self.buffer.append(msg)


def add_log_caching_handler(buffer_hdl=None):
    """添加日志缓存handler"""
    if buffer_hdl is None:
        buffer_hdl = BufferHandler()
        buffer_hdl.thread = threading.currentThread().ident
        buffer_hdl.setFormatter(logging.Formatter(Variables.report_vars.log_format))
    for name in log_names:
        logger = platform_logger(name)
        logger.platform_log.handlers.append(buffer_hdl)
    return buffer_hdl


def del_log_caching_handler(buffer_hdl):
    """移除日志缓存handler"""
    if buffer_hdl is None:
        return
    for name in log_names:
        logger = platform_logger(name)
        handlers = logger.platform_log.handlers
        handlers.remove(buffer_hdl)


def get_caching_logs(buffer_hdl):
    """获取日志缓存记录"""
    return buffer_hdl.buffer if isinstance(buffer_hdl, BufferHandler) else []


def generate_report(to_file, template="case.html", **kwargs):
    """生成用例html报告
    Args:
        to_file : str, render to file
        template: str, render template
    Example:
        generate_report(to_file, case=case_info, logs=log_content)
    """
    try:
        create_dir(os.path.dirname(to_file))
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../res/template")
        env = Environment(
            loader=FileSystemLoader(template_path),
            lstrip_blocks=True,
            trim_blocks=True)
        template = env.get_template(template)

        html_fd = os.open(to_file, os.O_CREAT | os.O_WRONLY, FilePermission.mode_644)
        with os.fdopen(html_fd, mode="w", encoding="utf-8") as html_f:
            html_f.write(template.render(kwargs))
        log.info("report is generated in path: {}".format(to_file))
    except Exception as exception:
        log.error("report generating failed! {}".format(exception))
