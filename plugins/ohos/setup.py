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
from setuptools import setup

INSTALL_REQUIRES = [
    "xdevice"
]

setup(
    name='xdevice-ohos',
    description='plugin for ohos',
    url='',
    package_dir={'': 'src'},
    packages=['ohos',
              'ohos.drivers',
              'ohos.config',
              'ohos.environment',
              'ohos.executor',
              'ohos.managers',
              'ohos.parser',
              'ohos.testkit'
              ],
    entry_points={
        'device': [
            'device=ohos.environment.device',
            'device_lite=ohos.environment.device_lite'
        ],
        'manager': [
            'manager=ohos.managers.manager_device',
            'manager_lite=ohos.managers.manager_lite'
        ],
        'driver': [
            'cpp_driver=ohos.drivers.cpp_driver',
            'cpp_driver_lite=ohos.drivers.cpp_driver_lite',
            'jsunit_driver=ohos.drivers.jsunit_driver',
            'ltp_posix_driver=ohos.drivers.ltp_posix_driver',
            'oh_jsunit_driver=ohos.drivers.oh_jsunit_driver',
            'oh_kernel_driver=ohos.drivers.oh_kernel_driver',
            'oh_yara_driver=ohos.drivers.oh_yara_driver',
            'c_driver_lite=ohos.drivers.c_driver_lite',
        ],
        'listener': [
            'listener=ohos.executor.listener',
        ],
        'testkit': [
            'kit=ohos.testkit.kit',
            'kit_lite=ohos.testkit.kit_lite'
        ],
        'parser': [
            'build_only_parser_lite=ohos.parser.build_only_parser_lite',
            'c_parser_lite=ohos.parser.c_parser_lite',
            'cpp_parser_lite=ohos.parser.cpp_parser_lite',
            'jsunit_parser_lite=ohos.parser.jsunit_parser_lite',
            'opensource_parser_lite=ohos.parser.opensource_parser_lite',

            'cpp_parser=ohos.parser.cpp_parser',
            'jsunit_parser=ohos.parser.jsunit_parser',
            'junit_parser=ohos.parser.junit_parser',
            'oh_jsunit_parser=ohos.parser.oh_jsunit_parser',
            'oh_kernel_parser=ohos.parser.oh_kernel_parser',
            'oh_rust_parser=ohos.parser.oh_rust_parser',
            'oh_yara_parser=ohos.parser.oh_yara_parser',
        ]
    },
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
)
