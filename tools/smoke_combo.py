# -*- coding: utf-8 -*-
"""验证「特效转换 + 替换模型」可以同时做。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.app import App, EFFECT_COMMON2STAND, EFFECT_NONE, EFFECT_STAND2COMMON  # noqa: E402

SRC = r"C:/Users/x1887/AppData/Local/Temp/wp_tool_shot/test_sakura.zip"

app = App()
app.geometry("+40+20")
app.lift()
app.attributes("-topmost", True)
state = {"t0": 0.0}


def step1():
    app.var_path.set(SRC)
    app.load_package()
    app.update()
    print("识别:", app.info.brief()["form"], "| 自动特效:", app.var_effect.get())
    print("输出:", os.path.basename(app.var_out.get()))

    # 只替换、不改特效 —— 验证 epvid 跟随目标编号
    app.var_effect.set(EFFECT_NONE)
    app.var_replace.set(True)
    tgt = next(x for x in app._target_items if x["dirname"] == "swo032")
    app._on_target_picked(tgt)
    app._sync_state()
    print("只替换 输出:", os.path.basename(app.var_out.get()))
    print("epvid 提示:", app.lbl_replace_hint.cget("text"))

    app.after(200, step2)


def step2():
    state["t0"] = time.time()
    app.preview()
    app.after(300, step3)


def step3():
    if app._busy and time.time() - state["t0"] < 20:
        app.after(200, step3)
        return
    txt = app.txt_log.get("1.0", "end").strip()
    print("--- 日志 ---")
    for line in txt.splitlines()[-24:]:
        print("   ", line)
    try:
        from PIL import ImageGrab
        app.lift(); app.update(); time.sleep(0.4)
        x, y = app.winfo_rootx(), app.winfo_rooty()
        w, h = int(app.winfo_width() * 1.5), int(app.winfo_height() * 1.5)
        img = ImageGrab.grab((x, y, x + w, y + h))
        out = os.path.join(os.environ.get("TEMP", "."), "wp_tool_shot", "combo.png")
        img.save(out)
        print("截图:", out, img.size)
    except Exception as exc:
        print("截图失败:", exc)
    print("SMOKE OK")
    app.destroy()


app.after(120, step1)
app.mainloop()
