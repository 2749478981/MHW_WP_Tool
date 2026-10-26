# -*- coding: utf-8 -*-
"""统一路径工具：源码运行 / PyInstaller 打包后都能找到 assets 与 data。"""
import os
import sys


def base_dir():
    """资源根目录。onefile 打包后指向解压出来的临时目录。"""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset(*parts):
    return os.path.join(base_dir(), "assets", *parts)


def data(*parts):
    return os.path.join(base_dir(), "data", *parts)


def app_dir():
    """exe 所在目录（用于默认输出路径、日志）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
