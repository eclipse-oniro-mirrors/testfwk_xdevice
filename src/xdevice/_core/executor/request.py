#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2022 Huawei Device Co., Ltd.
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
import time

from _core.constants import ConfigConst
from _core.context.handler import report_not_executed
from _core.context.option_util import get_device_options
from _core.error import ErrorMessage
from _core.exception import ParamError
from _core.executor.source import TestSource
from _core.logger import platform_logger
from _core.plugin import Config
from _core.plugin import Plugin
from _core.plugin import get_plugin
from _core.testkit.json_parser import JsonParser
from _core.testkit.kit import get_kit_instances
from _core.utils import get_repeat_round

__all__ = ["Descriptor", "Task", "Request"]
LOG = platform_logger("Request")


class Descriptor:
    """
    The descriptor for a test or suite
    """

    def __init__(self, uuid=None, name=None, source=None, container=False, error=None):
        self.unique_id = uuid
        self.display_name = name
        self.tags = {}
        self.source = source
        self.parent = None
        self.children = []
        self.container = container
        self.error = error

    def get_container(self):
        return self.container

    def get_unique_id(self):
        return self.unique_id


class Task:
    """
    TestTask describes the tree of tests and suites
    """
    EMPTY_TASK = "empty"
    TASK_CONFIG_SUFFIX = ".json"
    TASK_CONFIG_DIR = "config"
    life_stage_listener = None

    def __init__(self, root=None, drivers=None, config=None):
        self.root = root
        self.test_drivers = drivers or []
        self.config = config or Config()

    def init(self, config):
        from xdevice import Variables
        from _core.context.log import RuntimeLogs
        import uuid
        start_time = time.localtime(time.time())
        LOG.debug("StartTime={}".format(time.strftime("%Y-%m-%d %H:%M:%S", start_time)))

        self.config.update(config.__dict__)
        Variables.task_id = uuid.uuid4().hex
        if getattr(config, ConfigConst.report_path, "") == "":
            Variables.task_name = time.strftime('%Y-%m-%d-%H-%M-%S', start_time)
        else:
            Variables.task_name = config.report_path

        # create a report folder to store test report
        report_path = os.path.join(Variables.exec_dir,
                                   Variables.report_vars.report_dir,
                                   Variables.task_name)
        os.makedirs(report_path, exist_ok=True)
        self._check_report_path(report_path)

        log_path = os.path.join(report_path, Variables.report_vars.log_dir)
        os.makedirs(log_path, exist_ok=True)

        self.config.kits = []
        if getattr(config, "task", ""):
            task_file = config.task + self.TASK_CONFIG_SUFFIX
            task_dir = self._get_task_dir(task_file)
            self._load_task(task_dir, task_file)

        self.config.top_dir = Variables.top_dir
        self.config.exec_dir = Variables.exec_dir
        self.config.report_path = report_path
        self.config.log_path = log_path
        self.config.start_time = time.strftime("%Y-%m-%d %H:%M:%S", start_time)
        RuntimeLogs.start_task_log(self.config.log_path)
        RuntimeLogs.start_encrypt_log(self.config.log_path)
        LOG.info("Report path: %s", report_path)

    def _get_task_dir(self, task_file):
        from xdevice import Variables
        exec_task_dir = os.path.abspath(
            os.path.join(Variables.exec_dir, self.TASK_CONFIG_DIR))
        if not os.path.exists(os.path.join(exec_task_dir, task_file)):
            err_msg = ErrorMessage.Common.Code_0101015.format(task_file)
            if os.path.normcase(Variables.exec_dir) == \
                    os.path.normcase(Variables.top_dir):
                raise ParamError(err_msg)

            top_task_dir = os.path.abspath(
                os.path.join(Variables.top_dir, self.TASK_CONFIG_DIR))
            if not os.path.exists(os.path.join(top_task_dir, task_file)):
                raise ParamError(err_msg)
            else:
                return top_task_dir
        else:
            return exec_task_dir

    def _load_task(self, task_dir, file_name):
        task_file = os.path.join(task_dir, file_name)
        if not os.path.exists(task_file):
            raise ParamError(ErrorMessage.Common.Code_0101015.format(task_file))

        # add kits to self.config
        json_config = JsonParser(task_file)
        kits = get_kit_instances(json_config, self.config.resource_path,
                                 self.config.testcases_path)
        self.config.kits.extend(kits)

    def set_root_descriptor(self, root):
        if not isinstance(root, Descriptor):
            raise TypeError("need 'Descriptor' type param")

        self.root = root
        self._init_driver(root)
        if not self.test_drivers:
            LOG.error(ErrorMessage.Common.Code_0101016)

    def _init_driver(self, test_descriptor):

        plugin_id = None
        source = test_descriptor.source
        ignore_test = ""
        if isinstance(source, TestSource):
            if source.test_type is not None:
                plugin_id = source.test_type
            else:
                ignore_test = source.module_name
                LOG.error(ErrorMessage.Common.Code_0101017.format(source.test_name))

        drivers = get_plugin(plugin_type=Plugin.DRIVER, plugin_id=plugin_id)
        if plugin_id is not None:
            if len(drivers) == 0:
                ignore_test = source.module_name
                error_message = ErrorMessage.Common.Code_0101018.format(source.test_name, plugin_id)
                LOG.error(error_message)
                report_not_executed(self.config.report_path, [("", test_descriptor)], error_message)
            else:
                check_result = False
                for driver in drivers:
                    driver_instance = driver.__class__()
                    device_options = get_device_options(
                        self.config.__dict__, source)
                    check_result = driver_instance.__check_environment__(
                        device_options)
                    if check_result or check_result is None:
                        self.test_drivers.append(
                            (driver_instance, test_descriptor))
                        break
                if check_result is False:
                    LOG.error(ErrorMessage.Common.Code_0101019.format(source.test_name, plugin_id))
        if ignore_test and hasattr(self.config, ConfigConst.component_mapper):
            getattr(self.config, ConfigConst.component_mapper).pop(ignore_test)

        for desc in test_descriptor.children:
            self._init_driver(desc)

    @classmethod
    def _check_report_path(cls, report_path):
        for _, _, files in os.walk(report_path):
            for _file in files:
                if _file.endswith(".xml"):
                    raise ParamError(ErrorMessage.Common.Code_0101020)


class Request:
    """
    Provides the necessary information for TestDriver to execute its tests.
    """

    def __init__(self, uuid=None, root=None, listeners=None, config=None):
        self.uuid = uuid
        self.root = root
        self.listeners = listeners if listeners else []
        self.config = config

    def get_listeners(self):
        return self.listeners

    def get_config(self):
        return self.config

    def get(self, key=None, default=""):
        # get value from self.config
        if not key:
            return default
        return getattr(self.config, key, default)

    def get_devices(self):
        if self.config is None:
            return []
        if not hasattr(self.config, "environment"):
            return []
        if not hasattr(self.config.environment, "devices"):
            return []
        return getattr(self.config.environment, "devices", [])

    def get_config_file(self):
        return self._get_source_value("config_file")

    def get_source_file(self):
        return self._get_source_value("source_file")

    def get_test_name(self):
        return self._get_source_value("test_name")

    def get_source_string(self):
        return self._get_source_value("source_string")

    def get_test_type(self):
        return self._get_source_value("test_type")

    def get_module_name(self):
        return self._get_source_value("module_name")

    def get_repeat_round(self):
        return get_repeat_round(self.root.unique_id)

    def _get_source(self):
        if not hasattr(self.root, "source"):
            return ""
        return getattr(self.root, "source", "")

    def _get_source_value(self, key=None, default=""):
        if not key:
            return default
        source = self._get_source()
        if not source:
            return default
        return getattr(source, key, default)

    def get_ta_class(self):
        # 从-ta class中提取执行参数，运行命令：run -l xx -ta class:1,2,3
        test_args = self.get_test_args()
        ta_class = list(set(test_args.get("class", [])))
        if ta_class:
            return ta_class
        # 从testfile.json中提取执行参数，运行命令：run -tf testfile.json
        return self.get_tf_class()

    def get_ta_not_class(self):
        # 从-ta class中提取执行参数，运行命令：run -l xx -ta notClass:1,2,3
        test_args = self.get_test_args()
        ta_not_class = list(set(test_args.get("notClass", [])))
        if ta_not_class:
            return ta_not_class
        # 从testfile.json中提取执行参数，运行命令：run -tf testfile.json
        return self.get_tf_not_class()

    def get_test_args(self):
        return self.config.testargs

    def get_tf_config(self, key: str = "", default=None):
        testfile_cfg = getattr(self.config, "tf_suite", {})
        if not key:
            return testfile_cfg
        return testfile_cfg.get(key, default)

    def get_tf_class(self):
        # 原先testfile.json是用cases字段，表示要运行的用例，现统一用class
        return list(set(self.get_tf_config("class", []) or self.get_tf_config("cases", [])))

    def get_tf_not_class(self):
        return list(set(self.get_tf_config("notClass", [])))

    def get_tf_kits(self):
        return self.get_tf_config("kits", [])

    def get_tf_test_args(self):
        return self.get_tf_config("test_args", [])

    def get_tf_loop_tests(self):
        loop_tests = self.get_tf_config("loop_tests", {})
        strategies = self.get_tf_config("loop_tests_strategies", {})
        strategies.update(loop_tests)
        return strategies
