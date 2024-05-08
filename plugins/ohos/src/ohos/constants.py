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

from dataclasses import dataclass


__all__ = ["Constant", "ComType", "HostDrivenTestType",
           "ParserType", "DeviceLiteKernel", "CKit"]


class Constant:
    PRODUCT_PARAM_START = r"To Obtain Product Params Start"
    PRODUCT_PARAM_END = r"To Obtain Product Params End"
    TRUSTED_ROOT_CA = "trusted_root_ca.json"
    TRUSTED_ROOT_CA_PATH = "/system/etc/security/trusted_root_ca.json"
    TRUSTED_ROOT_CA_KEY = "C=CN, O=OpenHarmony, OU=OpenHarmony Team, CN=OpenHarmony Application Root CA"
    TRUSTED_ROOT_CA_VAL = """-----BEGIN CERTIFICATE-----
MIICRDCCAcmgAwIBAgIED+E4izAMBggqhkjOPQQDAwUAMGgxCzAJBgNVBAYTAkNO
MRQwEgYDVQQKEwtPcGVuSGFybW9ueTEZMBcGA1UECxMQT3Blbkhhcm1vbnkgVGVh
bTEoMCYGA1UEAxMfT3Blbkhhcm1vbnkgQXBwbGljYXRpb24gUm9vdCBDQTAeFw0y
MTAyMDIxMjE0MThaFw00OTEyMzExMjE0MThaMGgxCzAJBgNVBAYTAkNOMRQwEgYD
VQQKEwtPcGVuSGFybW9ueTEZMBcGA1UECxMQT3Blbkhhcm1vbnkgVGVhbTEoMCYG
A1UEAxMfT3Blbkhhcm1vbnkgQXBwbGljYXRpb24gUm9vdCBDQTB2MBAGByqGSM49
AgEGBSuBBAAiA2IABE023XmRaw2DnO8NSsb+KG/uY0FtS3u5LQucdr3qWVnRW5ui
QIL6ttNZBEeLTUeYcJZCpayg9Llf+1SmDA7dY4iP2EcRo4UN3rilovtfFfsmH4ty
3SApHVFzWUl+NwdH8KNCMEAwDwYDVR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMC
AQYwHQYDVR0OBBYEFBc6EKGrGXzlAE+s0Zgnsphadw7NMAwGCCqGSM49BAMDBQAD
ZwAwZAIwd1p3JzHN93eoPped1li0j64npgqNzwy4OrkehYAqNXpcpaEcLZ7UxW8E
I2lZJ3SbAjAkqySHb12sIwdSFKSN9KCMMEo/eUT5dUXlcKR2nZz0MJdxT5F51qcX
1CumzkcYhgU=
-----END CERTIFICATE-----
"""


@dataclass
class ComType(object):
    """
    ComType enumeration
    """
    cmd_com = "cmd"
    deploy_com = "deploy"


@dataclass
class HostDrivenTestType(object):
    """
    HostDrivenType enumeration
    """
    device_test = "DeviceTest"
    windows_test = "WindowsTest"


@dataclass
class ParserType:
    ctest_lite = "CTestLite"
    cpp_test_lite = "CppTestLite"
    cpp_test_list_lite = "CppTestListLite"
    open_source_test = "OpenSourceTest"
    build_only_test = "BuildOnlyTestLite"
    jsuit_test_lite = "JSUnitTestLite"


@dataclass
class DeviceLiteKernel(object):
    """
    Lite device os enumeration
    """
    linux_kernel = "linux"
    lite_kernel = "lite"


@dataclass
class CKit:
    push = "PushKit"
    liteinstall = "LiteAppInstallKit"
    command = "CommandKit"
    config = "ConfigKit"
    wifi = "WIFIKit"
    propertycheck = 'PropertyCheckKit'
    sts = 'STSKit'
    shell = "ShellKit"
    deploy = 'DeployKit'
    mount = 'MountKit'
    liteuikit = 'LiteUiKit'
    rootfs = "RootFsKit"
    liteshell = "LiteShellKit"
    app_install = "AppInstallKit"
    deploytool = "DeployToolKit"
    query = "QueryKit"
    component = "ComponentKit"
    permission = "PermissionKit"
    smartperf = "SmartPerfKit"
