# -*- coding: utf-8 -*-
"""内置游戏资源访问（evwp / epv3 / epvsp / wwct）。

资源来自解包的 chunk/wp，由 tools/prepare_assets.py 复制到 assets/，
打包进 exe，用于「MOD 里缺文件时补一份游戏默认的」。
"""
import os
import re

from . import paths

# 武器类型缩写 → 中文名
ABBR_CN = {
    "two": "大剑", "one": "片手剑", "sou": "双剑", "swo": "太刀",
    "ham": "大锤", "hue": "狩猎笛", "lan": "长枪", "gun": "铳枪",
    "saxe": "斩斧", "caxe": "盾斧", "rod": "操虫棍", "bow": "弓",
    "hbg": "重弩炮", "lbg": "轻弩炮", "mus": "猎虫",
}

# 武器类型缩写 → 通用特效文件基名 hm_wpXX
EPV_BASE = {
    "two": "hm_wp00", "one": "hm_wp01", "sou": "hm_wp02", "swo": "hm_wp03",
    "ham": "hm_wp04", "hue": "hm_wp05", "lan": "hm_wp06", "gun": "hm_wp07",
    "saxe": "hm_wp08", "caxe": "hm_wp09", "rod": "hm_wp10", "mus": "hm_wp10mus",
    "bow": "hm_wp11", "hbg": "hm_wbc", "lbg": "hm_wbl",
}


def epv_base(abbr):
    """武器类型 → 通用特效基名（hm_wp03）。未知类型返回 None。"""
    return EPV_BASE.get(abbr)


def _wp(*parts):
    return paths.asset("wp", *parts)


def evwp_for(abbr, dir_name):
    """取游戏默认 evwp 的 {文件名: bytes}。dir_name 形如 swo028 / bs_swo028。

    返回 (文件名, bytes) 或 (None, None)。
    """
    d = _wp(abbr, dir_name, "mod")
    if not os.path.isdir(d):
        return None, None
    for f in sorted(os.listdir(d)):
        if f.lower().endswith(".evwp"):
            with open(os.path.join(d, f), "rb") as fp:
                return f, fp.read()
    return None, None


def all_evwp(abbr, dir_name):
    """该目录下全部 evwp（太刀有 swo028.evwp + saya028.evwp 两个）。"""
    out = {}
    d = _wp(abbr, dir_name, "mod")
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if f.lower().endswith(".evwp"):
            with open(os.path.join(d, f), "rb") as fp:
                out[f] = fp.read()
    return out


def epv_for(abbr, base_name):
    """取内置 epv3。base_name 形如 hm_wp03。返回 bytes 或 None。"""
    p = _wp(abbr, "epv", base_name + ".epv3")
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def epvsp_for(abbr, base_name):
    p = _wp(abbr, "sound", base_name + ".epvsp")
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def wwct_for(abbr, base_name):
    """epvsp 配套的音效控制表（不是每个武器都有）。"""
    p = _wp(abbr, "sound", base_name + "_epvsp_snd_ct.wwct")
    if os.path.isfile(p):
        with open(p, "rb") as f:
            return f.read()
    return None


def list_epv(abbr):
    """该武器类型内置的全部 epv3 基名（不含扩展名）。"""
    d = _wp(abbr, "epv")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(d)
                  if f.lower().endswith(".epv3"))


def has_assets():
    d = paths.asset("wp")
    return os.path.isdir(d)


def asset_stats():
    """给「关于」页显示：内置了多少文件。"""
    n_evwp = n_epv = n_snd = 0
    root = paths.asset("wp")
    for cur, _dirs, files in os.walk(root):
        for f in files:
            low = f.lower()
            if low.endswith(".evwp"):
                n_evwp += 1
            elif low.endswith(".epv3"):
                n_epv += 1
            elif low.endswith((".epvsp", ".wwct")):
                n_snd += 1
    return n_evwp, n_epv, n_snd


# 独立特效文件名的编号部分：hm_wp03_28 / hm_wp03_111
_RE_SUFFIX = re.compile(r"^(?P<base>.+?)_(?P<id>\d{1,3})$")


def split_effect_name(stem, abbr):
    """把 epv3/epvsp 的基名拆成 (基名, id 或 None)。

    hm_wp03      → ("hm_wp03", None)
    hm_wp03_28   → ("hm_wp03", 28)
    hm_wp03_111  → ("hm_wp03", 111)
    """
    base = epv_base(abbr)
    if base and stem == base:
        return base, None
    if base and stem.startswith(base + "_"):
        tail = stem[len(base) + 1:]
        if tail.isdigit():
            return base, int(tail)
    m = _RE_SUFFIX.match(stem)
    if m and m.group("id").isdigit():
        return m.group("base"), int(m.group("id"))
    return stem, None


def effect_filename(abbr, eid):
    """按特效 id 生成 epv3 基名：0/None → hm_wp03；28 → hm_wp03_28。"""
    base = epv_base(abbr)
    if base is None:
        return None
    if not eid:
        return base
    return "%s_%02d" % (base, eid) if eid < 100 else "%s_%d" % (base, eid)
