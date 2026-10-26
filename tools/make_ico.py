# -*- coding: utf-8 -*-
"""把 icon/logo.svg 渲染成多尺寸 png 并合成 logo.ico。

用 Edge 无头模式渲染（不需要额外装 cairosvg）。
"""
import os
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ICON = os.path.join(os.path.dirname(HERE), "icon")
SVG = os.path.join(ICON, "logo.svg")
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
SIZES = [256, 128, 64, 48, 32, 16]


def render(size):
    html = os.path.join(ICON, "_shot_%d.html" % size)
    png = os.path.join(ICON, "_shot_%d.png" % size)
    with open(html, "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html><html><body style="margin:0;background:transparent">'
            '<img src="logo.svg" width="%d" height="%d" style="display:block">'
            "</body></html>" % (size, size)
        )
    subprocess.run([
        EDGE, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--default-background-color=00000000",
        "--force-device-scale-factor=1",
        "--window-size=%d,%d" % (size, size),
        "--screenshot=%s" % png,
        "file:///" + html.replace("\\", "/"),
    ], capture_output=True)
    os.remove(html)
    if not os.path.exists(png):
        raise SystemExit("渲染失败：%d" % size)
    return Image.open(png).convert("RGBA")


def main():
    if not os.path.exists(EDGE):
        raise SystemExit("找不到 Edge：%s" % EDGE)

    imgs = {}
    for s in SIZES:
        im = render(s)
        if im.size != (s, s):
            im = im.crop((0, 0, min(s, im.width), min(s, im.height)))
        imgs[s] = im
        print("渲染 %dx%d" % im.size)

    # 用 256 当主图，PIL 会按 sizes 生成其余尺寸
    big = imgs[256]
    ico = os.path.join(ICON, "logo.ico")
    big.save(ico, format="ICO", sizes=[(s, s) for s in SIZES])
    print("生成 %s（%d 字节）" % (ico, os.path.getsize(ico)))

    # 单独留一份 256 png 方便预览
    imgs[256].save(os.path.join(ICON, "logo_256.png"))

    for s in SIZES:
        p = os.path.join(ICON, "_shot_%d.png" % s)
        if os.path.exists(p):
            os.remove(p)

    # 自检：ico 里各尺寸都在
    with Image.open(ico) as im:
        got = sorted(im.ico.sizes())
    print("ico 内含尺寸：", got)
    want = sorted((s, s) for s in SIZES)
    print("OK" if got == want else "尺寸不完整：期望 %s" % want)


if __name__ == "__main__":
    sys.exit(main())
