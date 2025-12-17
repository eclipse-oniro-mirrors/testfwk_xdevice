#!/bin/bash
#
# Copyright (C) 2020-2021 Huawei Device Co., Ltd.
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

set -e

BASE_DIR=$(dirname "$0")
PYTHON=python3
TOOLS=tools

if ! command -v "$PYTHON" &> /dev/null; then
    echo "Python3.7 or higher version required!"
    exit 1
fi

if ! $PYTHON -c "import sys; exit(1) if sys.version_info.major < 3 or sys.version_info.minor < 7 else exit(0)" &> /dev/null; then
    echo "Python3.7 or higher version required!"
    exit 1
fi

if ! $PYTHON -c "import pip" &> /dev/null; then
    echo "Please install pip first!"
    exit 1
fi

if [ ! -d "$TOOLS" ]; then
    echo "$TOOLS directory not exists"
    exit 1
fi

echo "Uninstall all xdevice packages"
packages=$($PYTHON -m pip list | grep "^xdevice" | awk '{print $1}')
for pkg in $packages; do
    $PYTHON -m pip uninstall -y "$pkg"
done

echo
echo "Install packages under $BASE_DIR/$TOOLS"

for pkg in "$TOOLS"/*.egg; do
    if ! $PYTHON -c "import easy_install" &> /dev/null; then
        echo "Please install setuptools==46.1.3 first!"
        exit 1
    fi
    echo "Installing: $pkg"
    $PYTHON -m easy_install --user "$pkg" || echo "Error occurs to install $pkg!"
done

for pkg in "$TOOLS"/*.tar.gz; do
    echo "Installing: $pkg"
    $PYTHON -m pip install  --user "$pkg" || echo "Error occurs to install $pkg!"
done

$PYTHON -m xdevice "$@"
