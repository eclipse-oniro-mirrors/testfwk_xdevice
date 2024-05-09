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

LOCAL_IP = "127.0.0.1"
LOCAL_PORT = 6001
URL = "/"
FORWARD_PORT = 9501
SCREENRECORDER_COMMAND = "aa {} -b com.huawei.ohos.screenrecorder -a com.huawei.ohos.screenrecorder.ServiceExtAbility"


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
    def _do_capture(cls, _device, link, path, ext=".png"):
        if hasattr(_device, "is_oh"):
            remote = "/data/local/tmp/xdevice_screenshot{}".format(ext)
            new_ext = ".jpeg"
            link = link[:link.rfind(ext)] + new_ext
            path = path[:path.rfind(ext)] + new_ext
            remote = remote[:remote.rfind(ext)] + new_ext
            _device.execute_shell_command(
                "snapshot_display -f {}".format(remote), timeout=60000)
            # 适配非root
            if hasattr(_device, "is_root") and not getattr(_device, "is_root", False):
                time.sleep(1)
            _device.pull_file(remote, path)
            _device.execute_shell_command("rm -f {}".format(remote))
        else:
            remote = "/data/local/tmp/screen.png"
            _device.connector.shell("screencap -p {}".format(remote), timeout=60000)
            _device.pull_file(remote, path, timeout=30000)
            _device.execute_shell_command("rm -f {}".format(remote))
            try:
                # 压缩图片为80%
                cls.compress_image(path)
            except NameError:
                pass
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
        path, link = cls._do_capture(_device, link, path, ext)
        _device.log.info(
            '<a href="{}" target="_blank">Screenshot: {}<img style="display: none;" {}/>'
            '</a>'.format(link, path, cls.resize_image(path)))
        return path, link

    @classmethod
    def capture_step_picture(cls, _device, name, ext=".png"):
        """
        @summary: 截取step步骤图片并保存
        @param  name: 保存的图片名称,通过getTakePicturePath方法获取保存全路径
                ext: 保存图片后缀,支持".png"、".jpg"格式
        """
        return None, ""

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
            if hasattr(_device, "is_oh"):
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
        try:
            import cv2
            from PIL import Image
            if os.path.exists(file_path):
                if file_type == "image":
                    img = Image.open(file_path)
                    width, height = img.width, img.height
                    img.close()
                elif file_type == "video":
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
        except ZeroDivisionError:
            log.error("shot image height is 0")
            ratio = 1
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
