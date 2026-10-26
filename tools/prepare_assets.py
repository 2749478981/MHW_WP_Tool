# -*- coding: utf-8 -*-
"""生成内置资源 + 武器数据表（开发期跑一次，产物随 exe 打包）。

数据来源：
- D:/mhwmod解包/evwp all/chunk/wp   游戏默认 evwp / epv / epvsp
- D:/mhwmod解包/怪物猎人世界数据表*.xlsx  武器编号 → 名称 / 模型路径
"""
import json
import os
import re
import shutil

SRC = r"D:/mhwmod解包/evwp all/chunk/wp"
OUT_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
OUT_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

XLSX_CANDIDATES = [
    r"D:/mhwmod解包/怪物猎人世界数据表15.10.00简中_by冰块&Jodo (3).xlsx",
]

# 武器类型 ID → 目录缩写（MHW 内部代码）
TYPE_ABBR = {
    0: "two", 1: "one", 2: "sou", 3: "swo", 4: "ham", 5: "hue",
    6: "lan", 7: "gun", 8: "saxe", 9: "caxe", 10: "rod",
    11: "bow", 12: "hbg", 13: "lbg",
}
TYPE_CN = {
    "two": "大剑", "one": "片手剑", "sou": "双剑", "swo": "太刀",
    "ham": "大锤", "hue": "狩猎笛", "lan": "长枪", "gun": "铳枪",
    "saxe": "斩斧", "caxe": "盾斧", "rod": "操虫棍", "bow": "弓",
    "hbg": "重弩炮", "lbg": "轻弩炮", "mus": "猎虫",
}


def copy_assets():
    """把 evwp / epv3 / epvsp / wwct 复制进 assets，保留 wp/<type>/ 结构。"""
    n = 0
    for wtype in sorted(os.listdir(SRC)):
        src_dir = os.path.join(SRC, wtype)
        if not os.path.isdir(src_dir):
            continue
        for sub in ("epv", "sound"):
            s = os.path.join(src_dir, sub)
            if not os.path.isdir(s):
                continue
            for name in os.listdir(s):
                low = name.lower()
                if sub == "epv" and not low.endswith(".epv3"):
                    continue
                if sub == "sound" and not (low.endswith(".epvsp") or low.endswith(".wwct")):
                    continue
                dst_dir = os.path.join(OUT_ASSETS, "wp", wtype, sub)
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(os.path.join(s, name), os.path.join(dst_dir, name))
                n += 1
        # 各武器目录下的 evwp
        for name in os.listdir(src_dir):
            mod_dir = os.path.join(src_dir, name, "mod")
            if not os.path.isdir(mod_dir):
                continue
            for f in os.listdir(mod_dir):
                if not f.lower().endswith(".evwp"):
                    continue
                dst_dir = os.path.join(OUT_ASSETS, "wp", wtype, name, "mod")
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(os.path.join(mod_dir, f), os.path.join(dst_dir, f))
                n += 1
    print("复制资源 %d 个文件" % n)


def export_weapons():
    import openpyxl

    xlsx = next((p for p in XLSX_CANDIDATES if os.path.exists(p)), None)
    if xlsx is None:
        raise SystemExit("找不到数据表 xlsx")
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["武器"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        if r[0] is None:
            continue
        try:
            type_id = int(r[0])
        except (TypeError, ValueError):
            continue
        abbr = TYPE_ABBR.get(type_id)
        if abbr is None:
            continue
        model_path = (r[6] or "").replace("\\", "/").strip("/")
        attach_path = (r[7] or "").replace("\\", "/").strip("/")
        # 从模型路径反推武器编号，比直接用「武器ID」可靠（组合模型会共用）
        m = re.search(r"([a-z]+)(\d+)$", model_path.rsplit("/", 1)[-1] if model_path else "")
        num = m.group(2) if m else ""
        out.append({
            "typeId": type_id,
            "abbr": abbr,
            "typeCn": TYPE_CN.get(abbr, r[1] or ""),
            "wid": int(r[2]) if r[2] is not None else -1,
            "num": num,
            "name": (r[3] or "").strip(),
            "rarity": r[4],
            "kind": (r[5] or "").strip(),
            "model": model_path,
            "attach": attach_path,
        })

    os.makedirs(OUT_DATA, exist_ok=True)
    p = os.path.join(OUT_DATA, "weapons.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("导出武器 %d 条 -> %s (%.1f KB)" % (len(out), p, os.path.getsize(p) / 1024))

    # 顺便统计一下模型目录，便于自检
    dirs = sorted({r["model"] for r in out if r["model"]})
    print("不同模型目录 %d 个" % len(dirs))


if __name__ == "__main__":
    copy_assets()
    export_weapons()
