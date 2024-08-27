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

import os
import traceback
import platform
from xml.etree import ElementTree

from devicetest.core.exception import TestPrepareError
from devicetest.core.constants import RunResult
from devicetest.error import ErrorMessage
from devicetest.utils.util import get_base_name
from devicetest.utils.util import import_from_file


class PrepareHandler:

    def __init__(self, log, cur_case, project, configs, devices, run_list):
        self.log = log
        self.cur_case = cur_case
        self.project = project
        self.configs = configs
        self.devices = devices
        self.is_run_prepare = False
        self.parse_test_list(run_list)

    def parse_prepare_config(self, case_path, xml_path):
        try:
            self.log.debug("parse prepare config case path：{}".
                           format(case_path))
            case_name = get_base_name(case_path)
            prepares = ElementTree.parse(xml_path).findall("prepare")
            for cls in prepares:
                cls_name = get_base_name(cls.attrib["class"].strip())
                for case in cls.findall("testcase"):
                    name = get_base_name(case.attrib["name"].strip())
                    if name and case_name == name:
                        if self.flash_prepare_config(case_name, cls_name):
                            break
        except Exception:
            self.log.debug(traceback.format_exc())
            self.log.error("parse prepare config exception error.")

    def flash_prepare_config(self, case_name, cls_name):
        if cls_name not in self.project.prepare.config.keys():
            self.project.prepare.config[cls_name] = {}
            self.project.prepare.config[cls_name]['status'] = 'unexecuted'
            self.project.prepare.config[cls_name]['cases'] = []
        if case_name not in self.project.prepare.config[cls_name]['cases']:
            self.project.prepare.config[cls_name]['cases'].append(case_name)
            return True
        return False

    def parse_test_list(self, test_list):
        """Parse user provided test list into internal format for test_runner.
        """
        if not self.project.prepare.path:
            return
        xml_path = os.path.join(self.project.prepare.path, 'prepare.xml')
        self.log.debug("prepare xml path:{}".format(xml_path))
        if os.access(xml_path, os.F_OK):
            for elem in test_list:
                self._parse_one_test_specifier(elem, xml_path)
            self.log.debug("prepare config:{}".format(
                self.project.prepare.config))
            if self.project.prepare.config:
                self.is_run_prepare = True
        else:
            self.log.warning(
                "{} not exists, please check.".format(xml_path))

    def _parse_one_test_specifier(self, item, xml_path):
        sys_type = platform.system()
        if sys_type == "Windows":
            tokens = item.split(';')
        elif sys_type == "Linux":
            tokens = item.split(':')
        elif sys_type == "Darwin":
            tokens = item.split(':')
        else:
            self.log.error("system '{}' is not support".format(sys_type))
            raise TestPrepareError(ErrorMessage.Common.Code_0201011)
        if len(tokens) > 2:
            raise TestPrepareError(ErrorMessage.Common.Code_0201012.format(item))
        if len(tokens) == 1:
            # This should be considered a test class name
            self.parse_prepare_config(tokens[0], xml_path)
        elif len(tokens) == 2:
            test_cls_name, test_case_names = tokens
            for elem in test_case_names.split(','):
                self.validate_test_name(elem.strip())
                self.parse_prepare_config(test_cls_name, xml_path)

    def validate_test_name(self, name):
        """Checks if a test name is valid. """
        if name == "" or name is None or len(name) < 1:
            raise TestPrepareError(ErrorMessage.Common.Code_0201013.format(name))

    def _init_run_prepare(self, test_cls_name):
        """
        prepare变量清理
        Args:
            test_cls_name:
        Returns:
        """
        self.cur_case.log_details_path = "./log/test_run_details.log"
        self.cur_case.log_path = "./log/test_run_summary.log"
        self.cur_case.set_case_screenshot_dir(self.project.test_suite_path,
                                              self.project.task_report_dir,
                                              test_cls_name)
        self.cur_case.report_path = self.cur_case.case_screenshot_dir + ".html"
        self.cur_case.case_result = RunResult.PASSED
        self.cur_case.description = ""
        self.cur_case.error_msg = ""
        self.cur_case.status = 0
        self.cur_case.image_num = 0
        self.cur_case.dump_xml_num = 0

    def run_prepare(self, is_teardown=False):
        if not self.is_run_prepare:
            return
        func = 'teardown' if is_teardown else 'setup'
        self.log.debug("in prepare {}".format(func))
        error_msg = None
        try:
            for cls, val in self.project.prepare.config.items():
                if self.project.prepare.path:
                    prepare_path = self.project.prepare.path
                else:
                    prepare_path = os.path.join(
                        self.project.test_suite_path, 'prepare')

                self.log.debug("prepare path:{}".format(prepare_path))
                test_cls_name = os.path.join(prepare_path, cls + '.py')
                if not os.access(test_cls_name, os.F_OK):
                    test_cls_name = os.path.join(prepare_path,
                                                 cls + '.pyd')
                    if not os.access(test_cls_name, os.F_OK):
                        py_path = os.path.join(prepare_path, cls + '.py')
                        # .py/.pyd
                        msg = "{} or {}".format(py_path, py_path + "d")
                        raise TestPrepareError(ErrorMessage.Common.Code_0201014.format(msg))
                self.log.info("import prepare script:{}".format(cls))
                self.project.cur_case_full_path = test_cls_name
                test_cls = import_from_file(prepare_path, cls)
                self.log.debug(
                    "Success to import {}.".format(test_cls_name))
                with test_cls(self.configs) as test_instance:
                    if 'setup' == func:
                        if 'unexecuted' == val['status']:
                            self.project.prepare.config[cls][
                                'status'] = 'executed'
                            result = test_instance._exec_func(
                                test_instance.setup)
                            if not result:
                                raise TestPrepareError(ErrorMessage.Common.Code_0201015)
                    else:
                        if 'executed' == val['status']:
                            self.project.prepare.config[cls][
                                'status'] = 'finsh'
                            result = test_instance._exec_func(
                                test_instance.teardown)
                            if not result:
                                self.log.warning(ErrorMessage.Common.Code_0201016)

        except TestPrepareError as e:
            error_msg = str(e)
            self.log.error(error_msg)
            self.log.error(traceback.format_exc())

        except Exception as e:
            error_msg = "run prepare error! {}".format(e)
            self.log.error(error_msg)
            self.log.error(traceback.format_exc())

        finally:
            self.log.debug("exit prepare {}".format(func))
            if error_msg is not None:
                raise TestPrepareError(error_msg)
