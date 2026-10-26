# -*- coding: utf-8 -*-
"""武器数据表（来自「怪物猎人世界数据表」Excel 的「武器」页）。

用途：
1. 编号 → 武器名（界面上显示，避免只看到 swo028）
2. 武器 → 模型目录（替换武器模型时，目标目录名直接查表，不自己拼）
3. 附件模型目录（有的武器不止一个模型，如 wp/two/parts/op_two005）
"""
import json
import os
import re

from . import assets, paths

_CACHE = None


def load():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    p = paths.data("weapons.json")
    with open(p, encoding="utf-8") as f:
        _CACHE = json.load(f)
    return _CACHE


def dirname_of(model_path):
    """wp/swo/swo028 → swo028"""
    return model_path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def split_dirname(dir_name):
    """swo028 → ('swo', '028', False)；bs_swo028 → ('swo', '028', True)"""
    m = re.match(r"^(bs_)?([a-z]+)(\d+)$", dir_name)
    if not m:
        return None, None, False
    return m.group(2), m.group(3), bool(m.group(1))


def find_by_dir(dir_name, abbr=None):
    """按模型目录名找武器记录（取第一条有名字的）。"""
    want = dir_name.lower()
    hit = None
    for r in load():
        if dirname_of(r["model"]).lower() != want:
            continue
        if abbr and r["abbr"] != abbr:
            continue
        if r["name"] and r["name"] != "Unavailable":
            return r
        if hit is None:
            hit = r
    return hit


def find_by_num(abbr, num):
    """按武器类型缩写 + 编号找（num 可以是 '028' / 28 / '28'）。"""
    num = str(num).lstrip("0") or "0"
    hit = None
    for r in load():
        if r["abbr"] != abbr:
            continue
        if (r["num"].lstrip("0") or "0") != num:
            continue
        if r["name"] and r["name"] != "Unavailable":
            return r
        if hit is None:
            hit = r
    return hit


def model_list(abbr=None):
    """去重后的模型目录列表，供界面下拉选择。

    返回 [{abbr, dirname, path, attach, name, kind, nums}]，按 abbr + dirname 排序。
    """
    seen = {}
    for r in load():
        if not r["model"]:
            continue
        if abbr and r["abbr"] != abbr:
            continue
        key = r["model"].lower()
        item = seen.get(key)
        if item is None:
            item = seen[key] = {
                "abbr": r["abbr"],
                "dirname": dirname_of(r["model"]),
                "path": r["model"],
                "attach": r["attach"],
                "name": "",
                "kind": r["kind"],
                "nums": [],
            }
        if r["name"] and r["name"] != "Unavailable" and not item["name"]:
            item["name"] = r["name"]
            item["kind"] = r["kind"]
        if r["num"] and r["num"] not in item["nums"]:
            item["nums"].append(r["num"])
        if r["attach"] and not item["attach"]:
            item["attach"] = r["attach"]
    out = list(seen.values())
    for it in out:
        it["label"] = "%s  %s（%s）" % (
            it["dirname"], it["name"] or "—", it["kind"] or "—")
    out.sort(key=lambda x: (x["abbr"], x["dirname"]))
    return out


def search(keyword, limit=200):
    """按名称 / 目录名模糊搜索。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return []
    out, seen = [], set()
    for r in load():
        if not r["model"]:
            continue
        hay = "%s %s %s" % (r["name"], r["model"], r["abbr"])
        if kw not in hay.lower():
            continue
        key = r["model"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def type_cn(abbr):
    return assets.ABBR_CN.get(abbr, abbr)


def describe_dir(dir_name):
    """swo028 → '太刀 028 飞龙刀【樱花】'（查不到就只给目录名）。"""
    abbr, num, _is_bs = split_dirname(dir_name)
    if not abbr:
        return dir_name
    r = find_by_dir(dir_name, abbr)
    name = (r or {}).get("name") or ""
    if name == "Unavailable":
        name = ""
    parts = [type_cn(abbr), num]
    if name:
        parts.append(name)
    return " ".join(parts)
