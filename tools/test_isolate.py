# -*- coding: utf-8 -*-
"""特效路径隔离：转独立特效时把默认路径的 efx 搬到按 id 隔离的目录。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import convert, detect, package  # noqa: E402

FAIL = []


def check(cond, msg):
    print(("  [OK] " if cond else "  [FAIL] ") + msg)
    if not cond:
        FAIL.append(msg)


SRC = r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘"

# ---- 1. 隔离名必须等长（epv3 里是等长字节替换） ----
print("隔离名规则：")
for base, eid, want in [("hm_wp03", 28, "wp28"), ("hm_wp03", 5, "wp05"),
                        ("hm_wp03", 99, "wp99"), ("hm_wp03", 111, "w111"),
                        ("hm_wp00", 17, "wp17")]:
    got = convert._isolate_key(base, eid)
    check(got == want and len(got) == 4,
          "%s + %d → %s（长度 %s）" % (base, eid, got, len(got) if got else 0))

check(convert._isolate_key("hm_wp03_28", 28) is None, "带 _NN 后缀的不做隔离（已经隔离过）")

# ---- 2. 搬目录 + 改引用 ----
print()
print("搬目录与改引用：")
pkg = package.Package(SRC)
pkg.write("vfx/efx/wp/wp03/test_a.efx", b"A" * 16)
pkg.write("vfx/efx/wp/wp03/sub/test_b.efx", b"B" * 16)
pkg.write("vfx/efx/wp/wp00/other.efx", b"C" * 16)
# 造一个含默认路径的假 epv3（真实包里没有 vfx/efx/wp/wp03 的引用）
FAKE = b"\x00\x00vfx\\efx\\wp\\wp03\\test_a\x00\x00"
pkg.write("wp/swo/epv/hm_wp03.epv3", FAKE)

log = []
moved = convert._move_effect_dir(pkg, "wp03", "wp28", log, "隔离特效目录")
check(moved == 2, "搬了 2 个文件（实际 %d）" % moved)
n = pkg.names()
check("vfx/efx/wp/wp28/test_a.efx" in n, "test_a.efx 搬到 wp28")
check("vfx/efx/wp/wp28/sub/test_b.efx" in n, "子目录也一起搬")
check("vfx/efx/wp/wp00/other.efx" in n, "别的武器组 wp00 不动")
check(not any(x.startswith("vfx/efx/wp/wp03/") for x in n), "wp03 目录已清空")

fixed = convert._rewrite_effect_refs(pkg, "wp03", "wp28", log)
check(fixed >= 1, "改了 %d 个 epv3（包里引用默认路径的都要改）" % fixed)
got = pkg.read("wp/swo/epv/hm_wp03.epv3")
check(got == b"\x00\x00vfx\\efx\\wp\\wp28\\test_a\x00\x00",
      "epv3 里的路径换成 wp28，且长度不变（%d → %d）" % (len(FAKE), len(got)))
for a, d in log:
    print("   ·", a, d)

# ---- 3. 反向还原 ----
print()
print("反向还原：")
log2 = []
moved2 = convert._move_effect_dir(pkg, "wp28", "wp03", log2, "还原特效目录")
check(moved2 == 2, "搬回 2 个文件")
check("vfx/efx/wp/wp03/test_a.efx" in pkg.names(), "回到 wp03")
fixed2 = convert._rewrite_effect_refs(pkg, "wp28", "wp03", log2)
check(fixed2 >= 1, "引用改回 wp03（%d 个）" % fixed2)
check(pkg.read("wp/swo/epv/hm_wp03.epv3") == FAKE, "epv3 内容完全还原")

# ---- 4. 真实包不受影响（没有默认路径目录时不动） ----
print()
print("真实包：")
pkg3 = package.Package(SRC)
info3 = detect.scan(pkg3)
before = set(pkg3.names())
log3, err = convert.to_standalone(pkg3, info3, 30)
check(err is None, "樱上幕帘转独立无错误：%s" % err)
check("vfx/huazha/wp03_000.efx" in pkg3.names(), "自定义路径的 efx 原地不动")
check(not any(x.startswith("vfx/efx/wp/wp30/") for x in pkg3.names()),
      "包里没有默认路径目录，不产生隔离目录")
for a, d in log3:
    if "隔离" in a or "改特效路径" in a:
        print("   ·", a, d)

print()
if FAIL:
    print("失败 %d 项" % len(FAIL))
    sys.exit(1)
print("ALL OK")
