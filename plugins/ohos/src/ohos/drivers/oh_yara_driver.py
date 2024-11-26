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
import time
import json
import re
import stat
import shutil
import csv
from datetime import datetime
from enum import Enum
from ohos.drivers import *
from ohos.environment.dmlib import process_command_ret
from ohos.error import ErrorMessage

__all__ = ["OHYaraTestDriver"]

LOG = platform_logger("OHYaraTestDriver")


class OHYaraConfig(Enum):
    HAP_FILE = "hap-file"
    BUNDLE_NAME = "bundle-name"
    CLEANUP_APPS = "cleanup-apps"

    OS_FULLNAME_LIST = "osFullNameList"
    VULNERABILITIES = "vulnerabilities"
    VUL_ID = "vul_id"
    OPENHARMONY_SA = "openharmony-sa"
    AFFECTED_VERSION = "affected_versions"
    MONTH = "month"
    SEVERITY = "severity"
    VUL_DESCRIPTION = "vul_description"
    DISCLOSURE = "disclosure"
    AFFECTED_FILES = "affected_files"
    YARA_RULES = "yara_rules"

    PASS = "pass"
    FAIL = "fail"
    BLOCK = "block"

    ERROR_MSG_001 = "The patch label is longer than two months (60 days), which violates the OHCA agreement."
    ERROR_MSG_002 = "This test case is beyond the patch label scope and does not need to be executed."
    ERROR_MSG_003 = "Modify the code according to the patch requirements: "


class VulItem:
    vul_id = ""
    month = ""
    severity = ""
    vul_description = dict()
    disclosure = dict()
    affected_files = ""
    affected_versions = ""
    yara_rules = ""
    trace = ""
    final_risk = OHYaraConfig.PASS.value
    complete = False


@Plugin(type=Plugin.DRIVER, id=DeviceTestType.oh_yara_test)
class OHYaraTestDriver(IDriver):
    def __init__(self):
        self.result = ""
        self.error_message = ""
        self.config = None
        self.tool_hap_info = dict()
        self.security_patch = None
        self.system_version = None

    def __check_environment__(self, device_options):
        pass

    def __check_config__(self, config):
        pass

    def __execute__(self, request):
        try:
            LOG.debug("Start to execute open harmony yara test")
            self.result = os.path.join(
                request.config.report_path, "result",
                '.'.join((request.get_module_name(), "xml")))
            self.config = request.config
            self.config.device = request.config.environment.devices[0]

            config_file = request.root.source.config_file
            suite_file = request.root.source.source_file

            if not suite_file:
                raise ParamError(ErrorMessage.Common.Code_0301001.format(request.root.source.source_string))
            LOG.debug("Test case file path: %s" % suite_file)
            self.config.device.set_device_report_path(request.config.report_path)
            self._run_oh_yara(config_file, request)

        except Exception as exception:
            self.error_message = exception
            if not getattr(exception, "error_no", ""):
                setattr(exception, "error_no", "03409")
            LOG.exception(self.error_message, exc_info=False, error_no="03409")
        finally:
            if self.tool_hap_info.get(OHYaraConfig.CLEANUP_APPS.value):
                cmd = ["uninstall", self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)]
                result = self.config.device.connector_command(cmd)
                LOG.debug("Try uninstall tools hap, bundle name is {}, result is {}".format(
                    self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value), result))

            serial = "{}_{}".format(str(request.config.device.__get_serial__()), time.time_ns())
            log_tar_file_name = "{}_{}".format(
                request.get_module_name(), str(serial).replace(":", "_"))
            self.config.device.device_log_collector.stop_hilog_task(
                log_tar_file_name,
                module_name=request.get_module_name(),
                repeat=request.config.repeat,
                repeat_round=request.get_repeat_round())

            self.result = check_result_report(
                request.config.report_path, self.result, self.error_message)

    def _get_driver_config(self, json_config):
        yara_bin = get_config_value('yara-bin',
                                    json_config.get_driver(), False)
        version_mapping_file = get_config_value('version-mapping-file',
                                                json_config.get_driver(), False)
        vul_info_file = get_config_value('vul-info-file',
                                         json_config.get_driver(), False)
        # get absolute file path
        self.config.yara_bin = get_file_absolute_path(yara_bin)
        self.config.version_mapping_file = get_file_absolute_path(version_mapping_file)
        self.config.vul_info_file = get_file_absolute_path(vul_info_file, [self.config.testcases_path])

        # get tool hap info
        # default value
        self.tool_hap_info = {
            OHYaraConfig.HAP_FILE.value: "sststool.hap",
            OHYaraConfig.BUNDLE_NAME.value: "com.example.sststool",
            OHYaraConfig.CLEANUP_APPS.value: "true"
        }
        tool_hap_info = get_config_value('tools-hap-info',
                                         json_config.get_driver(), False)
        if tool_hap_info:
            self.tool_hap_info[OHYaraConfig.HAP_FILE.value] = \
                tool_hap_info.get(OHYaraConfig.HAP_FILE.value, "sststool.hap")
            self.tool_hap_info[OHYaraConfig.BUNDLE_NAME.value] = \
                tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value, "com.example.sststool")
            self.tool_hap_info[OHYaraConfig.CLEANUP_APPS.value] = \
                tool_hap_info.get(OHYaraConfig.CLEANUP_APPS.value, "true")

    def _run_oh_yara(self, config_file, request=None):
        message_list = list()

        json_config = JsonParser(config_file)
        self._get_driver_config(json_config)

        # get device info
        self.security_patch = self.config.device.execute_shell_command(
            "param get const.ohos.version.security_patch").strip()
        self.system_version = self.config.device.execute_shell_command(
            "param get const.ohos.fullname").strip()

        if "fail" in self.system_version:
            self._get_full_name_by_tool_hap()

        vul_items = self._get_vul_items()
        # if security patch expire, case fail
        current_date_str = datetime.now().strftime('%Y-%m')
        if self._check_if_expire_or_risk(current_date_str):
            LOG.info("Security patch has expired. Set all case blocked, but still execute.")
            for _, item in enumerate(vul_items):
                item.final_risk = OHYaraConfig.BLOCK.value
                item.trace = "{}".format(OHYaraConfig.ERROR_MSG_001.value)
        else:
            LOG.info("Security patch is shorter than two months. Start yara test.")
        # if security patch expire, still execute
        # parse version mapping file
        mapping_info = self._do_parse_json(self.config.version_mapping_file)
        os_full_name_list = mapping_info.get(OHYaraConfig.OS_FULLNAME_LIST.value, None)
        # check if system version in version mapping list
        vul_version = os_full_name_list.get(self.system_version, None)
        # not in the maintenance scope, skip all case
        if not vul_version and "OpenHarmony" in self.system_version:
            vul_version_list = self.system_version.split("-")[-1].split(".")[:2]
            vul_version_list.append("0")
            vul_version = ".".join(vul_version_list)

        if vul_version is None:
            LOG.debug("The system version is not in the maintenance scope, skip it. "
                      "system versions is {}".format(self.system_version))
        else:
            for _, item in enumerate(vul_items):
                LOG.debug("Affected files: {}".format(item.affected_files))
                for index, affected_file in enumerate(item.affected_files):
                    has_inter = False
                    for i, _ in enumerate(item.affected_versions):
                        if self._check_if_intersection(vul_version, item.affected_versions[i]):
                            has_inter = True
                            break
                    if not has_inter:
                        LOG.debug("Yara rule [{}] affected versions has no intersection "
                                  "in mapping version, skip it. Mapping version is {}, "
                                  "affected versions is {}".format(item.vul_id, vul_version,
                                                                   item.affected_versions))
                        if item.final_risk == OHYaraConfig.BLOCK.value:
                            item.trace = "{}\\n{}".format(item.trace, "if ignore it, this testcase pass")
                        continue
                    local_path = os.path.join(request.config.report_path, OHYaraConfig.AFFECTED_FILES.value,
                                              request.get_module_name(), item.yara_rules[index].split('.')[0])
                    if not os.path.exists(local_path):
                        os.makedirs(local_path)
                    yara_file = get_file_absolute_path(item.yara_rules[index], [self.config.testcases_path])
                    self.config.device.pull_file(affected_file, local_path)
                    affected_file = os.path.join(local_path, os.path.basename(affected_file))
                    if not os.path.exists(affected_file):
                        LOG.debug("affected file [{}] is not exist, skip it.".format(item.affected_files[index]))
                        if item.final_risk == OHYaraConfig.BLOCK.value:
                            item.trace = "{}\\n{}".format(item.trace, "if ignore it, this testcase pass")
                        else:
                            item.final_risk = OHYaraConfig.PASS.value
                        continue
                    cmd = [self.config.yara_bin, yara_file, affected_file]
                    result = exec_cmd(cmd)
                    LOG.debug("Yara result: {}, affected file: {}".format(result, item.affected_files[index]))
                    if item.final_risk == OHYaraConfig.BLOCK.value:
                        item.trace = "{}\\n{}".format(item.trace, "if ignore it, ")

                        if "testcase pass" in result:
                            item.trace = "{}{}".format(item.trace, "this testcase pass")
                            break
                        else:
                            item.trace = "{}{}".format(item.trace, "this testcase failed")
                    else:
                        if "testcase pass" in result:
                            item.final_risk = OHYaraConfig.PASS.value
                            break
                        else:
                            if self._check_if_expire_or_risk(item.month, check_risk=True):
                                item.trace = "{}{}".format(OHYaraConfig.ERROR_MSG_003.value,
                                                           item.disclosure.get("zh", ""))
                                item.final_risk = OHYaraConfig.FAIL.value
                            else:
                                item.final_risk = OHYaraConfig.BLOCK.value
                                item.trace = "{}{}".format(item.trace, OHYaraConfig.ERROR_MSG_002.value)
                    # if no risk delete files, if rule has risk keep it
                    if item.final_risk != OHYaraConfig.FAIL.value:
                        local_path = os.path.join(request.config.report_path, OHYaraConfig.AFFECTED_FILES.value,
                                                  request.get_module_name(), item.yara_rules[index].split('.')[0])
                        if os.path.exists(local_path):
                            LOG.debug(
                                "Yara rule [{}] has no risk, remove affected files.".format(
                                    item.yara_rules[index]))
                            shutil.rmtree(local_path)
                item.complete = True
        self._generate_yara_report(request, vul_items, message_list)
        self._generate_xml_report(request, vul_items, message_list)

    def _check_if_expire_or_risk(self, date_str, expire_time=2, check_risk=False):
        self.security_patch = self.security_patch.replace(' ', '')
        self.security_patch = self.security_patch.replace('/', '-')
        # get current date
        source_date = datetime.strptime(date_str, '%Y-%m')
        security_patch_date = datetime.strptime(self.security_patch[:-3], '%Y-%m')
        y1, m1 = source_date.year, source_date.month
        y2, m2 = security_patch_date.year, security_patch_date.month
        months = (y1 - y2) * 12 + (m1 - m2)

        if check_risk:
            # vul time after security patch time no risk
            LOG.debug("Security patch time: {}, vul time: {}, delta_months: {}"
                      .format(self.security_patch[:-3], date_str, months))
            return months <= 0
        else:
            # check if security patch time expire current time 2 months
            LOG.debug("Security patch time: {}, current time: {}, delta_months: {}"
                      .format(self.security_patch[:-3], date_str, months))
            return abs(months) > expire_time

    @staticmethod
    def _check_if_intersection(source_version, dst_version):
        # para dst_less_sor control if dst less than source
        def _do_check(src, dst, dst_less_src=True):
            if re.match(r'^\d{1,3}.\d{1,3}.\d{1,3}', src) and \
                    re.match(r'^\d{1,3}.\d{1,3}.\d{1,3}', dst):
                source_vers = src.split(".")
                dst_vers = dst.split(".")
                for index, _ in enumerate(source_vers):
                    if dst_less_src:
                        # check if all source number less than dst number
                        if int(source_vers[index]) < int(dst_vers[index]):
                            return False
                    else:
                        # check if all source number larger than dst number
                        if int(source_vers[index]) > int(dst_vers[index]):
                            return False
                return True
            return False

        source_groups = source_version.split("-")
        dst_groups = dst_version.split("-")
        if source_version == dst_version:
            return True
        elif len(source_groups) == 1 and len(dst_groups) == 1:
            return source_version == dst_version
        elif len(source_groups) == 1 and len(dst_groups) == 2:
            return _do_check(source_groups[0], dst_groups[0]) and \
                _do_check(source_groups[0], dst_groups[1], dst_less_src=False)
        elif len(source_groups) == 2 and len(dst_groups) == 1:
            return _do_check(source_groups[0], dst_groups[0], dst_less_src=False) and \
                _do_check(source_groups[1], dst_groups[0])
        elif len(source_groups) == 2 and len(dst_groups) == 2:
            return _do_check(source_groups[0], dst_groups[1], dst_less_src=False) and \
                _do_check(source_groups[1], dst_groups[0])
        return False

    def _get_vul_items(self):
        vul_items = list()
        vul_info = self._do_parse_json(self.config.vul_info_file)
        vulnerabilities = vul_info.get(OHYaraConfig.VULNERABILITIES.value, [])
        for _, vul in enumerate(vulnerabilities):
            affected_versions = vul.get(OHYaraConfig.AFFECTED_VERSION.value, [])
            item = VulItem()
            item.vul_id = vul.get(OHYaraConfig.VUL_ID.value, dict()).get(OHYaraConfig.OPENHARMONY_SA.value, "")
            item.affected_versions = affected_versions
            item.month = vul.get(OHYaraConfig.MONTH.value, "")
            item.severity = vul.get(OHYaraConfig.SEVERITY.value, "")
            item.vul_description = vul.get(OHYaraConfig.VUL_DESCRIPTION.value, "")
            item.disclosure = vul.get(OHYaraConfig.DISCLOSURE.value, "")
            item.affected_files = \
                vul["affected_device"]["standard"]["linux"]["arm"]["scan_strategy"]["ists"]["yara"].get(
                    OHYaraConfig.AFFECTED_FILES.value, [])
            item.yara_rules = \
                vul["affected_device"]["standard"]["linux"]["arm"]["scan_strategy"]["ists"]["yara"].get(
                    OHYaraConfig.YARA_RULES.value, [])
            vul_items.append(item)
        LOG.debug("Vul size is {}".format(len(vul_items)))
        return vul_items

    @staticmethod
    def _do_parse_json(file_path):
        json_content = None
        if not os.path.exists(file_path):
            raise ParamError(ErrorMessage.Common.Code_0301015.format(file_path))
        flags = os.O_RDONLY
        modes = stat.S_IWUSR | stat.S_IRUSR
        with os.fdopen(os.open(file_path, flags, modes),
                       "r", encoding="utf-8") as file_content:
            json_content = json.load(file_content)
        if json_content is None:
            raise ParamError(ErrorMessage.Config.Code_0302012.format(file_path))
        return json_content

    def _get_full_name_by_tool_hap(self):
        # check if has install
        result = self.config.device.execute_shell_command(
            "bm dump -a | grep {}".format(self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        LOG.debug(result)
        if self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value) not in result:
            hap_path = get_file_absolute_path(self.tool_hap_info.get(OHYaraConfig.HAP_FILE.value))
            self.config.device.push_file(hap_path, "/data/local/tmp")
            result = self.config.device.execute_shell_command(
                "bm install -p /data/local/tmp/{}".format(os.path.basename(hap_path)))
            LOG.debug(result)
            self.config.device.execute_shell_command(
                "mkdir -p /data/app/el2/100/base/{}/haps/entry/files".format(
                    self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        self.config.device.execute_shell_command(
            "aa start -a {}.MainAbility -b {}".format(
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value),
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value)))
        time.sleep(1)
        self.system_version = self.config.device.execute_shell_command(
            "cat /data/app/el2/100/base/{}/haps/entry/files/osFullNameInfo.txt".format(
                self.tool_hap_info.get(OHYaraConfig.BUNDLE_NAME.value))).replace('"', '')
        LOG.debug(self.system_version)

    def _generate_yara_report(self, request, vul_items, result_message):
        result_message.clear()
        yara_report = os.path.join(request.config.report_path, "vul_info_{}.csv"
                                   .format(request.config.device.device_sn))
        if os.path.exists(yara_report):
            data = []
        else:
            data = [
                ["设备版本号:", self.system_version, "设备安全补丁标签:", self.security_patch],
                ["漏洞编号", "严重程度", "披露时间", "检测结果", "修复建议", "漏洞描述"]
            ]
        fd = os.open(yara_report, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o755)
        for _, item in enumerate(vul_items):
            data.append([item.vul_id, item.severity,
                         item.month, item.final_risk,
                         item.disclosure.get("zh", ""), item.vul_description.get("zh", "")])
            result = "{}|{}|{}|{}|{}|{}|{}\n".format(
                item.vul_id, item.severity,
                item.month, item.final_risk,
                item.disclosure.get("zh", ""), item.vul_description.get("zh", ""),
                item.trace)
            result_message.append(result)
        with os.fdopen(fd, "a", newline='') as file_handler:
            writer = csv.writer(file_handler)
            writer.writerows(data)

    def _generate_xml_report(self, request, vul_items, message_list):
        result_message = "".join(message_list)
        listener_copy = request.listeners.copy()
        parsers = get_plugin(
            Plugin.PARSER, CommonParserType.oh_yara)
        if parsers:
            parsers = parsers[:1]
        for listener in listener_copy:
            listener.device_sn = self.config.device.device_sn
        parser_instances = []
        for parser in parsers:
            parser_instance = parser.__class__()
            parser_instance.suites_name = request.get_module_name()
            parser_instance.vul_items = vul_items
            parser_instance.listeners = listener_copy
            parser_instances.append(parser_instance)
        handler = ShellHandler(parser_instances)
        process_command_ret(result_message, handler)

    def __result__(self):
        return self.result if os.path.exists(self.result) else ""
