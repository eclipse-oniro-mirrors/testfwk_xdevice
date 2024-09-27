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
3.unzip the template.zip to the path '{resource_path}'
'''


def check_report_template():
    sources = [
        "static/css/element-plus@2.3.4_index.css",
        "static/element-plus@2.3.4_index.full.js",
        "static/element-plus_icons-vue@2.0.10_index.iife.min.js",
        "static/EventEmitter.js",
        "static/vue@3.2.41_global.min.js",
    ]
    resource_path = os.path.join(os.path.dirname(__file__), "_core", "resource")
    template_path = os.path.join(resource_path, "template")
    missing_files = []
    for source in sources:
        tmp_file = os.path.join(template_path, source)
        if not os.path.exists(tmp_file):
            missing_files.append(tmp_file)
    if len(missing_files) > 0:
        return False
    return True


def download_template_resource():
    LOG.info("There is no report template in target path. "
             "Start download report template...")
    sources = [
        {
            "file": "static/css/element-plus@2.3.4_index.css",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.css"
        },
        {
            "file": "static/element-plus@2.3.4_index.full.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.full.js"
        },
        {
            "file": "static/element-plus_icons-vue@2.0.10_index.iife.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus-icons-vue/2.0.10/index.iife.min.js"
        },
        {
            "file": "static/EventEmitter.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/EventEmitter/5.2.8/EventEmitter.js"
        },
        {
            "file": "static/vue@3.2.41_global.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/vue/3.2.41/vue.global.min.js"
        }
    ]
    resource_path = os.path.join(os.path.dirname(__file__), "_core", "resource")
    template_path = os.path.join(resource_path, "template")
    for source in sources:
        file, url = source.get("file"), source.get("url")
        to_path = os.path.join(template_path, file)
        if os.path.exists(to_path):
            continue
        LOG.info(f"get report template resource {file} from {url}")
        try:
            response = request.urlopen(url, timeout=5)
            with open(to_path, 'wb') as f:
                f.write(response.read())
        except Exception as e:
            LOG.error(f"get report template resource error, {e}")
    LOG.info("Finish download report template...")
    # check report template
    if not check_report_template():
        LOG.error("------" * 5)
        LOG.error(notice_zh.format(resource_path=resource_path))
        LOG.error(notice_en.format(resource_path=resource_path))
        LOG.error("------" * 5)
        return False
    else:
        return True


def main_process(command=None):
    LOG.info(
        "*************** xDevice Test Framework %s Starting ***************" %
        VERSION)
    if not check_report_template():
        if not download_template_resource():
            return
    if command:
        args = str(command).split(" ")
        args.insert(0, "xDevice")
    else:
        args = sys.argv
    console = Console()
    console.console(args)


if __name__ == "__main__":
    main_process()
