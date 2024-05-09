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

import enum
import time

try:
    from PIL import Image
    from PIL import ImageDraw
except ImportError:
    pass
from devicetest.utils.time_util import TS


class ImgLoc(enum.Enum):
    '''
    图片所在的枚举类
    1左上 (North_West)
    2中上 (North)
    3右上 (Nort_East)
    4左中 (West)
    5全图 (All)
    6右中 (East)
    7左下 (South_West)
    8中下 (South)
    9右下(South_East)
    '''

    # 在大图的左上内
    North_West = 1
    # 代表子图部分全部位于大图的水平中线以上
    North = 2
    # 在大图的右上内
    North_East = 3
    # 代表子图部分全部位于大图的垂直中线左
    West = 4
    # 全图查找,当小图跟大图的水平中线, 且与锤子中线都有交集,就只能用该参数了
    All = 5
    # 代表子图部分全部位于大图的垂直中线右
    East = 6
    # 在大图的左下内
    South_West = 7
    # 代表子图部分全部位于大图的水平中线以下
    South = 8
    # 在大图的右下内
    South_East = 9


class ImgUtils:
    @staticmethod
    def img2arr(arr_img, rect=None, convert=True):
        '''
        @将位图流转化为二维二值数组
        @param arr_img: instance of Image
        '''
        if convert and arr_img.mode != 'L':
            arr_img = arr_img.convert('L')

        width, height = arr_img.size
        pix = arr_img.load()
        if rect:
            rect_l, rect_t, rect_r, rect_b = rect
            result_list = []
            for pix_h in range(height):
                if not rect_t <= pix_h <= rect_b + 1:
                    continue
                temp_list = []
                for pix_w in range(width):
                    if not rect_l <= pix_w <= rect_r + 1:
                        continue
                    temp_list.append(pix[pix_w, pix_h])
                result_list.append(temp_list)
            return result_list

        result_list = []
        for pix_h in range(height):
            temp_list = []
            for pix_w in range(width):
                temp_list.append(pix[pix_w, pix_h])
            result_list.append(temp_list)

        return result_list

    @staticmethod
    def get_rect(rect_width, rect_height, location):
        '''
        根据方位对象,获取图片的方位
        '''
        rect = (0, 0, rect_width, rect_height)
        if location == ImgLoc.East.value:
            rect = (int(rect_width >> 1), 0, rect_width, rect_height)
        elif location == ImgLoc.South.value:
            rect = (0, int(rect_height >> 1), rect_width, rect_height)
        elif location == ImgLoc.West.value:
            rect = (0, 0, int(rect_width >> 1), rect_height)
        elif location == ImgLoc.North.value:
            rect = (0, 0, rect_width, int(rect_height >> 1))

        elif location == ImgLoc.North_East.value:
            rect = (int(rect_width >> 1), 0,
                    rect_width, int(rect_height >> 1))
        elif location == ImgLoc.South_East.value:
            rect = (int(rect_width >> 1),
                    int(rect_height >> 1), rect_width, rect_height)
        elif location == ImgLoc.North_West.value:
            rect = (0, 0, int(rect_width >> 1), int(rect_height >> 1))
        elif location == ImgLoc.South_West.value:
            rect = (0, int(rect_height >> 1),
                    int(rect_width >> 1), rect_height)

        return rect

    @staticmethod
    def quick_find(fp1, fp2, similar=1, density=None,
                   rect=None, loc=ImgLoc.All.value, debug=False):
        '''
        快速查找图片,指定的similar越大,速度越快
        1. 如果similar不等于1,则使用density来加快查找速度 density(x,y)
        表示对比的时候 每个横坐标上只对比 (width / 2^x)个点
        每个纵坐标上只对比 height / 2^y个点,相当于只对比原来的
        (width + height) / 2^(x+y) 个点
        @param fp1: 大图片的绝对路径
        @param fp2: 小图片的绝对路径
        @param similar: 对比的相似度;如 0.7, 0.9, 1
        @param density: 小图中对比的密度: (2,3) 表示每行对比 width >> 2个点;
        没列对比 height >> 3个点
        @param rect: 大图中指定区域内查找 (left,top,right,bottom)
        @param loc: 小图在大图中的什么部位，是一个枚举对象,ImgLoc,注意需要
        加.value；如: ImgLoc.North.value 或者 直接输入 1 -9 的数字也行
        @param debug: 是否打印debug信息
        '''
        if debug:
            TS.start()
        _m1 = Image.open(fp1)
        _m2 = Image.open(fp2)

        m1_w, m1_h = _m1.size
        if not rect:
            rect = ImgUtils.get_rect(m1_w, m1_h, loc)

        data1 = ImgUtils.img2arr(_m1.crop(rect) if rect else _m1)
        data2 = ImgUtils.img2arr(_m2)
        if debug:
            TS.stop("before find_arr")
        return ImgUtils.find_arr(data1, data2, similar, density, rect, debug)

    @staticmethod
    def find_arr(im1, im2, similar=1, density=None, rect=None, debug=False):
        '''
        在大图中查找小图
        注意:如果density值为None，则系统自动设置，保证特征点在9 - 16个左右
        (即 3 * 3 或 4 * 4之间)
        @param im1 大图的二维数组
        @param im2 小图的二维数组
        @param similar 相似度
        @param density (x,y)  x: 可以控制小图横坐标查找的点数
        im2Width >> x 个点数
        @param rect 在指定的区域中查找图片 (若指定,则可以大大节省时间)
        (leftX,topY,rihgtX,bottomY)
        @return (rect,similar) rect:找到的图片位置; similar:相似度
        '''
        if debug:
            TS.start()

        m2_width = len(im2[0])
        m2_height = len(im2)
        arr_width = len(im1[0]) - m2_width + 1
        arr_height = len(im1) - m2_height + 1

        denx, deny = 0, 0
        if not density:
            denx, deny = ImgUtils.get_density(m2_width, m2_height)
        else:
            denx, deny = density
        den_yy = int(m2_height >> deny)
        den_xx = int(m2_width >> denx)

        total = den_yy * den_xx
        if total == 0:
            total = 1
        max_fail_num = (1 - similar) * total
        if debug:
            print("denXX: %i; denYY: %i; total: %i" % (
                den_xx, den_yy, total))
            print("maxFailNum %i" % max_fail_num)
        starttime = time.time()
        endtime = starttime + 5.0 * 60.0
        for arr_h in range(arr_height):
            for arr_w in range(arr_width):
                # 对图片对比设置超时限制
                if time.time() <= endtime:
                    # 1. 对比当前位置的图片是否符合要求
                    fail_num = 0
                    found = True
                    for _yy in range(den_yy):
                        for _xx in range(den_xx):
                            x_den = _xx << denx
                            y_den = _yy << deny
                            m2_val = im2[y_den][x_den]
                            m1_val = im1[arr_h + y_den][x_den + arr_w]
                            if m1_val != m2_val:
                                fail_num += 1
                                if max_fail_num <= fail_num:
                                    found = False
                                    break
                        if not found:
                            break
                    if found:
                        if debug:
                            TS.stop("find_arr")
                        if rect:
                            # @UnusedVariable
                            rect_l, rect_t, rect_r, rect_b = rect
                            return (1 - fail_num / total), (
                                arr_w + rect_l, arr_h + rect_t, arr_w +
                                m2_width + rect_l, arr_h + m2_height + rect_t)
                        return (1 - fail_num / total), (
                            arr_w, arr_h, arr_w + m2_width, arr_h + m2_height)
                else:
                    return None, None
        if debug:
            TS.stop("find_arr")
        return None, None

    @staticmethod
    def img_filter(filter_img, *filters):
        last_img = filter_img
        for _filter in filters:
            last_img = last_img.filter(_filter)
        return last_img

    @staticmethod
    def get_density(width, height, maxWNum=4, maxHNum=4):
        denx, deny = 0, 0
        while width > maxWNum:
            denx += 1
            width = int(width >> 1)
        while height > maxHNum:
            deny += 1
            height = int(height >> 1)
        return denx, deny
