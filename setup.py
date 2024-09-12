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
from urllib import request

from setuptools import setup

install_requires = []
notice_zh = '''
由于网络原因，导致测试报告模板构建失败，请按如下指引进行修复:
1.下载已归档的报告模板文件
  下载链接：https://gitee.com/openharmony-sig/compatibility/test_suite/resource/xdevice/template
2.删除xdevice源码src/xdevice/_core/resource路径下的template文件夹
3.复制在第1步下载到本地的报告模板template文件夹到xdevice源码src/xdevice/_core/resource路径下
'''
notice_en = '''
Due to network issues, the construction of the test report template failed, please follow 
the following instructions to fix the issue
1.Download archived report template files
  Download Link: https://gitee.com/openharmony-sig/compatibility/test_suite/resource/xdevice/template
2.Remove the template folder in the xdevice source code path 'src/xdevice/_come/resource'
3.Copy the template folder downloaded locally in step 1 to the xdevice source code path 'src/xdevice/_come/resource'
'''


def setup_template_resource():
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
    template_path = os.path.join(
        os.path.dirname(__file__),
        "src/xdevice/_core/resource/template")
    for source in sources:
        file, url = source.get("file"), source.get("url")
        to_path = os.path.join(template_path, file)
        if os.path.exists(to_path):
            continue
        print(f"get report template resource {file} from {url}")
        try:
            request.urlretrieve(url, to_path)
        except Exception as e:
            print(e)
        if not os.path.exists(to_path):
            print("------" * 5)
            print(notice_zh)
            print(notice_en)
            print("------" * 5)
            raise Exception("get report template resource error")


setup_template_resource()
setup(
    name='xdevice',
    description='xdevice test framework',
    url='',
    package_dir={'': 'src'},
    packages=[
        'xdevice',
        'xdevice._core',
        'xdevice._core.command',
        'xdevice._core.config',
        'xdevice._core.driver',
        'xdevice._core.environment',
        'xdevice._core.executor',
        'xdevice._core.report',
        'xdevice._core.testkit',
        'xdevice._core.context',
    ],
    package_data={
        'xdevice._core': [
            'resource/*.txt',
            'resource/config/*.xml',
            'resource/template/*',
            'resource/template/static/*',
            'resource/template/static/components/*',
            'resource/template/static/css/*',
            'resource/tools/*'
        ]
    },
    entry_points={
        'console_scripts': [
            'xdevice=xdevice.__main__:main_process',
            'xdevice_report=xdevice._core.report.__main__:main_report'
        ]
    },
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        "full": ["cryptography"]
    },
)
