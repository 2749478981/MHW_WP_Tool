# -*- coding: utf-8 -*-
"""纯特效包（没有模型目录）转独立特效。

这类包只有 wp/<wt>/epv/ 和 wp/<wt>/sound/，没有 wp/<wt>/<dir>/，
所以补 evwp 时必须由外部指定「这套特效属于哪把武器」。
"""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import convert, detect, evwp, package  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


SRC = r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘/nativePC"
TMP = tempfile.mkdtemp(prefix="fxonly_")
ZIP = os.path.join(TMP, "fxonly.zip")

# ---- 造一个纯特效包 ----
items = ["wp/swo/epv/hm_wp03_28.epv3", "wp/swo/sound/hm_wp03_28.epvsp"]
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
    for rel in items:
        p = os.path.join(SRC, rel.replace("/", os.sep))
        if os.path.exists(p):
            z.write(p, "nativePC/" + rel)
        else:
            raise SystemExit("缺文件：" + p)
print("测试包：%d 个文件，%d KB" % (len(items), os.path.getsize(ZIP) // 1024))

# ---- 1. 识别 ----
pkg = package.Package(ZIP)
info = detect.scan(pkg)
print()
print("识别：", info.title, "|", info.form_cn, "| dir =", repr(info.dir_name))
check(info.abbr == "swo", "从 epv3 文件名推出武器类型 swo")
check(info.dir_name is None, "确认没有模型目录")
check(info.form == "standalone" and info.effect_id == 28,
      "从 epv3 文件名推出独立特效 id=28")
check(not info.evwp_files, "确认包里没有 evwp")
check("纯特效" in info.title, "标题标明是纯特效包")

# ---- 2. 不给所属武器应该报错 ----
log, err = convert.to_standalone(pkg, info, 30)
check(err is not None and "哪把武器" in err, "不给所属武器时明确报错")
check(not any(n.endswith("_30.epv3") for n in pkg.names()), "报错时没有改动文件")

# ---- 3. 指定所属武器 ----
log, err = convert.to_standalone(pkg, info, 30, owner_dir="swo032")
check(err is None, "指定 swo032 后转换成功")
for a, d in log:
    print("   ·", a, d)

n = pkg.names()
check("wp/swo/epv/hm_wp03_30.epv3" in n, "epv3 改成 hm_wp03_30")
check("wp/swo/sound/hm_wp03_30.epvsp" in n, "epvsp 改成 hm_wp03_30")
check("wp/swo/swo032/mod/swo032.evwp" in n, "补入 swo032.evwp")
check("wp/swo/swo032/mod/saya032.evwp" in n, "补入 saya032.evwp")
check(evwp.read_epv_no(pkg.read("wp/swo/swo032/mod/swo032.evwp")) == 30,
      "补入的 evwp mEpvNo = 30")

# ---- 3b. 连 epv3 都没有的包：应该从内置补一份 ----
pkg_n = package.Package(ZIP)
info_n = detect.scan(pkg_n)
# 把 epv3/epvsp 删掉，模拟「只有 vfx 特效资源」的包
for n in list(pkg_n.names()):
    if n.lower().endswith((".epv3", ".epvsp")):
        pkg_n.remove(n)
info_n = detect.scan(pkg_n)
check(info_n.abbr is None, "去掉 epv3 后确实推不出武器类型")
log, err = convert.to_standalone(pkg_n, info_n, 32, owner_dir="swo032")
check(err is None, "无 epv3 也能转（从所属武器推类型）")
check("wp/swo/epv/hm_wp03_32.epv3" in pkg_n.names(), "自动补入 epv3")
check("wp/swo/sound/hm_wp03_32.epvsp" in pkg_n.names(), "自动补入 epvsp")
check(evwp.read_epv_no(pkg_n.read("wp/swo/swo032/mod/swo032.evwp")) == 32,
      "补入的 evwp mEpvNo = 32（和所选武器编号一致）")

# ---- 4. 保存 + 读回 ----
out = os.path.join(TMP, "out.zip")
pkg.save(out)
check(os.path.getsize(out) > 0, "能保存（%d KB）" % (os.path.getsize(out) // 1024))

pkg2 = package.Package(out)
info2 = detect.scan(pkg2)
check(info2.form == "standalone" and info2.effect_id == 30,
      "回读仍是独立特效 id=30（%s %s）" % (info2.form, info2.effect_id))
check(info2.dir_name == "swo032", "回读能识别出补进去的模型目录 swo032")

print()
if FAIL:
    print("失败 %d 项" % len(FAIL))
    sys.exit(1)
print("ALL OK")
