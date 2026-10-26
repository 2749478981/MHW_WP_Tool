# -*- coding: utf-8 -*-
"""验证「只保留特效」：模型文件应全部删掉，特效文件应完整保留。"""
import os
import sys

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

before = pkg.names()
print("转换前 %d 个文件" % len(before))
models = [n for n in before if n.lower().endswith((".mod3", ".mrl3", ".ctc", ".tex", ".wwbk"))]
print("其中模型类 %d 个" % len(models))

log, err = convert.strip_model(pkg, info)
check(err is None, "strip 无错误：%s" % err)
for a, d in log:
    print("   ·", a, d)

after = pkg.names()
print("转换后 %d 个文件" % len(after))

# 1. 模型文件全没了
left_models = [n for n in after
               if n.startswith("wp/") and n.lower().endswith((".mod3", ".mrl3", ".ctc", ".tex"))]
check(not left_models, "wp/ 下没有模型文件了（剩 %d）" % len(left_models))

# 2. 特效文件还在
check(any(n.endswith(".evwp") for n in after), "evwp 还在")
check("wp/swo/epv/hm_wp03_28.epv3" in after, "通用/独立 epv3 还在")
check("wp/swo/sound/hm_wp03_28.epvsp" in after, "epvsp 还在")
check("wp/swo/swo028/epv/swo028.epv3" in after, "随刀特效还在")

# 3. vfx 特效资源没被误删（里面的 mod3/mrl3/tex 是特效模型）
vfx = [n for n in after if n.startswith("vfx/")]
vfx_models = [n for n in vfx if n.lower().endswith((".mod3", ".mrl3", ".tex"))]
check(len(vfx) > 0 and len(vfx_models) > 0,
      "vfx 特效资源保留（%d 个文件，含 %d 个模型）" % (len(vfx), len(vfx_models)))

# 4. 武器音效被删
check(not any(n.lower().endswith(".wwbk") for n in after), "武器音效 wwbk 已删")

# 5. evwp 内容没被破坏
data = pkg.read("wp/swo/swo028/mod/swo028.evwp")
check(evwp.is_evwp(data) and evwp.read_epv_no(data) == 28, "evwp 完好，mEpvNo=28")

# 6. 再扫一次，还能识别
info2 = detect.scan(pkg)
check(info2.abbr == "swo" and info2.num == "028", "重新扫描仍能识别武器")

# 7. 保存后能读回
import tempfile  # noqa: E402
out = os.path.join(tempfile.mkdtemp(prefix="strip_"), "out.zip")
pkg.save(out)
check(os.path.getsize(out) > 0, "能保存（%d KB）" % (os.path.getsize(out) // 1024))

print()
if FAIL:
    print("失败 %d 项" % len(FAIL))
    sys.exit(1)
print("ALL OK")
