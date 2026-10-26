# -*- coding: utf-8 -*-
"""端到端：文件夹 → 打成 zip → 读 zip → 转换 → 存 zip → 再读回来校验。"""
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import convert, detect, evwp, package, weapons  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


SRC = r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘"
TMP = tempfile.mkdtemp(prefix="wptool_")
ZIP_IN = os.path.join(TMP, "in.zip")
ZIP_OUT = os.path.join(TMP, "out.zip")

# ---- 1. 把文件夹打成 zip（模拟真实 MOD 包）----
print("=" * 70)
print("1. 打 zip")
root = os.path.join(SRC, "nativePC")
with zipfile.ZipFile(ZIP_IN, "w", zipfile.ZIP_DEFLATED) as z:
    for cur, _d, files in os.walk(root):
        for f in files:
            full = os.path.join(cur, f)
            rel = "nativePC/" + os.path.relpath(full, root).replace("\\", "/")
            z.write(full, rel)
print("   zip 条目：", len(zipfile.ZipFile(ZIP_IN).namelist()))

# ---- 2. 读 zip ----
print()
print("2. 读 zip 并识别")
pkg = package.Package(ZIP_IN)
info = detect.scan(pkg)
print("   前缀：", repr(pkg.prefix), " 文件：", len(pkg.names()))
print("   识别：", info.title, "|", info.form_cn, "| id=", info.effect_id)
check(pkg.prefix == "nativePC/", "识别出 nativePC 前缀")
check(info.form == "standalone" and info.effect_id == 28, "识别为独立特效 28")

# ---- 3. 转通用 ----
print()
print("3. 独立 → 通用")
log, err = convert.to_common(pkg, info)
check(err is None, "转换成功 %s" % err)
for a, d in log:
    print("   ·", a, d)

# ---- 4. 存 zip ----
print()
print("4. 存 zip")
pkg.save(ZIP_OUT)
check(os.path.isfile(ZIP_OUT), "输出文件存在（%d KB）" % (os.path.getsize(ZIP_OUT) // 1024))
names = zipfile.ZipFile(ZIP_OUT).namelist()
check("nativePC/wp/swo/epv/hm_wp03.epv3" in names, "zip 内路径带 nativePC")
check("nativePC/wp/swo/swo028/mod/swo028.mod3" in names, "模型文件在")
# vfx 目录要原样保留
check(any(n.startswith("nativePC/vfx/") for n in names), "vfx 资源保留")

# ---- 5. 读回来校验 ----
print()
print("5. 读回输出包")
pkg2 = package.Package(ZIP_OUT)
info2 = detect.scan(pkg2)
check(info2.form == "common", "回读判定为通用特效（%s）" % info2.form)
check(evwp.read_epv_no(pkg2.read("wp/swo/swo028/mod/swo028.evwp")) == 0,
      "swo028.evwp mEpvNo = 0")
check("wp/swo/epv/hm_wp03.epv3" in pkg2.names(), "epv3 是通用名")
check(pkg2.names() == pkg.names(), "文件集合与内存中一致")

# ---- 6. 再转成独立特效 id=111（三位数）----
print()
print("6. 通用 → 独立 id=111")
info3 = detect.scan(pkg2)
log, err = convert.to_standalone(pkg2, info3, 111)
check(err is None, "转换成功 %s" % err)
check("wp/swo/epv/hm_wp03_111.epv3" in pkg2.names(), "生成 hm_wp03_111.epv3")
check(evwp.read_epv_no(pkg2.read("wp/swo/swo028/mod/swo028.evwp")) == 111,
      "mEpvNo = 111")
ZIP_OUT2 = os.path.join(TMP, "out111.zip")
pkg2.save(ZIP_OUT2)
check(os.path.getsize(ZIP_OUT2) > 0, "三位数 id 的包能存")

# ---- 7. 缺 evwp / epv 的包：从内置补 ----
print()
print("7. 只有模型、没有 evwp/epv 的包（补内置）")
ZIP_MIN = os.path.join(TMP, "min.zip")
with zipfile.ZipFile(ZIP_MIN, "w") as z:
    z.writestr("nativePC/wp/swo/swo032/mod/swo032.mod3", b"\x00" * 16)
    z.writestr("nativePC/wp/swo/swo032/mod/swo032.mrl3", b"\x00" * 16)
pkg3 = package.Package(ZIP_MIN)
info4 = detect.scan(pkg3)
print("   识别：", info4.title, "| evwp", len(info4.evwp_files), "| epv", len(info4.epv_files))
check(not info4.evwp_files, "确认包里没有 evwp")
log, err = convert.to_standalone(pkg3, info4, 32)
check(err is None, "转换成功 %s" % err)
for a, d in log:
    print("   ·", a, d)
n3 = pkg3.names()
check("wp/swo/swo032/mod/swo032.evwp" in n3, "补入了内置 evwp")
check("wp/swo/swo032/mod/saya032.evwp" in n3, "补入了 saya evwp")
check("wp/swo/epv/hm_wp03_32.epv3" in n3, "补入了内置 epv3")
check(evwp.read_epv_no(pkg3.read("wp/swo/swo032/mod/swo032.evwp")) == 32,
      "补入的 evwp mEpvNo = 32")

# ---- 8. 替换武器（zip 输入）----
print()
print("8. 替换武器 swo028 → bs_swo003")
pkg4 = package.Package(ZIP_IN)
info5 = detect.scan(pkg4)
tgt = {"dirname": "bs_swo003", "name": weapons.find_by_dir("bs_swo003", "swo")["name"]}
log, err = convert.replace_weapon(pkg4, info5, tgt)
check(err is None, "替换成功 %s" % err)
n4 = pkg4.names()
print("   样例：", [x for x in n4 if "/mod/" in x][:6])
check("wp/swo/bs_swo003/mod/bs_swo003.mod3" in n4, "改成组合模型文件名")
check("wp/swo/bs_swo003/mod/bs_saya003.mod3" in n4, "saya 也跟着改")
check("wp/swo/bs_swo003/epv/bs_swo003.epv3" in n4, "随刀特效改成 bs_swo003")
texs_old = [x for x in n4 if x.lower().endswith(".tex") and "/swo028/" in x]
texs_new = [x for x in n4 if x.lower().endswith(".tex") and "/bs_swo003/" in x]
check(len(texs_old) == 4, "贴图 4 个留在原目录 swo028（%d）" % len(texs_old))
check(not texs_new, "贴图没有跟着搬到新目录")

print()
print("=" * 70)
print("临时目录：", TMP)
if FAIL:
    print("失败 %d 项：" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL OK")
