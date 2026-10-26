# -*- coding: utf-8 -*-
"""扫描 MOD 包，识别武器、特效形态、缺哪些文件。"""
import re

from . import assets, evwp, weapons

# wp/<abbr>/<dir>/mod/<file>
_RE_WP = re.compile(r"^wp/(?P<abbr>[a-z]+)/(?P<dir>(?:bs_)?(?P<abbr2>[a-z]+)(?P<num>\d+))/(?P<rest>.+)$")
# wp/<abbr>/epv/<file>
_RE_EPV = re.compile(r"^wp/(?P<abbr>[a-z]+)/epv/(?P<file>[^/]+)$")
# wp/<abbr>/sound/<file>
_RE_SND = re.compile(r"^wp/(?P<abbr>[a-z]+)/sound/(?P<file>[^/]+)$")


class PackageInfo:
    def __init__(self):
        self.abbr = None
        self.dir_name = None
        self.num = None
        self.is_bs = False
        self.epv_base = None
        self.evwp_files = {}      # 相对路径 → mEpvNo（读失败为 None）
        self.epv_files = {}       # 相对路径 → 特效 id（None = 通用）
        self.epvsp_files = {}     # 相对路径 → 特效 id
        self.wwct_files = {}
        self.model_files = []     # 武器模型相关文件（mod3/mrl3/ctc/evwp/tex）
        self.epv_dir_files = []   # wp/<abbr>/<dir>/epv/*（随刀特效）
        self.parts_dirs = []      # wp/<abbr>/parts/op_xxx
        self.form = "unknown"     # common / standalone / unknown
        self.effect_id = None
        self.issues = []
        self.warnings = []

    # ---- 展示用 ----
    @property
    def abbr_cn(self):
        return weapons.type_cn(self.abbr) if self.abbr else "?"

    @property
    def weapon_name(self):
        if not self.dir_name:
            return ""
        r = weapons.find_by_dir(self.dir_name, self.abbr)
        n = (r or {}).get("name") or ""
        return "" if n == "Unavailable" else n

    @property
    def title(self):
        if not self.dir_name:
            # 纯特效包没有模型目录，从 epv3 文件名能推出武器类型（太刀/双刀…）
            if self.abbr:
                return "%s · 纯特效包" % self.abbr_cn
            return "未识别出武器"
        bits = [self.abbr_cn, self.num or "?", self.weapon_name or "—"]
        if self.is_bs:
            bits.append("[组合模型]")
        return " ".join(bits)

    @property
    def form_cn(self):
        return {"common": "通用特效", "standalone": "独立特效",
                "unknown": "未识别"}[self.form]

    def summary_lines(self):
        out = []
        out.append("武器类型：%s（%s）" % (self.abbr_cn, self.abbr or "?"))
        out.append("模型目录：%s%s" % (self.dir_name or "?", "（组合模型）" if self.is_bs else ""))
        out.append("武器编号：%s" % (self.num or "?"))
        if self.weapon_name:
            out.append("武器名称：%s" % self.weapon_name)
        out.append("通用特效基名：%s" % (self.epv_base or "?"))
        out.append("")
        out.append("evwp：%d 个%s" % (len(self.evwp_files), self._epv_note()))
        out.append("epv3：%d 个%s" % (len(self.epv_files), self._epv_file_note()))
        out.append("epvsp：%d 个" % len(self.epvsp_files))
        if self.epv_dir_files:
            out.append("随刀特效：%d 个" % len(self.epv_dir_files))
        if self.parts_dirs:
            out.append("部件模型：%s" % ", ".join(self.parts_dirs))
        out.append("")
        out.append("判定：%s" % self.form_cn)
        return out

    def brief(self):
        """给界面用的紧凑字段。"""
        title = ("%s %s" % (self.abbr_cn, self.num)) if self.num else (
            "%s · 纯特效" % self.abbr_cn if self.abbr else "未识别出武器")
        if self.weapon_name:
            title += "  " + self.weapon_name
        if self.is_bs:
            title += "  [组合模型]"

        form = self.form_cn
        if self.form == "standalone" and self.effect_id:
            form += "（id=%d）" % self.effect_id

        bits = ["evwp %d" % len(self.evwp_files),
                "epv3 %d" % len(self.epv_files),
                "epvsp %d" % len(self.epvsp_files)]
        if self.epv_dir_files:
            bits.append("随刀 %d" % len(self.epv_dir_files))
        if self.parts_dirs:
            bits.append("部件 " + "/".join(self.parts_dirs))

        evp_nos = sorted({v for v in self.evwp_files.values() if v is not None})
        return {
            "title": title,
            "dir": ("%s%s" % (self.dir_name, "（组合模型）" if self.is_bs else ""))
            if self.dir_name else "无（纯特效包）",
            "base": self.epv_base or "?",
            "files": " · ".join(bits),
            "mepv": "mEpvNo = %s" % (",".join(map(str, evp_nos)) if evp_nos else "无 evwp"),
            "form": form,
        }

    def _epv_note(self):
        if not self.evwp_files:
            return "（无 → 游戏默认）"
        vals = sorted({v for v in self.evwp_files.values() if v is not None})
        return "，mEpvNo=%s" % (",".join(map(str, vals)) if vals else "?")

    def _epv_file_note(self):
        if not self.epv_files:
            return "（无）"
        ids = sorted({v for v in self.epv_files.values() if v is not None})
        if ids:
            return "，独立 id=%s" % ",".join(map(str, ids))
        return "，通用命名"


def scan(pkg):
    """扫描包，返回 PackageInfo。"""
    info = PackageInfo()

    # ---- 1. 找武器目录 ----
    dirs = {}
    for name in pkg.names():
        m = _RE_WP.match(name)
        if not m:
            continue
        abbr, dir_name, num = m.group("abbr"), m.group("dir"), m.group("num")
        # 过滤：wp/swo/parts/op_swo001 之类不会匹配，但防一手 abbr 不一致
        if m.group("abbr2") != abbr:
            continue
        d = dirs.setdefault(dir_name, {"abbr": abbr, "num": num,
                                       "is_bs": dir_name.startswith("bs_"),
                                       "files": []})
        d["files"].append(name)

    if dirs:
        # 文件最多的那个目录就是主武器
        main_dir = max(dirs.items(), key=lambda kv: len(kv[1]["files"]))[0]
        d = dirs[main_dir]
        info.abbr = d["abbr"]
        info.dir_name = main_dir
        info.num = d["num"]
        info.is_bs = d["is_bs"]
        info.model_files = sorted(d["files"])
        if len(dirs) > 1:
            info.warnings.append("包里有多套武器目录：%s，按文件最多的 %s 处理"
                                 % (", ".join(sorted(dirs)), main_dir))
    else:
        # 没有 mod 目录，退一步从 epv 路径猜
        for name in pkg.names():
            m = _RE_EPV.match(name)
            if m:
                info.abbr = m.group("abbr")
                break
        if not info.abbr:
            info.issues.append("没找到 wp/<武器>/ 结构，可能不是武器 MOD")
            return info
        info.warnings.append("包里没有模型文件（只有特效），按特效武器处理")

    info.epv_base = assets.epv_base(info.abbr)

    # ---- 2. evwp ----
    # ★ 只收主武器目录下的 evwp。MOD 包里常有「参考/」之类的作者留档目录，
    #   里面的 evwp 不属于这个武器，混进来会让 mEpvNo 判断出错。
    if info.dir_name:
        pre = "wp/%s/%s/mod/" % (info.abbr, info.dir_name)
        for name in pkg.names():
            if not name.startswith(pre) or not name.lower().endswith(".evwp"):
                continue
            data = pkg.read(name)
            try:
                info.evwp_files[name] = evwp.read_epv_no(data)
            except evwp.EvwpError:
                info.evwp_files[name] = None
                info.warnings.append("%s 不是有效 evwp（长度 %d）"
                                     % (name, len(data or b"")))
    if not info.evwp_files:
        # 没有模型目录时（纯特效包），退回按武器类型收
        for name in pkg.names():
            if not name.lower().endswith(".evwp") or "/mod/" not in name:
                continue
            if not name.startswith("wp/%s/" % info.abbr):
                continue
            data = pkg.read(name)
            try:
                info.evwp_files[name] = evwp.read_epv_no(data)
            except evwp.EvwpError:
                info.evwp_files[name] = None

    # ---- 3. epv3 ----
    for name in pkg.names():
        m = _RE_EPV.match(name)
        if not m or not name.lower().endswith(".epv3"):
            continue
        if m.group("abbr") != info.abbr:
            continue
        stem = m.group("file")[:-5]
        _base, eid = assets.split_effect_name(stem, info.abbr)
        info.epv_files[name] = eid

    # ---- 4. epvsp / wwct ----
    for name in pkg.names():
        m = _RE_SND.match(name)
        if not m or m.group("abbr") != info.abbr:
            continue
        low = name.lower()
        stem = m.group("file").rsplit(".", 1)[0]
        if low.endswith(".epvsp"):
            _base, eid = assets.split_effect_name(stem, info.abbr)
            info.epvsp_files[name] = eid
        elif low.endswith(".wwct") and "epvsp" in stem:
            info.wwct_files[name] = None

    # ---- 5. 随刀特效 + parts ----
    if info.dir_name:
        pre = "wp/%s/%s/epv/" % (info.abbr, info.dir_name)
        info.epv_dir_files = [n for n in pkg.names()
                              if n.startswith(pre) and n.lower().endswith(".epv3")]
        pre_parts = "wp/%s/parts/" % info.abbr
        for n in pkg.names():
            if n.startswith(pre_parts):
                d = n[len(pre_parts):].split("/")[0]
                if d and d not in info.parts_dirs:
                    info.parts_dirs.append(d)

    # ---- 6. 判定形态 ----
    ids = {v for v in info.epv_files.values() if v is not None}
    epv_nos = {v for v in info.evwp_files.values() if v is not None}
    if ids:
        info.form = "standalone"
        info.effect_id = sorted(ids)[0]
    elif epv_nos and any(v != 0 for v in epv_nos):
        info.form = "standalone"
        info.effect_id = sorted(v for v in epv_nos if v != 0)[0]
    elif info.epv_files or epv_nos == {0}:
        info.form = "common"
        info.effect_id = 0
    else:
        info.form = "common"
        info.effect_id = 0

    # ---- 7. 缺件提示 ----
    if not info.evwp_files:
        info.issues.append("没有 evwp（游戏用默认 evwp，转换时会补一份内置的）")
    if not info.epv_files:
        info.issues.append("没有 epv3（转换时会从内置资源补）")
    if not info.epvsp_files:
        info.warnings.append(
            "没有 epvsp —— 独立特效缺它会卡在加载界面，转独立特效时会自动补一份")

    return info
