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

import os
import requests
import shutil
import sys
import urllib3

urllib3.disable_warnings()


def copy_folder(src, dst):
    if not os.path.exists(src):
        print(f"copy folder error, source path '{src}' does not exist")
        return
    if not os.path.exists(dst):
        os.makedirs(dst)
    for filename in os.listdir(src):
        fr_path = os.path.join(src, filename)
        to_path = os.path.join(dst, filename)
        if os.path.isfile(fr_path):
            shutil.copy(fr_path, to_path)
        if os.path.isdir(fr_path):
            if not os.path.exists(to_path):
                os.makedirs(to_path)
            copy_folder(fr_path, to_path)


def download(url, to_path):
    cli = None
    try:
        cli = requests.get(url, timeout=5, verify=False)
        if cli.status_code == 200:
            with open(to_path, mode="wb+") as s_file:
                for chunk in cli.iter_content(chunk_size=1024 * 4):
                    s_file.write(chunk)
                s_file.flush()
    finally:
        if cli is not None:
            cli.close()


def main():
    sources = [
        {
            "file": "static/css/element-plus@2.3.4_index.css",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.css"
        },
        {
            "file": "static/element-plus@2.3.4_index.full.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus/2.3.4/index.full.js"
        },
        {
            "file": "static/element-plus_icons-vue@2.0.10_index.iife.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/element-plus-icons-vue/2.0.10/index.iife.min.js"
        },
        {
            "file": "static/EventEmitter.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/EventEmitter/5.2.8/EventEmitter.js"
        },
        {
            "file": "static/vue@3.2.41_global.min.js",
            "url": "https://cdn.bootcdn.net/ajax/libs/vue/3.2.41/vue.global.min.js"
        }
    ]
    cur_path = os.path.dirname(__file__)
    template_src = os.path.join(cur_path, "report")
    for source in sources:
        file, url = source.get("file"), source.get("url")
        to_path = os.path.join(template_src, file)
        if os.path.exists(to_path):
            continue
        print(f"get report template resource {file} from {url}")
        download(url, to_path)
        if not os.path.exists(to_path):
            raise Exception("get report template resource error")

    print("copy template to xdevice")
    template_dst = os.path.join(cur_path, "../src/xdevice/_core/resource/template")
    copy_folder(template_src, template_dst)


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except Exception as e:
        print(e)
        exit_code = 1
    sys.exit(exit_code)
