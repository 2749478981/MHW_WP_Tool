# -*- coding: utf-8 -*-
"""验证「删武器特效、保留随刀特效」。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import convert, detect, evwp, package  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


SRC = r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘"
pkg = package.Package(SRC)
info = detect.scan(pkg)
print("转换前 %d 个文件，mEpvNo=%s" % (len(pkg.names()), set(info.evwp_files.values())))

models_before = [x for x in pkg.names()
                 if x.startswith("wp/") and x.lower().endswith((".mod3", ".mrl3", ".ctc", ".tex"))]

log, err = convert.strip_weapon_effect(pkg, info)
check(err is None, "无错误：%s" % err)
for a, d in log:
    print("   ·", a, d)

n = pkg.names()

# 1. 武器特效（wp/<wt>/epv/ 和 wp/<wt>/sound/）都没了
check(not [x for x in n if x.startswith("wp/swo/epv/")], "wp/swo/epv/ 已清空")
check(not [x for x in n if x.startswith("wp/swo/sound/")], "wp/swo/sound/ 已清空")

# 2. 随刀特效保留
check("wp/swo/swo028/epv/swo028.epv3" in n, "随刀特效 swo028.epv3 保留")

# 3. 随刀目录里那份武器特效 epvsp 副本也删了
# 随刀目录里的东西一律保留（可能是随刀特效的音效，也可能是作者放错位置的）
check("wp/swo/swo028/sound/hm_wp03_28.epvsp" in n,
      "随刀目录里的 epvsp 副本保留（保守策略）")

# 4. mEpvNo 归零
check(evwp.read_epv_no(pkg.read("wp/swo/swo028/mod/swo028.evwp")) == 0,
      "mEpvNo 归零")
check(evwp.read_epv_no(pkg.read("wp/swo/swo028/mod/saya028.evwp")) == 0,
      "saya evwp mEpvNo 也归零")

# 5. 模型和 vfx 一点没动
models = [x for x in n if x.startswith("wp/")
          and x.lower().endswith((".mod3", ".mrl3", ".ctc", ".tex"))]
check(sorted(models) == sorted(models_before),
      "武器模型文件一个没动（%d 个）" % len(models))
# vfx：只删默认路径 vfx/efx/wp/wpNN/，自定义路径一律保留（可能混着模型贴图）
vfx_left = [x for x in n if x.startswith("vfx/")]
check(any(x.endswith(".efx") for x in vfx_left),
      "自定义路径的 efx 保留（%d 个）" % len([x for x in vfx_left if x.endswith(".efx")]))
check(len([x for x in vfx_left if x.startswith("vfx/084/")]) > 0,
      "vfx/084 下的贴图和模型保留（%d 个）"
      % len([x for x in vfx_left if x.startswith("vfx/084/")]))

# 标准路径 vfx/efx/wp/wp03/ 要整目录删
pkg2 = package.Package(SRC)
pkg2.write("vfx/efx/wp/wp03/wp03_060.efx", b"\x00" * 16)
pkg2.write("vfx/efx/wp/wp00/wp00_999.efx", b"\x00" * 16)
info2 = detect.scan(pkg2)
convert.strip_weapon_effect(pkg2, info2)
n2 = pkg2.names()
check("vfx/efx/wp/wp03/wp03_060.efx" not in n2, "vfx/efx/wp/wp03/ 整个删掉")
check("vfx/efx/wp/wp00/wp00_999.efx" in n2, "别的武器组 vfx/efx/wp/wp00/ 不动")

# 5b. 彻底模式：自定义目录的 efx 也要删，但 mrl3 引用的贴图要保住
pkg3 = package.Package(SRC)
info3 = detect.scan(pkg3)
convert.strip_weapon_effect(pkg3, info3, aggressive=True)
n3 = pkg3.names()
check(not [x for x in n3 if x.endswith(".efx")],
      "彻底模式删掉自定义 efx（剩 %d）" % len([x for x in n3 if x.endswith(".efx")]))
check("wp/swo/swo028/epv/swo028.epv3" in n3, "彻底模式也保留随刀特效")

# 6. 保存 + 读回
out = os.path.join(tempfile.mkdtemp(prefix="stripwp_"), "o.zip")
pkg.save(out)
check(os.path.getsize(out) > 0, "能保存（%d KB）" % (os.path.getsize(out) // 1024))

pkg2 = package.Package(out)
info2 = detect.scan(pkg2)
check(info2.form == "common",
      "回读判定为通用特效（form=%s, id=%s）" % (info2.form, info2.effect_id))

print()
if FAIL:
    print("失败 %d 项" % len(FAIL))
    sys.exit(1)
print("ALL OK")
