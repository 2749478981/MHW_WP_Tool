# -*- coding: utf-8 -*-
"""界面冒烟测试：建窗口 → 载入真实包 → 预览 → 截图 → 关闭。

必须走 mainloop，否则 worker 线程里的 self.after 会报
"main thread is not in main loop"。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.app import App  # noqa: E402

OUT = os.path.join(os.environ.get("TEMP", "."), "wp_tool_shot")
os.makedirs(OUT, exist_ok=True)

SRC = sys.argv[1] if len(sys.argv) > 1 else r"D:/mod3/084/huazha/独立特效+优化/樱上幕帘"
TAG = sys.argv[2] if len(sys.argv) > 2 else "main"

app = App()
app.geometry("+40+20")
app.lift()
app.attributes("-topmost", True)
app.focus_force()
state = {"t0": 0.0, "shot": None}


def shot(name):
    try:
        from PIL import ImageGrab
        app.update_idletasks()
        # ★ 窗口坐标是逻辑像素，ImageGrab 用物理像素，要乘 tk scaling
        sc = float(app.tk.call("tk", "scaling"))
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = int(app.winfo_width() * sc), int(app.winfo_height() * sc)
        img = ImageGrab.grab((x, y, x + w, y + h))
        p = os.path.join(OUT, name + ".png")
        img.save(p)
        print("截图：", p, img.size)
        state["shot"] = p
    except Exception as exc:
        print("截图失败：", exc)


def step1():
    app.var_path.set(SRC)
    app.load_package()
    app.update()
    b = app.info.brief()
    print("识别：", b["title"], "|", b["form"], "|", b["mepv"])
    print("特效ID默认：", app.var_eid.get())
    print("目标候选：", len(app._target_items), "|", app.var_target.get()[:46])
    print("输出：", app.var_out.get())
    app.after(200, step2)


def step2():
    shot(TAG + "_1_idle")
    print("--- 预览 ---")
    state["t0"] = time.time()
    app.preview()
    app.after(300, step3)


def step3():
    if app._busy and time.time() - state["t0"] < 20:
        app.after(200, step3)
        return
    print("日志行数：", int(app.txt_log.index("end-1c").split(".")[0]))
    txt = app.txt_log.get("1.0", "end")
    for line in txt.strip().splitlines()[-8:]:
        print("   ", line)
    shot(TAG + "_2_preview")

    # 切到替换模式看一眼
    app.var_mode.set("replace")
    app._sync_mode_state()
    app.update()
    app.after(150, step4)


def step4():
    shot(TAG + "_3_replace")
    print("SMOKE OK")
    app.destroy()


app.after(120, step1)
app.mainloop()
