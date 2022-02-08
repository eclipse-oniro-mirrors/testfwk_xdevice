#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2021 Huawei Device Co., Ltd.
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

import argparse
import os
import platform
import signal
import sys
import threading

from _core.config.config_manager import UserConfigManager
from _core.constants import SchedulerType
from _core.constants import ConfigConst
from _core.constants import ModeType
from _core.constants import ToolCommandType
from _core.environment.manager_env import EnvironmentManager
from _core.exception import ParamError
from _core.exception import ExecuteTerminate
from _core.executor.request import Task
from _core.executor.scheduler import Scheduler
from _core.logger import platform_logger
from _core.plugin import Plugin
from _core.plugin import get_plugin
from _core.utils import SplicingAction
from _core.utils import get_instance_name
from _core.report.result_reporter import ResultReporter

__all__ = ["Console"]

LOG = platform_logger("Console")
try:
    if platform.system() != 'Windows':
        import readline
except (ModuleNotFoundError, ImportError):
    LOG.warning("readline module is not exist.")


class Console(object):
    """
    Class representing an console for executing test.
    Main xDevice console providing user with the interface to interact
    """
    __instance = None

    def __new__(cls, *args, **kwargs):
        """
        Singleton instance
        """
        if cls.__instance is None:
            cls.__instance = super(Console, cls).__new__(cls, *args, **kwargs)
        return cls.__instance

    def __init__(self):
        pass

    @classmethod
    def handler_terminate_signal(cls, signalnum, frame):
        # ctrl+c
        del signalnum, frame
        if not Scheduler.is_execute:
            return
        LOG.info("get terminate input")
        terminate_thread = threading.Thread(
            target=Scheduler.terminate_cmd_exec)
        terminate_thread.setDaemon(True)
        terminate_thread.start()

    def console(self, args):
        """
        Main xDevice console providing user with the interface to interact
        """
        if sys.version_info.major < '3' or sys.version_info.minor < '7':
            LOG.error("Please use python 3.7 or higher version to "
                      "start project")
            sys.exit(0)

        if args is None or len(args) < 2:
            # init environment manager
            EnvironmentManager()
            # Enter xDevice console
            self._console()
        else:
            # init environment manager
            EnvironmentManager()
            # Enter xDevice command parser
            self.command_parser(" ".join(args[1:]))

    def _console(self):
        # Enter xDevice console
        signal.signal(signal.SIGINT, self.handler_terminate_signal)

        while True:
            try:
                usr_input = input(">>> ")
                if usr_input == "":
                    continue

                self.command_parser(usr_input)

            except SystemExit:
                LOG.info("Program exit normally!")
                break
            except ExecuteTerminate:
                LOG.info("execution terminated")
            except (IOError, EOFError, KeyboardInterrupt) as error:
                LOG.exception("Input Error: {}".format(error),
                              exc_info=False)

    def argument_parser(self, para_list):
        """
        argument parser
        """
        options = None
        unparsed = []
        valid_param = True
        parser = None

        try:
            parser = argparse.ArgumentParser(
                description="Specify tests to run.")
            group = parser.add_mutually_exclusive_group()
            parser.add_argument("action",
                                type=str.lower,
                                help="Specify action")
            parser.add_argument("task",
                                type=str,
                                default=None,
                                help="Specify task name")
            group.add_argument("-l", "--testlist",
                               action=SplicingAction,
                               type=str,
                               nargs='+',
                               dest=ConfigConst.testlist,
                               default="",
                               help="Specify test list"
                               )
            group.add_argument("-tf", "--testfile",
                               action=SplicingAction,
                               type=str,
                               nargs='+',
                               dest=ConfigConst.testfile,
                               default="",
                               help="Specify test list file"
                               )
            parser.add_argument("-tc", "--testcase",
                                action="store",
                                type=str,
                                dest=ConfigConst.testcase,
                                default="",
                                help="Specify test case"
                                )
            parser.add_argument("-c", "--config",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.configfile,
                                default="",
                                help="Specify config file path"
                                )
            parser.add_argument("-sn", "--device_sn",
                                action="store",
                                type=str,
                                dest=ConfigConst.device_sn,
                                default="",
                                help="Specify device serial number"
                                )
            parser.add_argument("-rp", "--reportpath",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.report_path,
                                default="",
                                help="Specify test report path"
                                )
            parser.add_argument("-respath", "--resourcepath",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.resource_path,
                                default="",
                                help="Specify test resource path"
                                )
            parser.add_argument("-tcpath", "--testcasespath",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.testcases_path,
                                default="",
                                help="Specify testcases path"
                                )
            parser.add_argument("-ta", "--testargs",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.testargs,
                                default={},
                                help="Specify test arguments"
                                )
            parser.add_argument("-pt", "--passthrough",
                                action="store_true",
                                dest=ConfigConst.pass_through,
                                help="Pass through test arguments"
                                )
            parser.add_argument("-env", "--environment",
                                action=SplicingAction,
                                type=str,
                                nargs='+',
                                dest=ConfigConst.test_environment,
                                default="",
                                help="Specify test environment"
                                )
            parser.add_argument("-e", "--exectype",
                                action="store",
                                type=str,
                                dest=ConfigConst.exectype,
                                default="device",
                                help="Specify test execute type"
                                )
            parser.add_argument("-t", "--testtype",
                                nargs='*',
                                dest=ConfigConst.testtype,
                                default=[],
                                help="Specify test type" +
                                     "(UT,MST,ST,PERF,SEC,RELI,DST,ALL)"
                                )
            parser.add_argument("-td", "--testdriver",
                                action="store",
                                type=str,
                                dest=ConfigConst.testdriver,
                                default="",
                                help="Specify test driver id"
                                )
            parser.add_argument("-tl", "--testlevel",
                                action="store",
                                type=str,
                                dest="testlevel",
                                default="",
                                help="Specify test level"
                                )
            parser.add_argument("-bv", "--build_variant",
                                action="store",
                                type=str,
                                dest="build_variant",
                                default="release",
                                help="Specify build variant(release,debug)"
                                )
            parser.add_argument("-cov", "--coverage",
                                action="store",
                                type=str,
                                dest="coverage",
                                default="",
                                help="Specify coverage"
                                )
            parser.add_argument("--retry",
                                action="store",
                                type=str,
                                dest=ConfigConst.retry,
                                default="",
                                help="Specify retry command"
                                )
            parser.add_argument("--session",
                                action="store",
                                dest=ConfigConst.session,
                                help="retry task by session id")
            parser.add_argument("--dryrun",
                                action="store_true",
                                dest=ConfigConst.dry_run,
                                help="show retry test case list")
            parser.add_argument("--reboot-per-module",
                                action="store_true",
                                dest=ConfigConst.reboot_per_module,
                                help="reboot devices before executing each "
                                     "module")
            parser.add_argument("--check-device",
                                action="store_true",
                                dest=ConfigConst.check_device,
                                help="check the test device meets the "
                                     "requirements")
            parser.add_argument("--repeat",
                                type=int,
                                default=0,
                                dest=ConfigConst.repeat,
                                help="number of times that a task is executed"
                                     " repeatedly")
            self._params_pre_processing(para_list)
            (options, unparsed) = parser.parse_known_args(para_list)
            if unparsed:
                LOG.warning("unparsed input: %s", " ".join(unparsed))
            self._params_post_processing(options)

        except SystemExit:
            valid_param = False
            parser.print_help()
            LOG.warning("Parameter parsing systemexit exception.")
        return options, unparsed, valid_param, parser

    @classmethod
    def _params_pre_processing(cls, para_list):
        if len(para_list) <= 1 or (
                len(para_list) > 1 and "-" in str(para_list[1])):
            para_list.insert(1, Task.EMPTY_TASK)
        for index, param in enumerate(para_list):
            if param == "--retry":
                if index + 1 == len(para_list):
                    para_list.append("retry_previous_command")
                elif "-" in str(para_list[index + 1]):
                    para_list.insert(index + 1, "retry_previous_command")
            elif param == "-->":
                para_list[index] = "!%s" % param

    def _params_post_processing(self, options):
        # params post-processing
        if options.task == Task.EMPTY_TASK:
            setattr(options, ConfigConst.task, "")
        if options.testargs:
            if not options.pass_through:
                test_args = self._parse_combination_param(options.testargs)
                setattr(options, ConfigConst.testargs, test_args)
            else:
                setattr(options, ConfigConst.testargs, {
                    ConfigConst.pass_through: options.testargs})
        if not options.resource_path:
            resource_path = UserConfigManager(
                config_file=options.config, env=options.test_environment).\
                get_resource_path()
            setattr(options, ConfigConst.resource_path, resource_path)
        if not options.testcases_path:
            testcases_path = UserConfigManager(
                config_file=options.config, env=options.test_environment).\
                get_testcases_dir()
            setattr(options, ConfigConst.testcases_path, testcases_path)

    def command_parser(self, args):
        try:
            Scheduler.command_queue.append(args)
            LOG.info("Input command: {}".format(args))
            para_list = args.split()
            (options, _, valid_param, parser) = self.argument_parser(
                para_list)
            if options is None or not valid_param:
                LOG.warning("options is None.")
                return None
            if options.action == ToolCommandType.toolcmd_key_run and \
                    options.retry:
                options = self._get_retry_options(options)
                if options.dry_run:
                    history_report_path = getattr(options,
                                                  "history_report_path", "")
                    self._list_retry_case(history_report_path)
                    return
            else:
                from xdevice import SuiteReporter
                SuiteReporter.clear_failed_case_list()
                SuiteReporter.clear_report_result()

            command = options.action
            if command == "":
                LOG.info("command is empty.")
                return

            self._process_command(command, options, para_list, parser)
        except (ParamError, ValueError, TypeError, SyntaxError,
                AttributeError) as exception:
            error_no = getattr(exception, "error_no", "00000")
            LOG.exception("%s: %s" % (get_instance_name(exception), exception),
                          exc_info=False, error_no=error_no)
            if Scheduler.upload_address:
                Scheduler.upload_unavailable_result(str(exception.args))
                Scheduler.upload_report_end()
        finally:
            if isinstance(Scheduler.command_queue[-1], str):
                Scheduler.command_queue.pop()

    def _process_command(self, command, options, para_list, parser):
        if command.startswith(ToolCommandType.toolcmd_key_help):
            self._process_command_help(parser, para_list)
        elif command.startswith(ToolCommandType.toolcmd_key_show):
            self._process_command_show(para_list)
        elif command.startswith(ToolCommandType.toolcmd_key_run):
            self._process_command_run(command, options)
        elif command.startswith(ToolCommandType.toolcmd_key_quit):
            self._process_command_quit(command)
        elif command.startswith(ToolCommandType.toolcmd_key_list):
            self._process_command_list(command, para_list)
        else:
            LOG.error("unsupported command action", error_no="00100",
                      action=command)

    def _get_retry_options(self, options):
        # get history command, history report path
        history_command, history_report_path = self._parse_retry_option(
            options)
        input_report_path = options.report_path
        LOG.info("History command: %s", history_command)
        if not os.path.exists(history_report_path) and \
                Scheduler.mode != ModeType.decc:
            raise ParamError(
                "history report path %s not exists" % history_report_path)

        # parse history command, set history report path
        is_dry_run = True if options.dry_run else False

        # clear the content about repeat count in history command
        if "--repeat" in history_command:
            split_list = list(history_command.split())
            if "--repeat" in split_list:
                pos = split_list.index("--repeat")
                split_list = split_list[:pos] + split_list[pos+2:]
                history_command = " ".join(split_list)

        (options, _, _, _) = self.argument_parser(history_command.split())
        options.dry_run = is_dry_run
        setattr(options, "history_report_path", history_report_path)

        # modify history_command -rp param
        history_command = self._parse_rp_option(
            history_command, input_report_path, options)

        # add history command to Scheduler.command_queue
        LOG.info("Retry command: %s", history_command)
        Scheduler.command_queue[-1] = history_command
        return options

    @classmethod
    def _parse_rp_option(cls, history_command, input_report_path,
                         options):
        if options.report_path:
            if input_report_path:
                history_command = history_command.replace(
                    options.report_path, input_report_path)
                setattr(options, "report_path", input_report_path)
            else:
                history_command = history_command.replace(
                    options.report_path, "").replace("-rp", "").replace(
                    "--reportpath", "")
                setattr(options, "report_path", "")
        else:
            if input_report_path:
                history_command = "{}{}".format(history_command,
                                                " -rp %s" % input_report_path)
                setattr(options, "report_path", input_report_path)
        return history_command.strip()

    @classmethod
    def _process_command_help(cls, parser, para_list):
        if para_list[0] == ToolCommandType.toolcmd_key_help:
            if len(para_list) == 2:
                cls.display_help_command_info(para_list[1])
            else:
                parser.print_help()
        else:
            LOG.error("Wrong help command. Use 'help' to print help")
        return

    @classmethod
    def _process_command_show(cls, para_list):
        if para_list[0] == ToolCommandType.toolcmd_key_show:
            pass
        else:
            LOG.error("Wrong show command.")
        return

    @classmethod
    def _process_command_run(cls, command, options):

        scheduler = get_plugin(plugin_type=Plugin.SCHEDULER,
                               plugin_id=SchedulerType.scheduler)[0]
        if scheduler is None:
            LOG.error("Can not find the scheduler plugin.")
        else:
            scheduler.exec_command(command, options)

        return

    def _process_command_list(self, command, para_list):
        if command != ToolCommandType.toolcmd_key_list:
            LOG.error("Wrong list command.")
            return
        if len(para_list) > 1:
            if para_list[1] == "history":
                self._list_history()
            elif para_list[1] == "devices" or para_list[1] == Task.EMPTY_TASK:
                env_manager = EnvironmentManager()
                env_manager.list_devices()
            else:
                self._list_task_id(para_list[1])
            return
        # list devices
        env_manager = EnvironmentManager()
        env_manager.list_devices()
        return

    @classmethod
    def _process_command_quit(cls, command):
        if command == ToolCommandType.toolcmd_key_quit:
            env_manager = EnvironmentManager()
            env_manager.env_stop()
            sys.exit(0)
        else:
            LOG.error("Wrong exit command. Use 'quit' to quit program")
        return

    @staticmethod
    def _parse_combination_param(combination_value):
        # sample: size:xxx1;exclude-annotation:xxx
        parse_result = {}
        key_value_pairs = str(combination_value).split(";")
        for key_value_pair in key_value_pairs:
            key, value = key_value_pair.split(":", 1)
            if not value:
                raise ParamError("'%s' no value" % key)
            value_list = str(value).split(",")
            exist_list = parse_result.get(key, [])
            exist_list.extend(value_list)
            parse_result[key] = exist_list
        return parse_result

    @classmethod
    def _list_history(cls):
        print("Command history:")
        print("{0:<16}{1:<50}{2:<50}".format(
            "TaskId", "Command", "ReportPath"))
        for command_info in Scheduler.command_queue[:-1]:
            command, report_path = command_info[1], command_info[2]
            if len(command) > 49:
                command = "%s..." % command[:46]
            if len(report_path) > 49:
                report_path = "%s..." % report_path[:46]
            print("{0:<16}{1:<50}{2:<50}".format(
                command_info[0], command, report_path))

    @classmethod
    def _list_task_id(cls, task_id):
        print("List task:")
        task_id, command, report_path = task_id, "", ""
        for command_info in Scheduler.command_queue[:-1]:
            if command_info[0] != task_id:
                continue
            task_id, command, report_path = command_info
            break
        print("{0:<16}{1:<100}".format("TaskId:", task_id))
        print("{0:<16}{1:<100}".format("Command:", command))
        print("{0:<16}{1:<100}".format("ReportPath:", report_path))

    @classmethod
    def _list_retry_case(cls, history_path):
        params = ResultReporter.get_task_info_params(history_path)
        if not params:
            raise ParamError("no retry case exists")
        session_id, command, report_path, failed_list = \
            params[0], params[1], params[2], \
            [(module, failed) for module, case_list in params[3].items()
             for failed in case_list]
        if Scheduler.mode == ModeType.decc:
            from xdevice import SuiteReporter
            SuiteReporter.failed_case_list = failed_list
            return

        # draw tables in console
        left, middle, right = 23, 49, 49
        two_segments = "{0:-<%s}{1:-<%s}+" % (left, middle + right)
        two_rows = "|{0:^%s}|{1:^%s}|" % (left - 1, middle + right - 1)

        three_segments = "{0:-<%s}{1:-<%s}{2:-<%s}+" % (left, middle, right)
        three_rows = "|{0:^%s}|{1:^%s}|{2:^%s}|" % \
                     (left - 1, middle - 1, right - 1)
        if len(session_id) > middle + right - 1:
            session_id = "%s..." % session_id[:middle + right - 4]
        if len(command) > middle + right - 1:
            command = "%s..." % command[:middle + right - 4]
        if len(report_path) > middle + right - 1:
            report_path = "%s..." % report_path[:middle + right - 4]

        print(two_segments.format("+", '+'))
        print(two_rows.format("SessionId", session_id))
        print(two_rows.format("Command", command))
        print(two_rows.format("ReportPath", report_path))

        print(three_segments.format("+", '+', '+'))
        print(three_rows.format("Module", "Testsuite", "Testcase"))
        print(three_segments.format("+", '+', '+'))
        for module, failed in failed_list:
            # all module is failed
            if "#" not in failed:
                class_name = "-"
                test = "-"
            # others, get failed cases info
            else:
                pos = failed.rfind("#")
                class_name = failed[:pos]
                test = failed[pos + 1:]
            if len(module) > left - 1:
                module = "%s..." % module[:left - 4]
            if len(class_name) > middle - 1:
                class_name = "%s..." % class_name[:middle - 4]
            if len(test) > right - 1:
                test = "%s..." % test[:right - 4]
            print(three_rows.format(module, class_name, test))
        print(three_segments.format("+", '+', '+'))

    @classmethod
    def _find_history_path(cls, session):
        from xdevice import Variables
        if os.path.isdir(session):
            return session

        target_path = os.path.join(
            Variables.exec_dir, Variables.report_vars.report_dir, session)
        if not os.path.isdir(target_path):
            raise ParamError("session '%s' is invalid!" % session)

        return target_path

    def _parse_retry_option(self, options):
        if Scheduler.mode == ModeType.decc:
            if len(Scheduler.command_queue) < 2:
                raise ParamError("no previous command executed")
            _, history_command, history_report_path = \
                Scheduler.command_queue[-2]
            return history_command, history_report_path

        # get history_command, history_report_path
        if options.retry == "retry_previous_command":
            from xdevice import Variables
            history_path = os.path.join(
                Variables.exec_dir, Variables.report_vars.report_dir, "latest")
            if options.session:
                history_path = self._find_history_path(options.session)

            params = ResultReporter.get_task_info_params(history_path)
            if not params:
                error_msg = "no previous command executed" if not \
                    options.session else "'%s' has no command executed" % \
                                         options.session
                raise ParamError(error_msg)
            history_command, history_report_path = params[1], params[2]
        else:
            history_command, history_report_path = "", ""
            for command_tuple in Scheduler.command_queue[:-1]:
                if command_tuple[0] != options.retry:
                    continue
                history_command, history_report_path = \
                    command_tuple[1], command_tuple[2]
                break
            if not history_command:
                raise ParamError("wrong task id input: %s" % options.retry)
        return history_command, history_report_path

    @classmethod
    def display_help_command_info(cls, command):
        if command == ToolCommandType.toolcmd_key_run:
            print(RUN_INFORMATION)
        elif command == ToolCommandType.toolcmd_key_list:
            print(LIST_INFORMATION)
        elif command == "empty":
            print(GUIDE_INFORMATION)
        else:
            print("'%s' command no help information." % command)


RUN_INFORMATION = """run:
    This command is used to execute the selected testcases.
    It includes a series of processes such as use case compilation, \
execution, and result collection.

usage: run [-l TESTLIST [TESTLIST ...] | -tf TESTFILE
           [TESTFILE ...]] [-tc TESTCASE] [-c CONFIG] [-sn DEVICE_SN]
           [-rp REPORT_PATH [REPORT_PATH ...]]
           [-respath RESOURCE_PATH [RESOURCE_PATH ...]]
           [-tcpath TESTCASES_PATH [TESTCASES_PATH ...]]
           [-ta TESTARGS [TESTARGS ...]] [-pt]
           [-env TEST_ENVIRONMENT [TEST_ENVIRONMENT ...]]
           [-e EXECTYPE] [-t [TESTTYPE [TESTTYPE ...]]]
           [-td TESTDRIVER] [-tl TESTLEVEL] [-bv BUILD_VARIANT]
           [-cov COVERAGE] [--retry RETRY] [--session SESSION]
           [--dryrun] [--reboot-per-module] [--check-device]
           [--repeat REPEAT]
           action task

Specify tests to run.

positional arguments:
  action                Specify action
  task                  Specify task name,such as "ssts", "acts", "hits"

optional arguments:
    -h, --help            show this help message and exit
    -l TESTLIST [TESTLIST ...], --testlist TESTLIST [TESTLIST ...]
                        Specify test list
    -tf TESTFILE [TESTFILE ...], --testfile TESTFILE [TESTFILE ...]
                        Specify test list file
    -tc TESTCASE, --testcase TESTCASE
                        Specify test case
    -c CONFIG, --config CONFIG
                        Specify config file path
    -sn DEVICE_SN, --device_sn DEVICE_SN
                        Specify device serial number
    -rp REPORT_PATH [REPORT_PATH ...], --reportpath REPORT_PATH [REPORT_PATH \
...]
                        Specify test report path
    -respath RESOURCE_PATH [RESOURCE_PATH ...], --resourcepath RESOURCE_PATH \
[RESOURCE_PATH ...]
                        Specify test resource path
    -tcpath TESTCASES_PATH [TESTCASES_PATH ...], --testcasespath \
TESTCASES_PATH [TESTCASES_PATH ...]
                        Specify testcases path
    -ta TESTARGS [TESTARGS ...], --testargs TESTARGS [TESTARGS ...]
                        Specify test arguments
    -pt, --passthrough    Pass through test arguments
    -env TEST_ENVIRONMENT [TEST_ENVIRONMENT ...], --environment \
TEST_ENVIRONMENT [TEST_ENVIRONMENT ...]
                        Specify test environment
    -e EXECTYPE, --exectype EXECTYPE
                        Specify test execute type
    -t [TESTTYPE [TESTTYPE ...]], --testtype [TESTTYPE [TESTTYPE ...]]
                        Specify test type(UT,MST,ST,PERF,SEC,RELI,DST,ALL)
    -td TESTDRIVER, --testdriver TESTDRIVER
                        Specify test driver id
    -tl TESTLEVEL, --testlevel TESTLEVEL
                        Specify test level
    -bv BUILD_VARIANT, --build_variant BUILD_VARIANT
                        Specify build variant(release,debug)
    -cov COVERAGE, --coverage COVERAGE
                        Specify coverage
    --retry RETRY         Specify retry command
    --session SESSION     retry task by session id
    --dryrun              show retry test case list
    --reboot-per-module   reboot devices before executing each module
    --check-device        check the test device meets the requirements
    --repeat REPEAT       number of times that a task is executed repeatedly

Examples:
    run -l <module name>;<module name>
    run -tf test/resource/<test file name>.txt 
    
    run –l <module name> -sn <device serial number>;<device serial number>
    run –l <module name> -respath <path of resource>
    run –l <module name> -ta size:large
    run –l <module name> –ta class:<package>#<class>#<method>
    run –l <module name> -ta size:large -pt
    run –l <module name> –env <the content string of user_config.xml>
    run –l <module name> –e device 
    run –l <module name> –t ALL
    run –l <module name> –td CppTest
    run –l <module name> -tcpath resource/testcases
    
    run ssts
    run ssts –tc <python script name>;<python script name>
    run ssts -sn <device serial number>;<device serial number>
    run ssts -respath <path of resource>
    ... ...   
    
    run acts
    run acts –tc <python script name>;<python script name>
    run acts -sn <device serial number>;<device serial number>
    run acts -respath <path of resource>
    ... ...
    
    run hits
    ... ...
    
    run --retry
    run --retry --session <report folder name>
    run --retry --dryrun
"""

LIST_INFORMATION = "list:" + """
    This command is used to display device list and task record.\n
usage: 
    list 
    list history
    list <id>
       
Introduction:
    list:         display device list 
    list history: display history record of a serial of tasks
    list <id>:    display history record about task what contains specific id

Examples:
    list
    list history
    list 6e****90
"""


GUIDE_INFORMATION = """help:
    use help to get  information.
    
usage:
    run:  Display a list of supported run command.
    list: Display a list of supported device and task record.

Examples:
    help run 
    help list
"""
