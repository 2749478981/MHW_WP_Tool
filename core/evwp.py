# -*- coding: utf-8 -*-
""".evwp 二进制读写。

145 字节定长，小端。字段布局（与 010 模板逐字节核对一致）：

    offset  size  字段
    0       4     mark
    4       4     magic "EVWP"
    8       4     version
    12      28    room   (pos/rot/scale)
    40      28    smith  (pos/rot/scale)
    68      28    sheath (pos/rot/scale)
    96      4     presetIdOffShake
    100     4     mMotNo
    104     4     mWpTypeGeneralValue
    108     4     mEpvNo        ← 决定用哪个 epv3 / epvsp
    112     28    pendant (pos/rot/scale)
    140     5     5 × byte flag
"""
import struct

EVWP_SIZE = 145
MAGIC = b"EVWP"

OFF_SHEATH_POS = 68
OFF_SHEATH_ROT = 80
OFF_SHEATH_SCALE = 92
OFF_PRESET = 96
OFF_MOTION = 100
OFF_GENERAL = 104
OFF_EPV_NO = 108
OFF_PENDANT = 112


class EvwpError(Exception):
    pass


def is_evwp(data):
    return len(data) == EVWP_SIZE and data[4:8] == MAGIC


def read_epv_no(data):
    """读 mEpvNo。0 = 通用特效，N = 独立特效 N。"""
    if not is_evwp(data):
        raise EvwpError("不是有效的 evwp（长度 %d，magic %r）" % (len(data), data[4:8]))
    return struct.unpack_from("<I", data, OFF_EPV_NO)[0]


def write_epv_no(data, value):
    """写 mEpvNo，返回新的 bytes（不改原对象）。"""
    if not is_evwp(data):
        raise EvwpError("不是有效的 evwp")
    if not 0 <= value <= 0xFFFFFFFF:
        raise EvwpError("mEpvNo 超出范围：%d" % value)
    buf = bytearray(data)
    struct.pack_into("<I", buf, OFF_EPV_NO, value)
    return bytes(buf)


def read_ints(data):
    """四个 uint 一起读，便于调试 / 界面显示。"""
    return struct.unpack_from("<4I", data, OFF_PRESET)


def describe(data):
    if not is_evwp(data):
        return "无效 evwp"
    p, m, g, e = read_ints(data)
    return "mEpvNo=%d  mMotNo=%d  general=%d  preset=%d" % (e, m, g, p)
