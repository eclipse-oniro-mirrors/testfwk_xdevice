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
import sys
from urllib import request
from xdevice import Console
from xdevice import platform_logger
from xdevice import ReportConstant
from xdevice import VERSION

srcpath = os.path.dirname(os.path.dirname(__file__))
sys.path.append(srcpath)

LOG = platform_logger("Main")
notice_zh = '''
由于测试报告模板缺失导致运行失败! 请按如下指引进行修复：
1.下载已归档的报告模板文件
  下载链接：https://gitee.com/openharmony-sig/compatibility/raw/master/test_suite/resource/xdevice/template.zip?lfs=1
2.删除“{resource_path}”路径下的template文件夹
3.解压template.zip到“{resource_path}”路径下
'''
notice_en = '''
Run failed due to missing the report template! Please follow the following instructions to fix the issue.
1.Download archived report template files
  Download Link: https://gitee.com/openharmony-sig/compatibility/raw/master/test_suite/resource/xdevice/template.zip?lfs=1
2.Remove the template folder in the path '{resource_path}'
3.Unzip the template.zip to the path '{resource_path}'
'''


def check_report_template():
    resource_path = os.path.join(os.path.dirname(__file__), "_core", "resource")
    template_path = os.path.join(resource_path, "template")
    missing_files = []
    for source in ReportConstant.new_template_sources:
        file, url = source.get("file"), source.get("url")
        to_path = os.path.join(template_path, file)
        if os.path.exists(to_path):
            continue
        LOG.info(f"get report template resource {file} from {url}")
        try:
            response = request.urlopen(url, timeout=5)
            with open(to_path, 'wb') as f:
                os.chmod(to_path, 0o600)
                f.write(response.read())
        except Exception as e:
            LOG.error(f"get report template resource error, {e}")
            if not os.path.exists(to_path):
                missing_files.append(to_path)
            break
    if len(missing_files) == 0:
        return
    LOG.warning("------" * 5)
    LOG.warning(notice_zh.format(resource_path=resource_path))
    LOG.warning(notice_en.format(resource_path=resource_path))
    LOG.warning("------" * 5)
    LOG.warning("Download report template failed, using the default report template.")


def main_process(command=None):
    LOG.info(
        "*************** xDevice Test Framework %s Starting ***************" %
        VERSION)
    check_report_template()
    if command:
        args = str(command).split(" ")
        args.insert(0, "xDevice")
    else:
        args = sys.argv
    console = Console()
    console.console(args)


if __name__ == "__main__":
    main_process()
