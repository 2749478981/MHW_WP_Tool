# -*- coding: utf-8 -*-
"""核心逻辑自测：拿真实 MOD 包跑三种转换。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import assets, convert, detect, evwp, package, weapons  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


def show(info):
    for line in info.summary_lines():
        print("    " + line)
    for w in info.warnings:
        print("    ! " + w)
    for i in info.issues:
        print("    - " + i)


# ----------------------------------------------------------------------
print("=" * 72)
print("A. 通用特效包 → 独立特效（bali 双刀，eid=30）")
A = r"D:/mod3/084/bali/weapon"
if not os.path.isdir(A):
    print("  跳过（目录不存在）")
else:
    pkg = package.Package(A)
    info = detect.scan(pkg)
    show(info)
    check(info.abbr == "sou", "识别武器类型 sou")
    check(info.num == "030", "识别编号 030")
    check(info.form == "common", "判定为通用特效")
    log, err = convert.to_standalone(pkg, info, 30)
    check(err is None, "转换无错误：%s" % err)
    for a, d in log:
        print("    · %-14s %s" % (a, d))
    names = pkg.names()
    check("wp/sou/epv/hm_wp02_30.epv3" in names, "epv3 改名为 hm_wp02_30.epv3")
    check("wp/sou/sound/hm_wp02_30.epvsp" in names, "epvsp 改名为 hm_wp02_30.epvsp")
    d1 = pkg.read("wp/sou/sou030/mod/sou030.evwp")
    d2 = pkg.read("wp/sou/sou030/mod/sou_r030.evwp")
    check(evwp.read_epv_no(d1) == 30, "sou030.evwp mEpvNo = 30")
    check(evwp.read_epv_no(d2) == 30, "sou_r030.evwp mEpvNo = 30")

    # 再转回来
    info2 = detect.scan(pkg)
    check(info2.form == "standalone" and info2.effect_id == 30,
          "重新扫描判定为独立特效 id=30")
    log2, err2 = convert.to_common(pkg, info2)
    check(err2 is None, "转回通用无错误")
    names2 = pkg.names()
    check("wp/sou/epv/hm_wp02.epv3" in names2, "epv3 改回 hm_wp02.epv3")
    check(evwp.read_epv_no(pkg.read("wp/sou/sou030/mod/sou030.evwp")) == 0,
          "mEpvNo 归零")

# ----------------------------------------------------------------------
print()
print("=" * 72)
print("B. 独立特效包 → 通用（樱上幕帘，eid=28）")
B = r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘"
if not os.path.isdir(B):
    print("  跳过（目录不存在）")
else:
    pkg = package.Package(B)
    info = detect.scan(pkg)
    show(info)
    check(info.abbr == "swo", "识别武器类型 swo")
    check(info.num == "028", "识别编号 028")
    check(info.form == "standalone", "判定为独立特效")
    check(info.effect_id == 28, "特效 id = 28")

    # 塞一个 wwct 进去，验证它也跟着改名（写完要重新扫描，info 才会收录）
    pkg.write("wp/swo/sound/hm_wp03_28_epvsp_snd_ct.wwct", b"fake")
    info = detect.scan(pkg)

    log, err = convert.to_common(pkg, info)
    check(err is None, "转换无错误：%s" % err)
    for a, d in log:
        print("    · %-14s %s" % (a, d))
    names = pkg.names()
    check("wp/swo/epv/hm_wp03.epv3" in names, "epv3 改回 hm_wp03.epv3")
    check("wp/swo/sound/hm_wp03.epvsp" in names,
          "epvsp 改回 hm_wp03.epvsp（独立→通用也要带 epvsp）")
    check("wp/swo/sound/hm_wp03_epvsp_snd_ct.wwct" in names,
          "wwct 跟着改成通用名")
    check(evwp.read_epv_no(pkg.read("wp/swo/swo028/mod/swo028.evwp")) == 0,
          "swo028.evwp mEpvNo = 0")
    check(evwp.read_epv_no(pkg.read("wp/swo/swo028/mod/saya028.evwp")) == 0,
          "saya028.evwp mEpvNo = 0")
    # 随刀特效不该被动
    check("wp/swo/swo028/epv/swo028.epv3" in names, "随刀特效 swo028.epv3 保留")

    # 再转回独立，确认 epvsp 又变回 _28
    info_b = detect.scan(pkg)
    log, err = convert.to_standalone(pkg, info_b, 28)
    check(err is None, "再转独立无错误")
    names = pkg.names()
    check("wp/swo/epv/hm_wp03_28.epv3" in names, "epv3 回到 hm_wp03_28.epv3")
    check("wp/swo/sound/hm_wp03_28.epvsp" in names, "epvsp 回到 hm_wp03_28.epvsp")
    check("wp/swo/sound/hm_wp03_28_epvsp_snd_ct.wwct" in names,
          "wwct 回到独立名")

# ----------------------------------------------------------------------
print()
print("=" * 72)
print("C. 替换武器模型：swo028 → swo032")
if os.path.isdir(B):
    pkg = package.Package(B)
    info = detect.scan(pkg)
    tgt = weapons.find_by_dir("swo032", "swo")
    print("    目标：", tgt and (tgt["name"], tgt["model"]))
    tmodel = {"dirname": "swo032", "name": tgt["name"] if tgt else ""}
    log, err = convert.replace_weapon(pkg, info, tmodel)
    check(err is None, "替换无错误：%s" % err)
    for a, d in log:
        print("    · %-14s %s" % (a, d))
    names = pkg.names()
    want = [
        "wp/swo/swo032/mod/swo032.mod3",
        "wp/swo/swo032/mod/swo032.mrl3",
        "wp/swo/swo032/mod/saya032.mod3",
        "wp/swo/swo032/mod/saya032.mrl3",
        "wp/swo/swo032/epv/swo032.epv3",
        # ★ 贴图不改名也不搬，留在原目录
        "wp/swo/swo028/huazha/BML.tex",
        # ★ 独立特效的 epvid 跟随目标编号 28 → 32
        "wp/swo/epv/hm_wp03_32.epv3",
        "wp/swo/sound/hm_wp03_32.epvsp",
    ]
    for w in want:
        check(w in names, "存在 " + w)
    check(evwp.read_epv_no(pkg.read("wp/swo/swo032/mod/swo032.evwp")) == 32,
          "替换后 mEpvNo = 32（跟随目标武器编号）")
    check("wp/swo/epv/hm_wp03_28.epv3" not in names, "旧 id 的 epv3 已不存在")
    check("wp/swo/swo032/huazha/BML.tex" not in names, "贴图没有跟着搬到 swo032")
    old_mod = [n for n in names if n.startswith("wp/swo/swo028/mod/")]
    check(all(n.lower().endswith(".tex") for n in old_mod),
          "swo028/mod 下没有非贴图文件（现有 %d 个）" % len(old_mod))
    texs = [n for n in names if n.lower().endswith(".tex") and "/swo032/" in n]
    check(not texs, "新目录里没有贴图")

# ----------------------------------------------------------------------
print()
print("=" * 72)
print("D. 特效文件名规则")
cases = [(1, "hm_wp03_01"), (28, "hm_wp03_28"), (111, "hm_wp03_111"), (0, "hm_wp03")]
for eid, want in cases:
    got = assets.effect_filename("swo", eid)
    check(got == want, "id=%s → %s（实际 %s）" % (eid, want, got))
for stem, want_base, want_id in [("hm_wp03", "hm_wp03", None),
                                 ("hm_wp03_28", "hm_wp03", 28),
                                 ("hm_wp03_111", "hm_wp03", 111)]:
    b, i = assets.split_effect_name(stem, "swo")
    check((b, i) == (want_base, want_id), "解析 %s → (%s,%s)" % (stem, b, i))

print()
print("=" * 72)
if FAIL:
    print("失败 %d 项：" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL OK")
