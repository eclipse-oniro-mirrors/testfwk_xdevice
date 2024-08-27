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

from devicetest.core.variables import DeccVariable
from devicetest.log.logger import DeviceTestLog as log
from devicetest.utils.file_util import create_dir
from xdevice import stop_standing_subprocess
from xdevice import DeviceConnectorType
from xdevice import TestDeviceState

LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 6001
URL = "/"
FORWARD_PORT = 9501


class ScreenAgent:
    SCREEN_AGENT_MAP = {}

    def __init__(self, device):
        self._device = device
        self.log = device.log
        self.proc = None
        self.thread = None
        self.local_port = None
        self.is_server_started = False

    def __del__(self):
        self.terminate()

    @classmethod
    def get_instance(cls, _device):
        _device.log.debug("in get instance.")
        instance_sn = _device.device_sn
        if instance_sn in ScreenAgent.SCREEN_AGENT_MAP:
            return ScreenAgent.SCREEN_AGENT_MAP[instance_sn]

        agent = ScreenAgent(_device)
        ScreenAgent.SCREEN_AGENT_MAP[instance_sn] = agent
        _device.log.debug("out get instance.")
        return agent

    @classmethod
    def remove_instance(cls, _device):
        _sn = _device.device_sn
        if _sn in ScreenAgent.SCREEN_AGENT_MAP:
            ScreenAgent.SCREEN_AGENT_MAP[_sn].terminate()
            del ScreenAgent.SCREEN_AGENT_MAP[_sn]

    @classmethod
    def get_screenshot_dir(cls):
        base_path = DeccVariable.cur_case().case_screenshot_dir
        return os.path.join(base_path, DeccVariable.cur_case().suite_name, DeccVariable.cur_case().name)

    @classmethod
    def get_take_picture_path(cls, _device, picture_name,
                              ext=".png", exe_type="takeImage"):
        """新增参数exeType，默认值为takeImage;可取值takeImage/dumpWindow"""
        if os.path.isfile(picture_name):
            folder = os.path.dirname(picture_name)
            create_dir(folder)
            return picture_name, os.path.basename(picture_name)

        folder = cls.get_screenshot_dir()
        create_dir(folder)
        if picture_name.endswith(ext):
            picture_name = picture_name.strip(ext)

        if exe_type == "takeImage":
            save_name = "{}.{}{}{}".format(
                _device.device_sn.replace("?", "sn").replace(":", "_"), picture_name,
                DeccVariable.cur_case().image_num, ext)
        elif exe_type == "videoRecord":
            save_name = "{}.{}{}{}".format(
                _device.device_sn.replace("?", "sn").replace(":", "_"), picture_name,
                DeccVariable.cur_case().video_num, ext)
        elif exe_type == "stepImage":
            save_name = "{}.{}{}".format(
                _device.device_sn.replace("?", "sn").replace(":", "_"), picture_name, ext)
        else:
            save_name = "{}.{}{}{}".format(
                _device.device_sn.replace("?", "sn").replace(":", "_"), picture_name,
                DeccVariable.cur_case().dump_xml_num, ext)

        fol_path = os.path.join(folder, save_name)
        if exe_type == "takeImage":
            DeccVariable.cur_case().image_num += 1
        elif exe_type == "videoRecord":
            DeccVariable.cur_case().video_num += 1
        else:
            if exe_type != "stepImage":
                DeccVariable.cur_case().dump_xml_num += 1
        return fol_path, save_name

    @classmethod
    def screen_take_picture(cls, args, result, _ta=None, is_raise_exception=True):
        # When the phone is off, you can set the screenshot off function
        pass

    @classmethod
    def _do_capture(cls, _device, link, path, title, ext=".png"):
        # 设备处于断开状态，不执行截图
        if hasattr(_device, 'test_device_state') and _device.test_device_state != TestDeviceState.ONLINE:
            _device.log.warning("device is offline")
            return '', ''

        if hasattr(_device, "capture"):
            # 截图需要设备对象实现capture方法
            link, path = _device.capture(link, path, ext)
            # 压缩图片为80%
            cls.compress_image(path)
        else:
            _device.log.debug("The device not implement capture function, don't capture!")
        if path and link:
            _device.log.info(
                '<a href="{}" target="_blank">Screenshot: {}'
                '<img style="display: block;" {} title="{}" src="{}"/>'
                '</a>'.format(link, path, cls.resize_image(path), title, link))
        return path, link

    @classmethod
    def __screen_and_save_picture(cls, _device, name, ext=".png", exe_type="takeImage"):
        """
        @summary: 截取设备屏幕图片并保存
        @param  name: 保存的图片名称,通过getTakePicturePath方法获取保存全路径
                ext: 保存图片后缀,支持".png"、".jpg"格式
        """
        path, link = cls.get_image_dir_path(_device, name, ext, exe_type=exe_type)
        # 截图文件后缀在方法内可能发生更改
        return cls._do_capture(_device, link, path, name, ext)

    @classmethod
    def capture_step_picture(cls, file_name, step_name, _device, ext=".png"):
        """截取step步骤图片并保存
        file_name: str, 保存的图片名称
        step_name: str, step步骤名称
        _device  : object, the device object to capture
        ext : str, 保存图片后缀,支持".png"、".jpg"格式
        """
        try:
            path, save_name = cls.get_take_picture_path(_device, file_name, ext, exe_type="stepImage")
            link = os.path.join(DeccVariable.cur_case().name, save_name)
            # 截图文件后缀在方法内可能发生更改
            return cls._do_capture(_device, link, path, step_name, ext)
        except Exception as e:
            log.error(f"take screenshot on step failed, reason: {e}")
        return '', ''

    @classmethod
    def compress_image(cls, img_path, ratio=0.5, quality=80):
        try:
            import cv2
            import numpy as np
            pic = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), -1)
            height, width, deep = pic.shape
            width, height = (width * ratio, height * ratio)
            pic = cv2.resize(pic, (int(width), int(height)))
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            cv2.imencode('.jpeg', pic, params=params)[1].tofile(img_path)
        except (ImportError, NameError):
            pass

    @classmethod
    def get_image_dir_path(cls, _device, name, ext=".png", exe_type="takeImage"):
        """
        增加了 exeType参数，默认为takeImage;可取值:takeImage/dumpWindow
        """
        try:
            if hasattr(_device, "is_oh") or hasattr(_device, "is_mac"):
                phone_time = _device.execute_shell_command("date '+%Y%m%d_%H%M%S'").strip()
            else:
                phone_time = _device.connector.shell("date '+%Y%m%d_%H%M%S'").strip()
        except Exception as exception:
            _device.log.error("get date exception error")
            _device.log.debug("get date exception: {}".format(exception))
        else:
            name = "{}.{}".format(phone_time, name)
        path, save_name = cls.get_take_picture_path(_device, name, ext, exe_type)
        link = os.path.join(DeccVariable.cur_case().name, save_name)
        return path, link

    @classmethod
    def resize_image(cls, file_path, max_height=480, file_type="image"):
        width, height = 1080, 1920
        ratio = 1
        try:
            if os.path.exists(file_path):
                if file_type == "image":
                    from PIL import Image
                    img = Image.open(file_path)
                    width, height = img.width, img.height
                    img.close()
                elif file_type == "video":
                    import cv2
                    try:
                        video_info = cv2.VideoCapture(file_path)
                        width = int(video_info.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(video_info.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        video_info.release()
                    except Exception as e:
                        log.warning("get video width and height error: {}, use default".format(e))
                    if width == 0 or height == 0:
                        width, height = 1080, 1920
            if height < max_height:
                return 'width="%d" height="%d"' % (width, height)
            ratio = max_height / height
        except ImportError:
            log.error("Pillow or opencv-python is not installed ")
        except ZeroDivisionError:
            log.error("shot image height is 0")
        return 'width="%d" height="%d"' % (width * ratio, max_height)

    def terminate(self):
        if self.local_port is not None and isinstance(self.local_port, int):
            if hasattr(self._device, "is_oh") or \
                    self._device.usb_type == DeviceConnectorType.hdc:
                self._device.connector_command('fport rm tcp:{}'.format(self.local_port))
            else:
                self._device.connector_command('forward --remove tcp:{}'.format(self.local_port))
        if self.proc is not None:
            stop_standing_subprocess(self.proc)
        if self.thread is not None:
            start = time.time()
            # 任务结束要等图片生成完
            while self.thread.isAlive() and time.time() - start < 3:
                time.sleep(0.1)
