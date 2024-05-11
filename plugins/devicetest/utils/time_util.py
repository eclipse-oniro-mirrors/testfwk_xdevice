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


from datetime import datetime
from inspect import stack
import json
import os
import time
from xdevice import get_cst_time


class TS():
    '''
    performace test class
    '''
    inner_stack = stack()
    total = 0
    times = 0

    @staticmethod
    def start():
        try:
            TS.inner_stack.append(time.time())
        except Exception:
            from devicetest.log.logger import DeviceTestLog as log
            log.error("start TS exception.", is_traceback=True)

    @staticmethod
    def average(prefix=''):
        if TS.times == 0:
            TS.times = 1
        return ("%s ==> average: %.3f ms" % (prefix, TS.total / TS.times))

    @staticmethod
    def stop(prefix=''):
        try:
            if len(TS.inner_stack) > 0:
                cur_time = (time.time() - TS.inner_stack.pop()) * 1000
                TS.total += cur_time
                TS.times += 1
                return cur_time
            return None
        except Exception:
            from devicetest.log.logger import DeviceTestLog as log
            log.error("stop TS exception.", is_traceback=True)
            return None


class TimeHandler:

    @classmethod
    def get_formated_datetime(cls, time_value=None):
        """
        get formated datetime that only contains year month day hour minute
        and second information

        Obtains the datetime object, which contains only the year, month,
        day, hour, minute, and second information.
        Args:
            time_value: Time to be processed. If the time does not exist,
                        the current time is used.
        Returns:
            Datetime object that has been processed. The object can be
            converted to a character string, The value is in the format of
            2011-12-15 16:08:35.
        """
        if time_value is None:
            time_value = time.time()
        return datetime(*(time.localtime(time_value)[:6]))

    @classmethod
    def get_formated_datetime_name(cls, time_val=None):
        """
        get formated datetime used to generate a file that only contains
        year month day hour minute and second information

        Obtains the current character string that contains only time
        information and underscores.
        Args:
            time_val: Time to be processed. If the time does not exist,
                        the current time is used.
        Returns:
            The value is a character string in the format of
            2011_12_15_16_08_35
        """
        result_list = []
        for _str in cls.get_formated_datetime(time_val).timetuple()[:6]:
            result_list.append(str("%02d" % _str))
        return "_".join(result_list)

    @classmethod
    def convert_formated_name(cls, convert_time,
                              formate="%Y-%m-%d %H:%M:%S.%f"):
        """
        Args:
            convert_time: Time value to be processed
        Returns: 1460907045 Format
        """
        strpt_time = time.strptime(convert_time, formate)
        return int(time.mktime(strpt_time))

    @classmethod
    def get_now_datetime(cls, time_format="%Y%m%d%H%M%S%f"):
        """
        Args:
            time_format: Obtain the time format, for example,
                        f="%Y-%m-%d %H:%M:%S.%f",
            The time in 2017-04-25 11:26:33.293963 format is returned.
        Returns: String
        """
        return get_cst_time().strftime(time_format)

    @classmethod
    def get_timeout_value(cls):
        project_path = \
            os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        config = os.path.join(project_path, "project.config")
        with open(config, 'r', encoding='utf-8') as f_time:
            conf = json.load(f_time)
            get_case_time = conf.get("caseTimeOut", 60 * 60 * 1)
            return get_case_time

    @classmethod
    def get_formated_time(cls, time_format='%Y-%m-%d %H:%M:%S'):
        """
        get current time, for example: 2020-08-04 15:48:04
        :param time_format: time format
        :return: current time
        """
        return get_cst_time().strftime(time_format)

    @classmethod
    def get_interval_timestamp(cls, start_format_time, end_format_time,
                               time_format='%Y-%m-%d %H:%M:%S'):
        try:
            start_timestamp = datetime.strptime(
                start_format_time, time_format).timestamp()
            end_timestamp = datetime.strptime(
                end_format_time, time_format).timestamp()
            interval_timestamp = round(end_timestamp - start_timestamp, 3)
            return interval_timestamp
        except Exception:
            return 0.00

    @staticmethod
    def get_current_epoch_time():
        """Current epoch time in milliseconds.
        Returns:
            An integer representing the current epoch time in milliseconds.
        """
        return int(round(time.time() * 1000))

    @staticmethod
    def get_current_human_time():
        """Returns the current time in human readable format.
        Returns:
            The current time stamp in Month-Day-Year Hour:Min:Sec format.
        """
        return time.strftime("%m-%d-%Y %H:%M:%S ")