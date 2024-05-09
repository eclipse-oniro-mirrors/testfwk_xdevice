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
import stat
from setuptools import setup


INSTALL_REQUIRES = [
    "jinja2",
    "xdevice"
]

setup(
    name='xdevice-devicetest',
    description='device test runner',
    url='',
    package_dir={'devicetest': ''},
    packages=[
        'devicetest',
        'devicetest.controllers',
        'devicetest.controllers.tools',
        'devicetest.core',
        'devicetest.core.suite',
        'devicetest.log',
        'devicetest.report',
        'devicetest.runner',
        'devicetest.utils',
        'devicetest.driver'
    ],
    package_data={
        'devicetest': [
            'res/template/*'
        ]
    },
    entry_points={
        'driver': [
            'device_test=devicetest.driver.device_test',
            'windows=devicetest.driver.windows'
        ]
    },
    zip_safe=False,
    install_requires=INSTALL_REQUIRES,
    extras_require={
        "full": ["numpy", "pillow", "opencv-python"]
    },
)
