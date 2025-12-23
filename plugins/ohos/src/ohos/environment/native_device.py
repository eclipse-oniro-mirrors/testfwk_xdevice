import os.path
import shutil
import subprocess

from xdevice import convert_serial
from xdevice import platform_logger
from xdevice import HdcError
from xdevice import TestDeviceState
from xdevice import Variables

from ohos.error import ErrorMessage
from ohos.environment.device import Device
from ohos.constants import ConnectType

TIMEOUT = 300 * 1000

LOG = platform_logger("NativeDevice")


class NativeDevice(Device):
    tmp_path = Variables.temp_dir

    def __init__(self):
        super().__init__()
        self.device_sn = self.get_property_value("ohos.boot.sn") or "NativeDevice"
        self.host = "127.0.0.1"
        self.port = ""
        self.test_device_state = TestDeviceState.ONLINE
        self.label = self.get_device_type()
        self.__class__.__name__ = "Device"

    def set_tmp_path(self, tmp_path: str):
        self.tmp_path = tmp_path

    @property
    def connect_type(self):
        return ConnectType.native

    def execute_shell_command(self, command: str, timeout: int = TIMEOUT, **kwargs):
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        out, err = proc.communicate(timeout=timeout)
        out = out.decode("utf-8", errors="ignore").strip()
        if err:
            LOG.error(err.decode("utf-8", errors="ignore").strip())
        return out

    def execute_shell_cmd_background(self, command: str, timeout: int = TIMEOUT, **kwargs):
        return self.execute_shell_command(command, timeout=timeout, **kwargs)

    @property
    def ui_proxy(self):
        # ui operation agent
        ui_proxy = getattr(self, "_ui_proxy", None)
        if ui_proxy is None:
            from ohos.proxy.ui_proxy import NativeUIProxy
            self._ui_proxy = NativeUIProxy()
            self._ui_proxy.__set_device__(self)
            self._ui_proxy.__init_proxy__()
            self.clean_proxy_function.append(self._ui_proxy.__clean_proxy__)
        return self._ui_proxy.rpc_proxy

    def connector_command(self, command: str, **kwargs):
        command = command.replace("shell", "")
        timeout = int(kwargs.get("timeout", TIMEOUT) / 1000)
        timeout_msg = '' if timeout == 300.0 else \
            " with timeout %ss" % timeout
        LOG.debug("{} execute command {} {}".format(self.device_sn,
                                                    command, timeout_msg))
        result = self.execute_shell_command(command, timeout=timeout)
        if not result:
            return result
        is_print = bool(kwargs.get("is_print", True))
        if is_print:
            for line in str(result).split("\n"):
                if line.strip():
                    LOG.debug(line.strip())
        return result

    def reboot(self):
        LOG.error("do not support reboot")

    def install_package(self, package_path, command=""):
        if package_path is None:
            raise HdcError(ErrorMessage.Device.Code_0303005)
        LOG.info("{} install {}".format(convert_serial(self.device_sn), package_path))
        cmd = "bm install -p {} {}".format(command.strip(), package_path)
        return self.execute_shell_command(cmd)

    def uninstall_package(self, package_name):
        command = "bm uninstall -n {} ".format(package_name)
        LOG.info("{} {}".format(convert_serial(self.device_sn), command))
        return self.execute_shell_command(command)

    def push_file(self, local, remote, **kwargs):
        if local is None:
            raise HdcError(ErrorMessage.Device.Code_0303001)

        remote_is_dir = kwargs.get("remote_is_dir", False)
        if remote_is_dir:
            ret = self.execute_shell_command("test -d {} && echo 0".format(remote))
            if not (ret != "" and len(str(ret).split()) != 0 and
                    str(ret).split()[0] == "0"):
                self.execute_shell_command("mkdir -p {}".format(remote))

        if os.path.isdir(local):
            shutil.copytree(local, remote)
        else:
            shutil.copy2(local, remote)

    def pull_file(self, remote, local, **kwargs):
        if os.path.isdir(remote):
            shutil.copytree(remote, local)
        else:
            shutil.copy2(remote, local)

    def uninstall_app(self, package_name):
        return self.uninstall_package(package_name)

    def install_app(self, package_path, command=""):
        return self.install_package(package_path, command)
