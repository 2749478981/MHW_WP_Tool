# -*- coding: utf-8 -*-
"""四种操作。

1. to_standalone  通用特效 → 独立特效
2. to_common      独立特效 → 通用特效
3. replace_weapon 把 MOD 的替换目标武器改成另一把
4. strip_model    去掉模型替换，只保留特效

所有操作都在 Package 内存里完成，调用方决定保存到哪。
"""
import re

from . import assets, evwp, weapons

TEX_EXT = (".tex",)

# 特效侧文件：这些要留下，其余算模型侧
EFFECT_EXT = (".evwp", ".epv3", ".epvsp", ".wwct")


def _log(log, action, detail=""):
    log.append((action, detail))


def _num_re(num):
    """匹配独立的编号（避免 028 命中 0280）。"""
    return re.compile(r"(?<!\d)" + re.escape(num) + r"(?!\d)")


def _rename_to_single(pkg, names, want, log, label):
    """把一组同类文件收成一个 `want`；多出来的原样保留（别互相覆盖）。"""
    names = sorted(names)
    if not names:
        return False
    if want in names:
        _log(log, "保留", want)
        for n in names:
            if n != want:
                _log(log, "多余 " + label, "%s（保持原样，未动）" % n)
        return True
    pkg.rename(names[0], want)
    _log(log, "改名", "%s → %s" % (names[0], want))
    for n in names[1:]:
        _log(log, "多余 " + label, "%s（保持原样，未动）" % n)
    return True


def _sync_sound(pkg, info, target_stem, fill_missing, log):
    """把 epvsp / wwct 统一成 target_stem（`hm_wp03` 或 `hm_wp03_28`）。

    ★ epvsp 是**必需文件**：游戏按 mEpvNo 拼出 `hm_wpXX[_NN].epvsp` 去加载，
      独立特效缺了它不是「没音效」，而是**卡在加载界面**。
      所以这里返回是否拿到了 epvsp，调用方据此决定要不要中止。
    """
    abbr = info.abbr
    base = info.epv_base or assets.epv_base(abbr)
    want = "wp/%s/sound/%s.epvsp" % (abbr, target_stem)
    has_epvsp = False

    if info.epvsp_files:
        _rename_to_single(pkg, list(info.epvsp_files), want, log, "epvsp")
        has_epvsp = True
    elif fill_missing:
        data = assets.epvsp_for(abbr, base)
        if data is None:
            _log(log, "缺 epvsp",
                 "包里没有，内置资源里也没有 %s.epvsp" % base)
        else:
            pkg.write(want, data)
            _log(log, "补入内置 epvsp", "%s.epvsp → %s" % (base, want))
            has_epvsp = True

    # wwct：hm_wp03_epvsp_snd_ct / hm_wp03_28_epvsp_snd_ct
    pat = re.compile(r"^" + re.escape(base) + r"(?:_\d+)?(_epvsp_snd_ct)\.wwct$", re.I)
    for name in sorted(info.wwct_files):
        folder, _sep, fname = name.rpartition("/")
        m = pat.match(fname)
        if not m:
            continue
        new_name = "%s/%s%s.wwct" % (folder, target_stem, m.group(1))
        if new_name != name:
            pkg.rename(name, new_name)
            _log(log, "改名", "%s → %s" % (name, new_name))
    return has_epvsp



# ----------------------------------------------------------------------
# 特效路径隔离
#
# 问题：通用特效 MOD 往往直接覆盖默认路径 vfx/efx/wp/wp03/ 下的 efx。
#       这种包转成独立特效后，epv3 里引用的还是默认路径 ——
#       于是所有用通用特效（mEpvNo=0）的武器都会读到被改的 efx，冲突。
#
# 解法：把默认路径的整个目录按 epvid 搬到另一个目录，再把 epv3 里的
#       路径字符串一起改掉。epv3 是二进制，路径字符串长度必须保持一致，
#       所以隔离名也做成 4 字符：
#         wp03 + id=28  → wp28
#         wp03 + id=111 → w111
# ----------------------------------------------------------------------
def _isolate_key(epv_base, eid):
    """`hm_wp03` + 28 → `wp28`；+ 111 → `w111`（都是 4 字符，可等长替换）。"""
    m = re.match(r"^hm_(wp\d+)$", epv_base or "")
    if not m:
        return None
    if not 1 <= eid <= 999:
        return None
    return "wp%02d" % eid if eid <= 99 else "w%03d" % eid


def _move_effect_dir(pkg, src_key, dst_key, log, note):
    """把 vfx/efx/wp/<src_key>/ 整个搬到 <dst_key>/。"""
    src_pre = "vfx/efx/wp/%s/" % src_key
    dst_pre = "vfx/efx/wp/%s/" % dst_key
    moved = 0
    for name in list(pkg.names()):
        if name.startswith(src_pre):
            pkg.rename(name, dst_pre + name[len(src_pre):])
            moved += 1
    if moved:
        _log(log, note, "%s → %s（%d 个文件）" % (src_pre, dst_pre, moved))
    return moved


def _rewrite_effect_refs(pkg, src_key, dst_key, log):
    r"""把包里所有 epv3 中的 `vfx\efx\wp\<src>\` 换成 `<dst>\`。

    等长替换，不改变二进制里任何偏移。
    """
    old = ("vfx\\efx\\wp\\%s\\" % src_key).encode("latin1")
    new = ("vfx\\efx\\wp\\%s\\" % dst_key).encode("latin1")
    if len(old) != len(new):
        _log(log, "跳过改路径", "新旧长度不一致（%d vs %d）" % (len(old), len(new)))
        return 0
    fixed = 0
    for name in list(pkg.names()):
        if not name.lower().endswith(".epv3"):
            continue
        data = pkg.read(name)
        if not data or old not in data:
            continue
        pkg.write(name, data.replace(old, new))
        fixed += 1
        _log(log, "改特效路径", "%s：wp\\%s → %s" % (name, src_key, dst_key))
    return fixed


def to_standalone(pkg, info, eid, owner_dir=None):
    """通用 → 独立：改 evwp 的 mEpvNo，epv3 / epvsp / wwct 加 _NN 后缀。

    owner_dir：纯特效包（没有 wp/<wt>/<dir>/ 模型目录）时，用来指定
    「这套特效属于哪把武器」。补 evwp 必须知道目录名，否则不知道该往哪写。
    """
    log = []
    if not 1 <= eid <= 999:
        return log, "特效 ID 必须在 1~999 之间"

    # 纯特效包可能连 epv3 都没有，这时 abbr 推不出来 —— 从所属武器目录名反推
    abbr = info.abbr
    if not abbr and owner_dir:
        abbr = re.sub(r"[^a-z]", "", owner_dir.replace("bs_", ""))
        if abbr:
            info.abbr = abbr      # 写回去，后面 _sync_sound 也要用
            _log(log, "推断武器类型", "%s（来自所属武器 %s）" % (abbr, owner_dir))
    if not abbr:
        return log, "没识别出武器类型，无法转换（可以在「所属武器」里指定）"

    # 包里没 epv3 时，用内置的通用特效名当基准
    base = info.epv_base or assets.epv_base(abbr)
    new_stem = assets.effect_filename(abbr, eid)     # hm_wp03_28
    if not new_stem:
        return log, "未知武器类型，无法生成特效文件名"

    # ---- 前置检查：宁可现在就报错，也别改了一半文件再失败 ----
    if not info.evwp_files and not (info.dir_name or owner_dir):
        return log, ("包里没有模型目录（纯特效包），需要指定这套特效属于哪把武器，"
                     "否则不知道该把 evwp 补到哪。")
    if not info.epvsp_files and assets.epvsp_for(abbr, base) is None:
        return log, ("独立特效必须带 %s.epvsp，但包里没有、内置资源里也没有。\n"
                     "缺了它游戏会卡在加载界面，已中止（本次不会输出文件）。" % new_stem)

    # ---- 特效路径隔离：默认路径的 efx 搬到独立目录，避免通用特效也读到 ----
    iso = _isolate_key(base, eid)
    src_key = re.match(r"^hm_(wp\d+)$", base).group(1) if re.match(r"^hm_(wp\d+)$", base) else None
    if iso and src_key and iso != src_key:
        if _move_effect_dir(pkg, src_key, iso, log, "隔离特效目录"):
            _rewrite_effect_refs(pkg, src_key, iso, log)

    # ---- epv3 ----
    if info.epv_files:
        _rename_to_single(pkg, list(info.epv_files),
                          "wp/%s/epv/%s.epv3" % (abbr, new_stem), log, "epv3")
    else:
        data = assets.epv_for(abbr, base)
        if data is None:
            # 轻弩炮（lbg）这类武器本来就没有武器特效，内置资源里也没有
            _log(log, "跳过 epv3",
                 "内置资源里没有 %s.epv3（该武器类型没有通用特效）" % base)
        else:
            new_name = "wp/%s/epv/%s.epv3" % (abbr, new_stem)
            pkg.write(new_name, data)
            _log(log, "补入内置 epv3",
                 "%s.epv3（%d 字节）→ %s" % (base, len(data), new_name))

    # ---- epvsp / wwct ----
    # ★ 独立特效没有 epvsp 会让游戏卡在加载界面，所以这里必须拿到；
    #   拿不到就整体中止，不能生成一个进不去的包。
    if not _sync_sound(pkg, info, new_stem, True, log):
        return log, ("独立特效必须带 %s.epvsp，但包里没有、内置资源里也没有。\n"
                     "缺了它游戏会卡在加载界面，已中止（本次不会输出文件）。" % new_stem)

    # ---- evwp ----
    if info.evwp_files:
        for name in list(info.evwp_files):
            data = pkg.read(name)
            if data is None:
                continue
            try:
                cur = evwp.read_epv_no(data)
                if cur == eid:
                    _log(log, "保留", "%s：mEpvNo 已经是 %d" % (name, eid))
                else:
                    pkg.write(name, evwp.write_epv_no(data, eid))
                    _log(log, "改 mEpvNo", "%s：%d → %d" % (name, cur, eid))
            except evwp.EvwpError as exc:
                _log(log, "跳过", "%s：%s" % (name, exc))
    else:
        # 纯特效包没有模型目录，用调用方指定的所属武器（owner_dir）
        dir_name = info.dir_name or owner_dir
        if not dir_name:
            return log, ("包里没有模型目录（纯特效包），需要指定这套特效属于哪把武器，"
                         "否则不知道该把 evwp 补到哪。")
        found = assets.all_evwp(abbr, dir_name)
        if not found:
            return log, "内置资源里找不到 %s 的默认 evwp" % dir_name
        if not info.dir_name:
            _log(log, "所属武器", "%s（纯特效包，按它补 evwp）" % dir_name)
        for fname, data in found.items():
            rel = "wp/%s/%s/mod/%s" % (abbr, dir_name, fname)
            pkg.write(rel, evwp.write_epv_no(data, eid))
            _log(log, "补入内置 evwp", "%s（mEpvNo → %d）" % (rel, eid))

    return log, None


# ----------------------------------------------------------------------
def to_common(pkg, info):
    """独立 → 通用：mEpvNo 归零，epv3 / epvsp / wwct 改回通用名。"""
    log = []
    if not info.abbr:
        return log, "没识别出武器类型，无法转换"

    abbr = info.abbr
    base = info.epv_base
    if not base:
        return log, "未知武器类型，无法生成通用特效文件名"

    # ---- 特效路径还原：独立目录搬回默认，免得通用特效找不到 ----
    iso = _isolate_key(base, info.effect_id or 0)
    src_key = re.match(r"^hm_(wp\d+)$", base).group(1) if re.match(r"^hm_(wp\d+)$", base) else None
    if iso and src_key and iso != src_key:
        if _move_effect_dir(pkg, iso, src_key, log, "还原特效目录"):
            _rewrite_effect_refs(pkg, iso, src_key, log)

    # ---- epv3 ----
    if not info.epv_files:
        _log(log, "跳过 epv3", "包里没有 epv3")
    else:
        _rename_to_single(pkg, list(info.epv_files),
                          "wp/%s/epv/%s.epv3" % (abbr, base), log, "epv3")

    # ---- epvsp / wwct（通用特效也必须带自己那份）----
    _sync_sound(pkg, info, base, True, log)

    # ---- evwp ----
    if not info.evwp_files:
        _log(log, "跳过 evwp", "包里没有 evwp（游戏本来就用默认的，mEpvNo 已经是 0）")
    for name in list(info.evwp_files):
        data = pkg.read(name)
        if data is None:
            continue
        try:
            cur = evwp.read_epv_no(data)
            if cur == 0:
                _log(log, "保留", "%s：mEpvNo 已经是 0" % name)
            else:
                pkg.write(name, evwp.write_epv_no(data, 0))
                _log(log, "改 mEpvNo", "%s：%d → 0" % (name, cur))
        except evwp.EvwpError as exc:
            _log(log, "跳过", "%s：%s" % (name, exc))

    return log, None


# ----------------------------------------------------------------------
def _target_prefix(dst_is_bs, stem):
    """去掉/补上 bs_ 前缀。"""
    has = stem.startswith("bs_")
    core = stem[3:] if has else stem
    return ("bs_" if dst_is_bs else "") + core


def _rename_stem(stem, src_num, dst_num, src_bs, dst_bs):
    """把文件名主体里的编号换成目标编号，并同步 bs_ 前缀。

    不含源编号的文件名（如自定义贴图名）返回 None，表示不改名。
    """
    if not src_num or not dst_num or src_num == dst_num:
        return None
    pat = _num_re(src_num)
    if not pat.search(stem):
        return None
    core = _target_prefix(dst_bs, stem)
    return pat.sub(dst_num, core, count=1)


def replace_weapon(pkg, info, target, sync_epv_id=True):
    """把替换目标改成另一把武器。

    会动的：mod3 / mrl3 / ctc / evwp / 随刀 epv3 / parts —— 换目录并改编号。
    不动的：tex —— 名字不改、也不跟着搬，留在原目录
            （mrl3 里写的是完整路径 `wp\\swo\\swo028\\mod\\swo028_BML`）。

    sync_epv_id=True 时，如果这个包用的是独立特效，会把 epvid 一起改成
    目标武器的编号（swo028 → swo032 就把 id 28 改成 32）——
    独立特效的 id 惯例就是武器编号，不跟着改会和目标武器原本的特效撞车。
    """
    log = []
    if not info.dir_name:
        return log, "包里没有武器模型目录，无法替换"
    if not target or not target.get("dirname"):
        return log, "没有选择目标武器"

    abbr = info.abbr
    src_dir = info.dir_name
    dst_dir = target["dirname"]
    src_num = info.num or ""
    dst_num = re.sub(r"\D", "", dst_dir) or ""
    if not dst_num:
        return log, "目标目录名里没有编号：%s" % dst_dir
    src_bs = info.is_bs
    dst_bs = dst_dir.startswith("bs_")

    if src_dir.lower() == dst_dir.lower():
        return log, "源和目标都是 %s，不需要改" % src_dir

    # 目标武器的模型目录可能不在同一个武器类型下（正常不会，防一手）
    dst_abbr = re.sub(r"[^a-z]", "", dst_dir.replace("bs_", "")) or abbr
    if dst_abbr != abbr:
        return log, "目标武器类型（%s）和源（%s）不一致，暂不支持跨武器类型替换" % (dst_abbr, abbr)

    # ---- 0. 独立特效的 epvid 跟随目标武器编号 ----
    if sync_epv_id and info.form == "standalone":
        new_eid = int(dst_num)
        _log(log, "同步 epvid", "%d → %d（跟随目标武器 %s）"
             % (info.effect_id or 0, new_eid, dst_dir))
        part, err = to_standalone(pkg, info, new_eid)
        log.extend(part)
        if err:
            return log, "同步特效 ID 失败：%s" % err

    renamed = 0
    skipped_tex = 0

    pre_src = "wp/%s/%s/" % (abbr, src_dir)
    pre_dst = "wp/%s/%s/" % (abbr, dst_dir)
    if any(n.startswith(pre_dst) for n in pkg.names()):
        _log(log, "注意",
             "包里已经有 %s 目录，同名文件会被覆盖" % dst_dir)

    # ---- 1. 主模型目录 ----
    for name in list(pkg.names()):
        if not name.startswith(pre_src):
            continue
        tail = name[len(pre_src):]           # mod/swo028.mod3
        head, _sep, fname = tail.rpartition("/")
        low = fname.lower()

        if low.endswith(TEX_EXT):
            # ★ 贴图不改名、也不跟着搬：mrl3 里写的是完整路径
            #   （wp\swo\swo028\mod\swo028_BML），留在原目录才能被找到。
            skipped_tex += 1
            continue

        stem, dot, ext = fname.rpartition(".")
        if not dot:
            stem, ext = fname, ""
        new_stem = _rename_stem(stem, src_num, dst_num, src_bs, dst_bs)
        if new_stem is None and low.endswith(".epvsp") and info.epv_base:
            # 随刀目录里的冗余 epvsp 副本：hm_wp03_28.epvsp → hm_wp03_04.epvsp
            m = re.match(r"^" + re.escape(info.epv_base) + r"_(?P<id>\d{1,3})$", stem)
            if m:
                new_stem = (assets.effect_filename(abbr, int(dst_num))
                            or "%s_%d" % (info.epv_base, int(dst_num)))
        new_fname = fname if new_stem is None else new_stem + ("." + ext if ext else "")

        new_name = pre_dst + (head + "/" if head else "") + new_fname
        if new_name != name:
            pkg.rename(name, new_name)
            renamed += 1
            # 只有文件名真变了才记日志（单纯换目录的不刷屏）
            if new_fname != fname:
                _log(log, "改名", "%s → %s" % (fname, new_fname))

    # ---- 2. 部件模型 wp/<abbr>/parts/op_<src> ----
    src_parts = "op_%s" % src_dir
    dst_parts = "op_%s" % dst_dir
    pre_src_p = "wp/%s/parts/%s/" % (abbr, src_parts)
    pre_dst_p = "wp/%s/parts/%s/" % (abbr, dst_parts)
    for name in list(pkg.names()):
        if not name.startswith(pre_src_p):
            continue
        tail = name[len(pre_src_p):]
        head, _sep, fname = tail.rpartition("/")
        low = fname.lower()
        if low.endswith(TEX_EXT):
            skipped_tex += 1
            continue
        stem, dot, ext = fname.rpartition(".")
        if not dot:
            stem, ext = fname, ""
        # op_ 前缀要单独处理（它不含 bs_）
        new_stem = _rename_stem(stem, src_num, dst_num, False, False)
        new_fname = fname if new_stem is None else new_stem + ("." + ext if ext else "")
        new_name = pre_dst_p + (head + "/" if head else "") + new_fname
        if new_name != name:
            pkg.rename(name, new_name)
            renamed += 1
            if new_fname != fname:
                _log(log, "改名(部件)", "%s → %s" % (fname, new_fname))

    if renamed == 0 and skipped_tex == 0:
        return log, "这个包里没有可改名的模型文件"

    _log(log, "完成", "移动/改名 %d 个文件" % renamed)
    if skipped_tex:
        _log(log, "贴图未动",
             "%d 个 tex 留在原目录 %s（mrl3 里按原路径引用，搬走就找不到）"
             % (skipped_tex, src_dir))
    _log(log, "提示", "目标武器：%s %s" % (dst_dir, target.get("name") or ""))
    return log, None


# ----------------------------------------------------------------------
def strip_model(pkg, info):
    """去掉模型替换，只保留特效。

    留下：`wp/<wt>/<dir>/` 下的 evwp（决定 mEpvNo）、随刀 epv3、
          随刀 epvsp、`wp/<wt>/epv/`、`wp/<wt>/sound/` 的 epvsp/wwct、
          以及整个 `vfx/` 特效资源。
    删掉：模型/材质/物理/贴图、parts 部件模型、武器音效 wwbk。

    ★ vfx/ 下的 mod3/mrl3/tex 是**特效模型**，不能删 —— 只清 wp/ 下的。
    """
    log = []
    if not info.dir_name:
        return log, "包里没有武器模型目录，没法判断哪些是模型"

    abbr = info.abbr
    pre_dir = "wp/%s/%s/" % (abbr, info.dir_name)
    pre_parts = "wp/%s/parts/" % abbr
    pre_snd = "wp/%s/sound/" % abbr

    removed = 0
    kept = 0

    # ---- 1. 武器目录：白名单保留特效文件 ----
    for name in list(pkg.names()):
        if not name.startswith(pre_dir):
            continue
        low = name.lower()
        if low.endswith(EFFECT_EXT):
            kept += 1
            continue
        pkg.remove(name)
        removed += 1

    # ---- 2. 部件模型整个删 ----
    for name in list(pkg.names()):
        if name.startswith(pre_parts):
            pkg.remove(name)
            removed += 1

    # ---- 3. 武器音效（snd_xxx_bk.wwbk），epvsp/wwct 留着 ----
    for name in list(pkg.names()):
        if not name.startswith(pre_snd):
            continue
        low = name.lower()
        if low.endswith((".epvsp", ".wwct")):
            kept += 1
            continue
        pkg.remove(name)
        removed += 1

    if removed == 0:
        return log, "这个包里没有模型文件，已经是纯特效了"

    _log(log, "删除模型文件", "%d 个（mod3 / mrl3 / ctc / tex / parts / wwbk）" % removed)
    _log(log, "保留特效文件", "%d 个（evwp / epv3 / epvsp / wwct）" % kept)

    # ---- 4. 检查剩下的特效是否完整 ----
    left = pkg.names()
    has_evwp = any(n.lower().endswith(".evwp") for n in left)
    has_epv = any(n.lower().endswith(".epv3") for n in left)
    if not has_evwp:
        _log(log, "注意", "包里的 evwp 也被删了，游戏会用默认 evwp（mEpvNo=0）")
    if not has_epv:
        _log(log, "注意", "包里没有 epv3，特效可能不生效")
    return log, None


# ----------------------------------------------------------------------
# epv3 里的特效路径是「反斜杠 + 无扩展名」，例如 vfx\efx\wp\wp03\wp03_060
# epv3 / efx / mrl3 里的资源路径都是「反斜杠 + 无扩展名」：
#   vfx\efx\wp\wp03\wp03_060、wp\ham\HEIPAI\mod3\halo、wp\ham\HEIPAI\BM
_PATH_REF = re.compile(rb"(?:wp|vfx|Assets)[\\/][A-Za-z0-9_\\/\-\.]{3,}")
_ASSET_EXT = ("", ".efx", ".mod3", ".mrl3", ".tex", ".uvs")


def _path_refs(pkg, names, pattern=None):
    """从若干二进制文件里提取资源路径（正斜杠、无扩展名）。"""
    pat = pattern or _PATH_REF
    refs = set()
    for name in names:
        data = pkg.read(name)
        if not data:
            continue
        for m in pat.finditer(data):
            s = m.group().decode("latin1").replace("\\", "/").strip("/")
            if len(s) > 4:
                refs.add(s)
    return refs


def _epv_vfx_refs(pkg, epv_names):
    return _path_refs(pkg, epv_names)


def strip_weapon_effect(pkg, info, aggressive=False):
    """删掉武器特效，只保留随刀特效。

    两种力度：

    **保险（aggressive=False，默认）** —— 只删默认路径：
      1. `wp/<wt>/epv/*.epv3`
      2. `wp/<wt>/sound/*.epvsp`、`*.wwct`
      3. `vfx/efx/wp/<wpNN>/` 整个目录
      自定义路径（`wp/ham/HEIPAI/*.efx`）一律不动 —— 那里可能混着模型贴图。

    **彻底（aggressive=True）** —— 在上面基础上，再顺着 epv3 / efx 的引用
      把自定义目录里的特效资源（efx 及其引用的 mod3 / tex / uvs）也删掉。
      删除前会先算「mrl3 引用的贴图」当保护名单，模型贴图不会被动。

      ⚠️ 保护名单只覆盖 mrl3 直接引用的主贴图；如果特效和模型共用
      别的贴图，彻底模式有可能误删，拿不准就用保险模式。

    两种模式最后都会把 mEpvNo 归零 —— 不然它还指着刚删掉的
    `hm_wpXX_NN.epv3`，游戏找不到文件会卡在加载界面。
    """
    log = []
    if not info.abbr:
        return log, "没识别出武器类型"

    abbr = info.abbr
    pre_epv = "wp/%s/epv/" % abbr
    pre_snd = "wp/%s/sound/" % abbr

    names = set(pkg.names())

    # 标准路径：vfx/efx/wp/wp03/（hm_wp03 → wp03）
    base_name = info.epv_base or assets.epv_base(abbr) or ""
    m = re.match(r"^hm_(wp\d+)", base_name)
    pre_std = "vfx/efx/wp/%s/" % m.group(1) if m else ""

    # 删之前先把 epv3 读出来（彻底模式要提取引用 —— 删完就读不到了）
    del_epv = [n for n in names
               if n.startswith(pre_epv) and n.lower().endswith(".epv3")]
    epv_refs = _path_refs(pkg, del_epv) if aggressive else set()

    removed_epv = 0
    removed_std = 0
    for name in list(names):
        low = name.lower()
        if name.startswith(pre_epv) and low.endswith(".epv3"):
            pkg.remove(name)
            names.discard(name)
            removed_epv += 1
        elif name.startswith(pre_snd) and low.endswith((".epvsp", ".wwct")):
            pkg.remove(name)
            names.discard(name)
            removed_epv += 1
        elif pre_std and name.startswith(pre_std):
            pkg.remove(name)
            names.discard(name)
            removed_std += 1

    # ---- 彻底模式：按引用关系再清一遍自定义目录 ----
    removed_ref = 0
    protected_hits = 0
    if aggressive:
        # 保护名单：mrl3 引用的贴图（模型材质用的，绝对不能删）
        mrl3_files = [n for n in names if n.lower().endswith(".mrl3")]
        protected = _path_refs(pkg, mrl3_files)

        def is_protected(path):
            return path in protected or path.rsplit(".", 1)[0] in protected

        todo = set(epv_refs)
        # 顺着 efx 再挖两层（efx → mod3 / tex / uvs）
        for _ in range(2):
            efx_files = []
            for ref in list(todo):
                for ext in _ASSET_EXT:
                    cand = ref + ext
                    if cand in names and cand.lower().endswith(".efx"):
                        efx_files.append(cand)
            if not efx_files:
                break
            todo |= _path_refs(pkg, efx_files)

        # 待删 efx 所在目录下的其它 efx 也一起删（都是特效文件）
        efx_dirs = set()
        for ref in todo:
            for ext in _ASSET_EXT:
                cand = ref + ext
                if cand in names and cand.lower().endswith(".efx"):
                    efx_dirs.add(cand.rsplit("/", 1)[0])
        for d in efx_dirs:
            for n in list(names):
                if n.startswith(d + "/") and n.lower().endswith(".efx"):
                    todo.add(n.rsplit(".", 1)[0])

        for ref in sorted(todo):
            for ext in _ASSET_EXT:
                cand = ref + ext if ext else ref
                if cand not in names:
                    continue
                if is_protected(cand):
                    protected_hits += 1
                    names.discard(cand)
                    continue
                pkg.remove(cand)
                names.discard(cand)
                removed_ref += 1

    if removed_epv == 0 and removed_std == 0 and removed_ref == 0:
        return log, "这个包里没有武器特效可删"

    mode = "彻底" if aggressive else "保险"
    _log(log, "删除方式", mode)
    if removed_epv:
        _log(log, "删除武器特效", "%d 个（epv3 / epvsp / wwct）" % removed_epv)
    if removed_std:
        _log(log, "删除特效目录", "%s 整个（%d 个文件）" % (pre_std, removed_std))
    if removed_ref:
        _log(log, "删除特效资源", "%d 个（efx 及其引用的模型 / 贴图）" % removed_ref)
    if protected_hits:
        _log(log, "保护模型贴图", "%d 个（mrl3 引用到的，没删）" % protected_hits)

    # ---- 自定义路径的资源：保险模式下提示保留 ----
    custom = [n for n in pkg.names()
              if n.lower().endswith(".efx") and not n.startswith("vfx/efx/wp/")]
    if custom and not aggressive:
        dirs = sorted({n.rsplit("/", 1)[0] for n in custom})
        _log(log, "保留自定义特效", "%d 个 efx（%s）"
             % (len(custom), "、".join(dirs[:3]) + ("…" if len(dirs) > 3 else "")))
        _log(log, "提示", "这些不在 vfx/efx/wp 下，可能混着模型贴图，没动它们")

    # ---- 保留清单 ----
    kept_epv = [n for n in pkg.names()
                if n.startswith("wp/%s/" % abbr) and "/epv/" in n
                and n.lower().endswith(".epv3")]
    for n in kept_epv:
        _log(log, "保留随刀特效", n)

    # ---- mEpvNo 归零 ----
    pre_dir_all = "wp/%s/" % abbr
    for name in list(pkg.names()):
        if not name.startswith(pre_dir_all) or not name.lower().endswith(".evwp"):
            continue
        data = pkg.read(name)
        if data is None:
            continue
        try:
            cur = evwp.read_epv_no(data)
            if cur != 0:
                pkg.write(name, evwp.write_epv_no(data, 0))
                _log(log, "改 mEpvNo", "%s：%d → 0（回落到本体通用特效）" % (name, cur))
            else:
                _log(log, "保留", "%s：mEpvNo 已经是 0" % name)
        except evwp.EvwpError as exc:
            _log(log, "跳过", "%s：%s" % (name, exc))

    if not kept_epv:
        _log(log, "注意", "包里没有随刀特效")
    return log, None
