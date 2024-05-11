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

import codecs
import os
import shutil
import stat
import sys
import time

from devicetest.core.error_message import ErrorMessage
from devicetest.core.exception import DeviceTestError
from devicetest.core.variables import get_project_path
from devicetest.log.logger import DeviceTestLog as log


def get_template_path(template_file_path, isdir=None):
    '''
    @summary: Obtains the absolute path of the template screen cap path.
    @param isdir: Obtain the directory: True; Obtain the file: False;
                  None: Ignore the file type
    '''
    template_file_path = template_file_path.replace("\\", "/")
    if os.path.isabs(template_file_path) \
            and (not isdir and os.path.isfile(template_file_path)):
        return os.path.abspath(template_file_path)

    # remove first str '/'
    if not os.path.isfile(template_file_path) and template_file_path.startswith("/"):
        template_file_path = template_file_path[1:]

    _fol = None
    if template_file_path.startswith("resource"):
        path = template_file_path[9:]
        from xdevice import EnvPool
        if EnvPool.resource_path is not None:
            folder = os.path.abspath(EnvPool.resource_path)
            _fol = travesal_folder(folder, path, isdir)
            if _fol is None:
                log.debug("Not found [%s] in env pool path %s, "
                          "continue to find template in resource path." % (
                              path, folder))
        if _fol is None:
            ecotest_resource_path = getattr(sys, "ecotest_resource_path", "")
            if ecotest_resource_path is not None:
                folder = os.path.abspath(ecotest_resource_path)
                _fol = travesal_folder(folder, path, isdir)
                if _fol is None:
                    log.debug("Not found [%s] in resource path %s, "
                              "continue to find template in other path." % (
                                  path, folder))
    else:
        _fol = get_resource_path(template_file_path)
    log.debug("get template path:{}".format(_fol))
    return _fol


def get_resource_path(resource_file_path, isdir=None):
    '''
    @summary: Obtains the absolute path of the resource file.
    @param isdir: Obtain the directory: True; Obtain the file: False;
                  None: Ignore the file type
    '''
    resource_file_path = resource_file_path.replace("\\", "/")
    if os.path.isabs(resource_file_path) \
            and ((isdir is None and os.path.exists(resource_file_path))
                 or (not isdir and os.path.isfile(resource_file_path))
                 or (isdir and os.path.isdir(resource_file_path))):
        return os.path.abspath(resource_file_path)

    _fol = None
    from xdevice import EnvPool
    if EnvPool.resource_path is not None:
        folder = os.path.abspath(EnvPool.resource_path)
        _fol = travesal_folder(folder, resource_file_path, isdir)
        if _fol is None:
            log.debug("Not found [%s] in env pool path %s, "
                      "continue to find in project resource path." % (
                          resource_file_path, folder))

    if _fol is None:
        ecotest_resource_path = getattr(sys, "ecotest_resource_path", "")
        if ecotest_resource_path is not None:
            folder = os.path.abspath(ecotest_resource_path)
            _fol = travesal_folder(folder, resource_file_path, isdir)
            if _fol is None:
                log.debug("Not found [%s] in ecotest path %s, "
                          "continue to find in suit path." % (
                              resource_file_path, folder))

    from devicetest.core.variables import DeccVariable
    if _fol is None:
        folder = os.path.abspath(DeccVariable.project.resource_path)
        _fol = travesal_folder(folder, resource_file_path, isdir)
        if _fol is None:
            log.debug("Not found [%s] in product path %s, "
                      "continue to find in project resource path." % (
                          resource_file_path, folder))

    if _fol is None:
        folder = os.path.abspath(DeccVariable.project.test_suite_path)
        _fol = travesal_folder(folder, resource_file_path, isdir)
        if _fol is None:
            log.debug("Not found [%s] in product path %s, "
                      "continue to find in suit resource path." % (
                          resource_file_path, folder))

    if _fol is None:
        folder = os.path.abspath(get_project_path())
        _fol = travesal_folder(folder, resource_file_path, isdir)
        if _fol is None:
            log.debug("Not found [%s] in product path %s, "
                      "continue to find in project path." % (
                          resource_file_path, folder))

    if _fol is None:
        log.error(ErrorMessage.Error_01102.Message.en,
                  error_no=ErrorMessage.Error_01102.Code)
        raise DeviceTestError(ErrorMessage.Error_01102.Topic)
    log.debug("get resource path:{}".format(_fol))
    return _fol


def travesal_folder(folder, folder_file_path, isdir=False):
    folder_file = os.path.join(folder, folder_file_path)
    if (isdir is None and os.path.exists(folder_file)) \
            or (not isdir and os.path.isfile(folder_file)) \
            or (isdir and os.path.isdir(folder_file)):
        return os.path.abspath(folder_file)

    if not os.path.exists(folder):
        return None

    for child in os.listdir(folder):
        if child == ".svn":
            continue

        folder_file = os.path.join(folder, child)
        if os.path.isdir(folder_file):
            if (isdir is None or isdir) \
                    and folder_file.endswith(os.sep + folder_file_path):
                return folder_file
            else:
                folder_ret = travesal_folder(folder_file,
                                             folder_file_path, isdir)
                if folder_ret is not None:
                    return folder_ret
        elif os.path.isfile(folder_file) \
                and folder_file.endswith(os.sep + folder_file_path) \
                and (isdir is None or not isdir):
            return folder_file

    return None


def os_open_file_write(file_path, content, mode="w"):
    try:
        flags = os.O_WRONLY | os.O_CREAT
        modes = stat.S_IWUSR | stat.S_IRUSR
        dir_path = os.path.dirname(file_path)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)
        with os.fdopen(os.open(file_path, flags, modes), mode) as fout:
            fout.write(content)

    except Exception as error:
        log.error(ErrorMessage.Error_01214.Message.en,
                  error_no=ErrorMessage.Error_01214.Code,
                  is_traceback=True)
        raise DeviceTestError(ErrorMessage.Error_01214.Topic) from error


def os_open_file_read(file_path, mode="r"):
    try:
        flags = os.O_RDONLY
        modes = stat.S_IWUSR | stat.S_IRUSR
        with os.fdopen(os.open(file_path, flags, modes), mode) as fout:
            return fout.read()

    except FileNotFoundError as error:
        log.error(ErrorMessage.Error_01216.Message.en,
                  error_no=ErrorMessage.Error_01216.Code,
                  is_traceback=True)
        raise DeviceTestError(ErrorMessage.Error_01216.Topic) from error

    except Exception as error:
        log.error(ErrorMessage.Error_01215.Message.en,
                  error_no=ErrorMessage.Error_01215.Code,
                  is_traceback=True)
        raise DeviceTestError(ErrorMessage.Error_01215.Topic) from error


def save_file(file_path, content):
    os_open_file_write(file_path, content, "wb")


def create_dir(create_path):
    """
    Creates a directory if it does not exist already.
    Args:
        create_path: The path of the directory to create.
    """
    full_path = os.path.abspath(os.path.expanduser(create_path))
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)  # exist_ok=True 


def to_file_plus(file_path, content, console=False, level="INFO"):
    """
    @summary: Create file, append "content" to file and add timestamp.
    """
    dirname = os.path.dirname(file_path)
    if not os.path.exists(dirname):
        # When the to_file_plus method is invoked in a thread, there is a
        # possibility that the method does not exist when os.path.exists is
        # executed. However, the directory has been created by the main thread
        # during directory creation. Therefore, an exception is captured.
        try:
            os.makedirs(dirname)
        except Exception as exception:
            log.error(exception)
    from devicetest.log.logger import get_log_line_timestamp
    timestamp = get_log_line_timestamp()
    data = "%s %s %s\n" % (timestamp, level, content)
    if console:
        print(data[:-2])
    srw = codecs.open(file_path, "a", "utf-8")
    srw.write(data)
    srw.close()


def to_file(filename, content):
    '''
    genenrate files
    '''
    dirname = os.path.dirname(filename)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    os_open_file_write(filename, content, "wb")


def delfile(filename):
    try:
        os.remove(filename)
    except Exception as exception:
        log.error(exception)
        if os.path.isfile(filename):
            if "nt" in sys.builtin_module_names:
                os.remove(filename)
            else:
                shutil.rmtree(filename)

    for _ in range(5):
        if os.path.isfile(filename):
            time.sleep(0.1)
            continue
        else:
            break

    if os.path.isfile(filename):
        log.error("Delete file %s failed." % filename)


def delfolder(dirname):
    try:
        shutil.rmtree(dirname)
    except Exception as _:
        if os.path.isdir(dirname):
            shutil.rmtree(dirname)

    for _ in range(5):
        if os.path.isdir(dirname):
            time.sleep(0.1)
            continue
        else:
            break

    if os.path.isdir(dirname):
        log.error("Delete folder %s failed." % dirname)


def copy_to_folder(src, des):
    """Copy a folder and its children or a file to another folder.
    """
    src = os.path.normpath(src)
    des = os.path.normpath(des)
    if not os.path.exists(src):
        log.error("No found [%s]" % src)
        return
    if not os.path.exists(des):
        create_dir(des)
    if not os.path.isdir(des):
        log.error("[%s] is not a folder." % des)
        return

    if not os.path.isdir(src):
        shutil.copy(src, des)
        return
    os.chdir(src)
    src_file_list = [os.path.join(src, src_file)
                     for src_file in os.listdir(des)]
    for source in src_file_list:
        if os.path.isfile(source):
            shutil.copy(source, des)
        if os.path.isdir(source):
            _, src_name = os.path.split(source)
            shutil.copytree(source, os.path.join(des, src_name))


def delete_file_folder(src):
    '''
    @summary: Delete files or directories.
    '''

    if os.path.isfile(src):
        delfile(src)
    elif os.path.isdir(src):
        delfolder(src)
