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

import json
import os
import sys
from dataclasses import dataclass
from xml.etree import ElementTree

from _core.error import ErrorMessage
from _core.exception import ParamError
from _core.logger import platform_logger
from _core.utils import get_local_ip
from _core.constants import ConfigConst
from _core.constants import Cluster

__all__ = ["UserConfigManager"]
LOG = platform_logger("ConfigManager")


def initialize(func):
    def wrapper(self, *args, **kwargs):
        name = "_" + func.__name__
        if not hasattr(self, name):
            setattr(self, name, func(self, *args, **kwargs))
        return getattr(self, name)

    return wrapper


@dataclass
class ConfigFileConst(object):
    userconfig_filepath = "user_config.xml"


class UserConfigManager(object):
    def __init__(self, config_file="", env=""):
        from xdevice import Variables
        try:
            if env:
                self.config_content = ElementTree.fromstring(env)
            else:
                if config_file:
                    self.file_path = config_file
                else:
                    user_path = os.path.join(Variables.exec_dir, "config")
                    top_user_path = os.path.join(Variables.top_dir, "config")
                    config_path = os.path.join(Variables.res_dir, "config")
                    paths = [user_path, top_user_path, config_path]

                    for path in paths:
                        if os.path.exists(os.path.abspath(os.path.join(
                                path, ConfigFileConst.userconfig_filepath))):
                            self.file_path = os.path.abspath(os.path.join(
                                path, ConfigFileConst.userconfig_filepath))
                            break

                LOG.debug("User config path: %s" % self.file_path)
                if os.path.exists(self.file_path):
                    tree = ElementTree.parse(self.file_path)
                    self.config_content = tree.getroot()
                else:
                    raise ParamError(ErrorMessage.UserConfig.Code_0103001)

        except SyntaxError as error:
            err = ErrorMessage.UserConfig.Code_0103003 if env else ErrorMessage.UserConfig.Code_0103002
            err_msg = err.format(error)
            raise ParamError(err_msg) from error

    @property
    @initialize
    def environment(self):
        envs = []
        ele_environment = self.config_content.find("environment")
        if ele_environment is None:
            return envs
        dev_alias = {}
        for device in ele_environment.findall("device"):
            device_type = device.get("type", "").strip()
            if not device_type or device_type == "com":
                continue
            # 设备管理器使用usb_type作为入参，故需将type转换为usb_type
            data = {"usb_type": device_type, "label": ""}
            data.update(device.attrib)
            for info in device.findall("info"):
                dev = {"ip": "", "port": "", "sn": "", "alias": ""}
                dev.update(info.attrib)
                dev.update(data)

                # 去除空格，alias字符转大写
                new_dev = {}
                for k, v in dev.items():
                    if k == "alias":
                        v = v.upper()
                    v = v.strip()
                    new_dev[k] = v
                dev.update(new_dev)

                # 不允许设备的别名相同
                sn, alias = dev.get("sn"), dev.get("alias")
                if alias:
                    for k, v in dev_alias.items():
                        if alias == v:
                            raise ParamError(ErrorMessage.UserConfig.Code_0103004.format(sn, k))
                dev_alias.update({sn: alias})

                ip = dev.get("ip")
                if not ip:
                    dev.update({"ip": "127.0.0.1"})
                envs.append(dev)
        return envs

    @property
    @initialize
    def testcases(self):
        return self.get_element_cfg("testcases")

    @property
    @initialize
    def resource(self):
        return self.get_element_cfg("resource")

    @property
    @initialize
    def devicelog(self):
        """
        <devicelog>
            <enable>ON</enable>
            <clear>TRUE</clear>
            <dir></dir>
            <loglevel>INFO</loglevel>
            <hdc>FALSE</hdc>
            <suitecaselog>ON</suitecaselog>
        </devicelog>
        """
        tag = "devicelog"
        cfg = self.get_element_cfg(tag)

        # 若是旧配置方式<devicelog>ON</devicelog>，转换为{"enable": "ON"}
        enable = cfg.get(tag)
        if enable is not None:
            cfg.pop(tag)
            cfg.update({ConfigConst.tag_enable: "ON" if enable.upper() == "ON" else "OFF"})

        # 从自定义参数中更新配置
        if self.pass_through:
            user_define = None
            try:
                user_define = json.loads(self.pass_through).get("user_define")
            except ValueError as error:
                LOG.warning("error:{}".format(error))
            if user_define and isinstance(user_define, dict):
                device_log = user_define.get(tag)
                if device_log and isinstance(device_log, dict):
                    cfg.update(device_log)

        # 默认配置参数
        default_cfg = {
            ConfigConst.tag_enable: "ON",
            ConfigConst.tag_suite_case_log: "ON",
            ConfigConst.tag_clear: "TRUE",
            ConfigConst.tag_dir: "",
            ConfigConst.tag_loglevel: "INFO",
            ConfigConst.tag_hdc: "FALSE"
        }
        for k, v in default_cfg.items():
            value = cfg.get(k)
            if not value:
                cfg.update({k: v})
                continue
            if isinstance(value, bool):
                value = str(value)
            if k != ConfigConst.tag_dir and value.lower() in ['true', 'false', 'on', 'off']:
                cfg.update({k: value.upper()})
        return cfg

    @property
    @initialize
    def loglevel(self):
        data = self.get_element_cfg(ConfigConst.tag_loglevel)
        level = data.get(ConfigConst.tag_loglevel)
        if level is not None:
            data.pop(ConfigConst.tag_loglevel)
            level = level.upper()
            level = level if level in ["DEBUG", "INFO"] else ""
            data.update({"console": level or "INFO"})
        return data

    @property
    @initialize
    def taskargs(self):
        """
        <taskargs>
            <agent_mode></agent_mode>
            <pass_through></pass_through>
            <repeat></repeat>
            <screenshot>false</screenshot>
            <screenrecorder>false</screenrecorder>
        </taskargs>
        """
        data = self.get_element_cfg("taskargs")
        pass_through = data.get(ConfigConst.pass_through)
        if pass_through:
            user_define = None
            try:
                user_define = json.loads(pass_through).get("user_define")
            except ValueError:
                pass
            if user_define:
                self.update_task_args(data, user_define)
        return data

    @property
    @initialize
    def custom(self):
        """
        <custom></custom>
        """
        return self.get_element_cfg("custom")

    @property
    @initialize
    def cluster(self):
        """
        <cluster>
          <enable>true/false</enable>
          <service_mode>controller/worker</service_mode>
          <service_port>8000</service_port>
          <control_service_url>http://127.0.0.1:8000</control_service_url>
        </cluster>
        """
        cfg = self.get_element_cfg(ConfigConst.cluster)
        enable = cfg.get(ConfigConst.tag_enable) or "false"
        service_mode = cfg.get(ConfigConst.service_mode) or Cluster.controller
        service_port = cfg.get(ConfigConst.service_port) or Cluster.service_port
        cfg.update({
            ConfigConst.tag_enable: enable.lower(),
            ConfigConst.service_mode: service_mode.lower(),
            ConfigConst.service_port: service_port.lower()
        })
        return cfg

    def enable_cluster(self):
        enable = self.cluster.get(ConfigConst.tag_enable) == "true"
        if enable:
            if sys.version_info < (3, 10, 0):
                raise Exception(ErrorMessage.Cluster.Code_0104026)
        return enable

    @property
    @initialize
    def pass_through(self):
        return self.taskargs.get(ConfigConst.pass_through)

    def get_element_cfg(self, tag):
        element = self.config_content.find(tag)
        return {} if element is None else self.get_element_dict(element)

    @staticmethod
    def get_element_dict(element, is_top=True):
        """
        element: ElementTree.Element, traversal element
        is_top: bool, when the element has no child and if is the top, result as dict else as text
        return : dict
        """
        if not isinstance(element, ElementTree.Element):
            raise TypeError("element must be instance of xml.etree.ElementTree.Element")
        data = element.attrib
        if len(element) == 0:
            text = "" if element.text is None else element.text.strip()
            if is_top:
                data.update({element.tag: text})
                data = {k: v.strip() for k, v in data.items()}
                return data
            return text

        for sub in element:
            k, v = sub.tag, UserConfigManager.get_element_dict(sub, is_top=False)
            # 同一层级存在多个同名tag，数据存为列表
            if len(element.findall(k)) > 1:
                value = data.get(k) if k in data else []
                value.append(v)
                data.update({k: value})
            else:
                data.update({k: v})
        return data

    def get_batch_run_size(self):
        cfg_name = ConfigConst.TaskArgs.batch_run_size.value
        default_size = 200
        size = str(self.taskargs.get(cfg_name, default_size)).strip()
        if not size or not size.isdigit():
            return default_size
        size = int(size)
        return size if size > 0 else default_size

    def get_max_log_line_in_html(self):
        """控制用例html报告最多显示运行日志行数"""
        cfg_name = ConfigConst.TaskArgs.max_log_line_in_html.value
        # 默认的最多显示行数
        max_line_default = 20000
        if cfg_name not in self.taskargs:
            return max_line_default
        max_line = self.taskargs.get(cfg_name).strip()
        if max_line == "None":
            return None
        if not max_line or not max_line.isdigit():
            return max_line_default
        max_line = int(max_line)
        return max_line if max_line > max_line_default else max_line_default

    def get_wifi_config(self):
        wifi = self.taskargs.get("wifi")
        if wifi:
            return wifi.split(",")
        wifi = self.custom.get("wifi")
        # 未配置
        if wifi is None:
            return []
        # 只配置了一个
        if isinstance(wifi, dict):
            wifi = [wifi]
        data = []
        for info in wifi:
            if not isinstance(info, dict):
                continue
            ssid = info.get("ssid", "")
            password = info.get("password", "")
            wifi_type = info.get("type", "")
            if not ssid:
                continue
            if not wifi_type:
                data.append("{}:{}".format(ssid, password))
            else:
                data.append("{}:{}:{}".format(ssid, password, wifi_type))
        return data

    def update_task_args(self, task_args=None, new_args=None):
        if task_args is None:
            task_args = self.taskargs
        if not isinstance(new_args, dict):
            return
        # 目前在用的参数列表
        known_test_args = [i.value for i in ConfigConst.TaskArgs]
        # 更新同名参数
        keys = set(task_args.keys()) & set(new_args.keys()) | set(known_test_args)
        for key in keys:
            value = new_args.get(key)
            if not value or task_args.get(key) == value:
                continue
            task_args.update({key: value})

    def get_user_config_list(self, tag_name):
        data_dic = {}
        for child in self.config_content:
            if tag_name == child.tag:
                for sub in child:
                    data_dic[sub.tag] = sub.text
        return data_dic

    @staticmethod
    def remove_strip(value):
        return value.strip()

    @staticmethod
    def _verify_duplicate(items):
        if len(set(items)) != len(items):
            LOG.warning("Find duplicate sn config, configuration incorrect")
            return False
        return True

    def _handle_str(self, input_string):
        config_list = map(self.remove_strip, input_string.split(';'))
        config_list = [item for item in config_list if item]
        if config_list:
            if not self._verify_duplicate(config_list):
                return []
        return config_list

    def get_sn_list(self, input_string):
        sn_select_list = []
        if input_string:
            sn_select_list = self._handle_str(input_string)
        return sn_select_list

    def get_remote_config(self):
        remote_dic = {}
        data_dic = self.get_user_config_list("remote")

        if "ip" in data_dic.keys() and "port" in data_dic.keys():
            remote_ip = data_dic.get("ip", "")
            remote_port = data_dic.get("port", "")
        else:
            remote_ip = ""
            remote_port = ""

        if (not remote_ip) or (not remote_port):
            remote_ip = ""
            remote_port = ""
        if remote_ip == get_local_ip():
            remote_ip = "127.0.0.1"
        remote_dic["ip"] = remote_ip
        remote_dic["port"] = remote_port
        return remote_dic

    def get_user_config(self, target_name, filter_name=None):
        data_dic = {}
        all_nodes = self.config_content.findall(target_name)
        if not all_nodes:
            return data_dic

        for node in all_nodes:
            if filter_name:
                if node.get('label') != filter_name:
                    continue
            for sub in node:
                data_dic[sub.tag] = sub.text if sub.text else ""

        return data_dic

    def get_testcases_dir(self):
        from xdevice import Variables
        testcases_dir = self.testcases.get(ConfigConst.tag_dir)
        if testcases_dir:
            if os.path.isabs(testcases_dir):
                return testcases_dir
            return os.path.abspath(
                os.path.join(Variables.exec_dir, testcases_dir))
        return os.path.abspath(os.path.join(Variables.exec_dir, "testcases"))

    def get_resource_path(self):
        from xdevice import Variables
        resource_dir = self.resource.get(ConfigConst.tag_dir)
        if resource_dir:
            if os.path.isabs(resource_dir):
                return resource_dir
            return os.path.abspath(
                os.path.join(Variables.exec_dir, resource_dir))
        return os.path.abspath(os.path.join(Variables.exec_dir, "resource"))

    def environment_enable(self):
        if self.config_content.find("environment") or \
                self.config_content.find("environment/device"):
            return True
        return False

    def get_max_driver_threads(self):
        if not self.taskargs or not self.taskargs.get("max_driver_threads"):
            return 8
        value = int(self.taskargs.get("max_driver_threads"))
        return value if value > 0 else 8
