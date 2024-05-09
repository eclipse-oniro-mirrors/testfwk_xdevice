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

import datetime
import logging
import os
import sys
import traceback
from xdevice import get_cst_time
from xdevice import platform_logger


class DeviceTestLog:
    _log = platform_logger("DeviceTestLog")

    @classmethod
    def set_log(cls, log_obj):
        if log_obj is not None:
            cls._log = log_obj
            cls.info("INIT DeviceTest Log Successfully.")

    @classmethod
    def error(cls, content, error_no=None, is_traceback=False):
        """
        Only the description information is printed in info mode,
        and detailed error information is printed in debug mode
        """
        error_no = error_no or '00000'
        if is_traceback:
            cls._log.debug(traceback.format_exc())
        cls._log.error(content, error_no=error_no)

    @classmethod
    def warn(cls, content):
        cls._log.warning(content)

    @classmethod
    def warning(cls, content):
        cls._log.warning(content)

    @classmethod
    def info(cls, content):
        cls._log.info(content)

    @classmethod
    def debug(cls, content):
        cls._log.debug(content)

    @classmethod
    def exception(cls, content, error_no=None):
        error_no = error_no or '00000'
        cls._log.exception(content, error_no=error_no)


def create_dir(path):
    """Creates a directory if it does not exist already.
    Args:
        path: The path of the directory to create.
    """
    full_path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(full_path):
        os.makedirs(full_path, exist_ok=True)


def _get_timestamp(time_format, delta=None):
    now_time = get_cst_time()
    if delta:
        now_time = now_time + datetime.timedelta(seconds=delta)
    return now_time.strftime(time_format)[:-3]


def get_log_file_timestamp(delta=None):
    """Returns a timestamp in the format used for log file names.

    Default is current time. If a delta is set, the return value will be
    the current time offset by delta seconds.

    Params:
        delta: Number of seconds to offset from current time; can be negative.

    Returns:
        A timestamp in log filen name format with an offset.
    """
    return _get_timestamp("%m-%d-%Y_%H-%M-%S-%f", delta)


def get_test_logger(log_path, tag, prefix=None, filename=None,
                    is_debug=False):
    """Returns a logger object used for tests.

    The logger object has a stream handler and a file handler. The stream
    handler logs INFO level to the terminal, the file handler logs DEBUG
    level to files.

    Params:
        log_path: Location of the log file.
        TAG: Name of the logger's owner.
        prefix: A prefix for each log line in terminal.
        filename: Name of the log file. The default is the time the logger
            is requested.

    Returns:
        A logger configured with one stream handler and one file handler
    """
    log = logging.getLogger(tag)
    if log.handlers:
        return log
    log.propagate = False

    if not is_debug:
        log.setLevel(logging.INFO)
    else:
        log.setLevel(logging.DEBUG)
    # Log info to stream
    log_line_format = "%(asctime)s.%(msecs).03d %(threadName)s-%(" \
                      "thread)d %(levelname)s %(message)s"
    log_line_time_format = "%Y-%m-%d %H:%M:%S"
    terminal_format = log_line_format
    if prefix:
        terminal_format = "[{}] {}".format(prefix, log_line_format)
    c_formatter = logging.Formatter(terminal_format, log_line_time_format)
    ch_value = ConsoleHandler()
    ch_value.setFormatter(c_formatter)
    if not is_debug:
        ch_value.setLevel(logging.INFO)
    else:
        ch_value.setLevel(logging.DEBUG)

    # Log everything to file
    f_formatter = logging.Formatter(log_line_format, log_line_time_format)
    # All the logs of this test class go into one directory
    if filename is None:
        filename = get_log_file_timestamp()
    if tag == "xDevice":
        create_dir(log_path)
        fh_vaule = logging.FileHandler(
            os.path.join(log_path, filename), encoding="utf-8")
    else:
        log_path = os.path.join(log_path, filename)
        create_dir(log_path)
        fh_vaule = logging.FileHandler(
            os.path.join(log_path, 'test_run_details.log'), encoding="utf-8")
    fh_vaule.setFormatter(f_formatter)
    if not is_debug:
        fh_vaule.setLevel(logging.INFO)
    else:
        fh_vaule.setLevel(logging.DEBUG)
    log.addHandler(fh_vaule)
    log.addHandler(ch_value)
    return log


def kill_test_logger(_logger):
    """Cleans up a test logger object created by get_test_logger.

    Params:
        logger: The logging object to clean up.
    """
    for h_value in list(_logger.handlers):
        _logger.removeHandler(h_value)
        if isinstance(h_value, logging.FileHandler):
            h_value.close()


def create_latest_log_alias(actual_path):
    """Creates a symlink to the latest test run logs.

    Args:
        actual_path: The source directory where the latest test run's logs are.
    """
    link_path = os.path.join(os.path.dirname(actual_path), "latest")
    if os.path.islink(link_path):
        os.remove(link_path)

    try:
        os.symlink(actual_path, link_path)
    except Exception as error:
        print("xDeviceTest-31 create_latest_log_alias:" + str(error))


def logger(log_path, tag, prefix=None, filename=None, is_debug=False):
    """Returns a logger and a reporter of the same name.

    Params:
        log_path: Location of the report file.
        TAG: Name of the logger's owner.
        prefix: A prefix for each log line in terminal.
        filename: Name of the files. The default is the time the objects
            are requested.

    Returns:
        A log object and a reporter object.
    """
    if filename is None:
        filename = get_log_file_timestamp()
    create_dir(log_path)
    create_latest_log_alias(log_path)
    get_logger = get_test_logger(log_path, tag, prefix, filename,
                                 is_debug=is_debug)
    return get_logger, filename


def get_log_line_timestamp(delta=None):
    """
    Get a timestamp in the format used by log lines.
    Default is current time. If a delta is set, the return value will be
    the current time offset by delta seconds.
    """
    return _get_timestamp("%Y-%m-%d %H:%M:%S.%f", delta)


class ConsoleHandler(logging.Handler):
    """
    A handler class which writes logging records, appropriately formatted,
    to a stream. Note that this class does not close the stream, as
    sys.stdout or sys.stderr may be used.
    """

    terminator = '\n'

    def __init__(self, stream=None):
        """
        Initialize the handler.
        """
        super().__init__()
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.stream = stream if stream is not None else sys.stderr

    def flush(self):

        self.acquire()
        try:
            if self.stream:
                if hasattr(self.stream, "flush"):
                    self.stream.flush()
        finally:
            self.release()

    def emit(self, emit_record):

        try:
            msg = self.format(emit_record)
            if emit_record.levelno > logging.INFO:
                self.stream = self.stderr
            else:
                self.stream = self.stdout

            self.stream.write(msg)
            self.stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(emit_record)


"""
兼容release2脚本需要
"""


def print_info(msg):
    DeviceTestLog._log.info(msg)


def print_error(msg):
    DeviceTestLog._log.error(msg)


def print_debug(msg):
    DeviceTestLog._log.debug(msg)


def print_warn(msg):
    DeviceTestLog._log.warning(msg)


def print_trace():
    DeviceTestLog._log.error("".join(
        traceback.format_exception(*sys.exc_info())))
