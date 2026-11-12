#!/usr/bin/env python3
# coding=utf-8

#
# Copyright (c) 2020-2023 Huawei Device Co., Ltd.
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

import pkgutil
from abc import ABC, abstractmethod

from _core.constants import SchedulerType
from _core.logger import platform_logger

LOG = platform_logger("Policy")

__all__ = [
    "ISchedulingPolicy",
    "IReportablePolicy",
    "register_policy",
    "create_policy",
]

_POLICY_REGISTRY = {}
_RESERVED_NAMES = ("default", SchedulerType.module, SchedulerType.synchronize)


class ISchedulingPolicy(ABC):
    """Base interface for all scheduling policies.

    A policy has exactly one responsibility: reorder test_drivers.
    Implement only this interface → default test reports only, no extra reports.
    """
    name = ""

    @abstractmethod
    def sort_test_drivers(self, test_drivers):
        """Reorder test_drivers according to this policy's rules and return
        the new list. This is the only method required by the framework.
        """


class IReportablePolicy(ABC):
    """Optional opt-in interface: policies that also produce extra reports.

    Only policies that explicitly implement this interface get an extra
    report generation entry point. Default test reports are always generated
    by the framework's existing pipeline regardless of this interface.
    """

    @abstractmethod
    def generate_reports(self, report_path, task=None):
        """Generate extra reports for this policy. Implementation body should
        stay in the report layer; this method is a delegation entry only.

        Only called from result_reporter._generate_custom_summary_reports.
        Default test report pipeline completes before this is invoked.
        """


def register_policy(name):
    """Class decorator: register a policy class under the given name.

    Reserved names ("default" / "module" / "synchronize") are rejected
    with a warning to avoid conflicting with existing SchedulerType values
    that are already consumed by equal-sign checks elsewhere.
    """
    def decorator(cls):
        if name in _RESERVED_NAMES:
            LOG.warning(
                "Policy name '%s' is reserved; registration skipped", name)
            return cls
        if name in _POLICY_REGISTRY:
            LOG.warning(
                "Policy name '%s' already registered; skipping duplicate", name)
            return cls
        _POLICY_REGISTRY[name] = cls
        cls.name = name
        return cls
    return decorator


def create_policy(name):
    """Factory: instantiate a policy by name. Returns None for unknown names
    so the caller can fall back to FIFO. Instantiation errors (e.g. declaring
    IReportablePolicy without implementing generate_reports → TypeError) are
    caught with a warning and return None, never blocking task execution.
    """
    if not name:
        return None
    cls = _POLICY_REGISTRY.get(name)
    if cls is None:
        return None
    try:
        return cls()
    except Exception as error:
        LOG.warning(
            "Failed to instantiate policy '%s': %s; fallback to FIFO",
            name, error)
        return None


def _autoload_policies():
    """Scan this package for all *_policy.py modules and import them so
    that @register_policy decorators execute. New policy files placed in
    this package are automatically discovered — no manual import needed.
    """
    import importlib
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name.endswith("_policy"):
            try:
                importlib.import_module(
                    ".{}".format(module_name), package=__name__)
            except Exception as error:
                LOG.warning(
                    "Failed to load policy module '%s': %s", module_name, error)


_autoload_policies()
