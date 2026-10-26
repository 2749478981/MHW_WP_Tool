# -*- coding: utf-8 -*-
"""主界面。"""
import os
import re
import sys
import tempfile
import threading
import tkinter as tk
import traceback
import webbrowser
from tkinter import filedialog, messagebox, ttk

from core import assets, convert, detect, evwp, package, paths, updater, version, weapons
from .about import AboutWindow

FONT = ("Microsoft YaHei UI", 9)
FONT_S = ("Microsoft YaHei UI", 8)
FONT_B = ("Microsoft YaHei UI", 10, "bold")
FONT_MONO = ("Consolas", 9)

BG = "#f6f7f9"
CARD = "#ffffff"
LINE = "#d8dbe0"
TEXT = "#1f2328"
MUTED = "#6b7280"
OK = "#1a7f37"
WARN = "#9a6700"
ERR = "#cf222e"
ACCENT = "#2f6feb"

BILI_URL = version.BILI_URL
AUTHOR = version.AUTHOR

EFFECT_NONE = "none"
EFFECT_COMMON2STAND = "c2s"
EFFECT_STAND2COMMON = "s2c"
EFFECT_STRIP_WP = "stripwp"

STRIP_SAFE = "safe"
STRIP_FULL = "full"

MODEL_KEEP = "keep"
MODEL_REPLACE = "replace"
MODEL_STRIP = "strip"


def dpi_aware():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MHW 武器 MOD 工具 — 特效转换 / 模型替换")
        # ★ 用「屏幕百分比」定尺寸，别用绝对值。
        #   源码运行时 tk 拿的是逻辑尺寸（1536x864），exe 里 DPI aware 生效后
        #   拿到的是物理尺寸（2304x1296），同一组绝对像素在两边视觉大小差 1.5 倍。
        #   按百分比算，两边都得到差不多大的窗口。
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * 0.72), int(sh * 0.84)
        self.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, max(0, (sh - h) // 4)))
        self.minsize(int(sw * 0.55), int(sh * 0.5))
        self.configure(bg=BG)

        self.pkg = None
        self.info = None
        self._busy = False

        self.var_path = tk.StringVar()
        self.var_effect = tk.StringVar(value=EFFECT_COMMON2STAND)
        self.var_eid = tk.StringVar(value="")
        self.var_model = tk.StringVar(value=MODEL_KEEP)
        self.var_strip_mode = tk.StringVar(value=STRIP_SAFE)
        self.var_target = tk.StringVar()
        self.var_out = tk.StringVar()
        self.var_overwrite = tk.BooleanVar(value=False)

        self._target_items = []
        self._eid_synced = False
        self._owner_item = None
        self._build()
        self._sync_state()

    # ------------------------------------------------------------------
    def _build(self):
        # ===== 顶部标题 =====
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=16, pady=(8, 2))
        tk.Label(head, text="MHW 武器 MOD 工具", font=("Microsoft YaHei UI", 13, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(head, text="v" + version.VERSION, font=FONT_S, bg=BG,
                 fg=MUTED).pack(side="left", padx=(8, 0), pady=(4, 0))
        tk.Label(head, text="通用特效 ⇄ 独立特效 · 替换武器模型",
                 font=FONT_S, bg=BG, fg=MUTED).pack(side="left", padx=(10, 0), pady=(4, 0))

        # ---- 署名 + B站链接（放右边，不占左栏空间）----
        credit = tk.Frame(head, bg=BG)
        credit.pack(side="right")
        tk.Label(credit, text="by 真夜中のloop", font=FONT_S,
                 bg=BG, fg=MUTED).pack(side="left")
        self.lnk_bili = tk.Label(credit, text="B站主页", font=("Microsoft YaHei UI", 8, "underline"),
                                 bg=BG, fg=ACCENT, cursor="hand2")
        self.lnk_bili.pack(side="left", padx=(8, 0))
        self.lnk_bili.bind("<Button-1>", lambda _e: self._open_bili())
        self._tip = None
        self.lnk_bili.bind("<Enter>", lambda _e: self._show_tip(BILI_URL))
        self.lnk_bili.bind("<Leave>", lambda _e: self._hide_tip())

        # ===== 左右分栏 =====
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        main.columnconfigure(0, weight=0, minsize=600)
        main.columnconfigure(1, weight=1, minsize=300)
        main.rowconfigure(0, weight=1)

        left_wrap = tk.Frame(main, bg=BG)
        left_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_wrap.rowconfigure(0, weight=1)
        left_wrap.columnconfigure(0, weight=1)

        # 左栏内容可能比屏幕高，套一层 Canvas 做竖向滚动
        canvas = tk.Canvas(left_wrap, bg=BG, highlightthickness=0, bd=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(left_wrap, orient="vertical", command=canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=vsb.set)

        left = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")

        def _on_inner(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas(e):
            canvas.itemconfigure(win_id, width=e.width)

        left.bind("<Configure>", _on_inner)
        canvas.bind("<Configure>", _on_canvas)
        self._canvas = canvas

        def _wheel(e):
            if canvas.winfo_height() < left.winfo_reqheight():
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _wheel, add="+")

        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        # ---------- ① 选择 MOD ----------
        card1 = self._card(left)
        card1.pack(fill="x")
        self._section(card1, "① 选择 MOD 包")

        row = tk.Frame(card1, bg=CARD)
        row.pack(fill="x", padx=10, pady=(0, 6))
        ent = ttk.Entry(row, textvariable=self.var_path, font=FONT)
        ent.pack(side="left", fill="x", expand=True)
        ent.bind("<Return>", lambda e: self.load_package())
        ttk.Button(row, text="zip", width=5, command=self.pick_zip).pack(side="left", padx=(5, 0))
        ttk.Button(row, text="文件夹", width=7, command=self.pick_dir).pack(side="left", padx=(3, 0))
        ttk.Button(row, text="识别", width=5, command=self.load_package).pack(side="left", padx=(3, 0))

        self.info_box = tk.Frame(card1, bg="#fbfcfd", highlightthickness=1,
                                 highlightbackground=LINE)
        self.info_box.pack(fill="x", padx=10, pady=(0, 10))
        self._render_info(None)

        # ---------- ② 操作 ----------
        card2 = self._card(left)
        card2.pack(fill="x", pady=(6, 0))
        self._section(card2, "② 要做什么（两项可以同时做）")

        body = tk.Frame(card2, bg=CARD)
        body.pack(fill="x", padx=10, pady=(0, 6))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="特效类型", font=FONT_S, bg=CARD, fg=MUTED,
                 anchor="w").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.rb0 = ttk.Radiobutton(body, text="不改", value=EFFECT_NONE,
                                   variable=self.var_effect, command=self._sync_state)
        self.rb0.grid(row=1, column=0, sticky="w", pady=2)

        self.rb1 = ttk.Radiobutton(body, text="通用特效 → 独立特效",
                                   value=EFFECT_COMMON2STAND,
                                   variable=self.var_effect, command=self._sync_state)
        self.rb1.grid(row=2, column=0, sticky="w", pady=2)
        sub1 = tk.Frame(body, bg=CARD)
        sub1.grid(row=2, column=1, sticky="w", padx=(8, 0))
        tk.Label(sub1, text="特效 ID", font=FONT_S, bg=CARD, fg=MUTED).pack(side="left")
        self.sp_eid = ttk.Spinbox(sub1, from_=1, to=999, width=6,
                                  textvariable=self.var_eid, font=FONT,
                                  command=self._update_eid_hint)
        self.sp_eid.pack(side="left", padx=(4, 6))
        self.sp_eid.bind("<KeyRelease>", lambda _e: self._update_eid_hint())
        self.lbl_eid_hint = tk.Label(sub1, text="", font=FONT_S, bg=CARD, fg=MUTED)
        self.lbl_eid_hint.pack(side="left")

        self.rb2 = ttk.Radiobutton(body, text="独立特效 → 通用特效",
                                   value=EFFECT_STAND2COMMON,
                                   variable=self.var_effect, command=self._sync_state)
        self.rb2.grid(row=3, column=0, sticky="w", pady=2)
        tk.Label(body, text="mEpvNo 归零，epv3 / epvsp 改回 hm_wpXX",
                 font=FONT_S, bg=CARD, fg=MUTED).grid(row=3, column=1, sticky="w", padx=(8, 0))

        self.rb_stripwp = ttk.Radiobutton(body, text="删武器特效（保留随刀特效）",
                                          value=EFFECT_STRIP_WP,
                                          variable=self.var_effect, command=self._sync_state)
        self.rb_stripwp.grid(row=4, column=0, sticky="w", pady=2)
        tk.Label(body, text="删 epv3 / epvsp，mEpvNo 归零回落到本体通用特效",
                 font=FONT_S, bg=CARD, fg=MUTED, anchor="w").grid(
            row=4, column=1, sticky="w", padx=(8, 0))

        mode_row = tk.Frame(body, bg=CARD)
        mode_row.grid(row=5, column=1, sticky="w", padx=(8, 0), pady=(0, 2))
        self.rb_safe = ttk.Radiobutton(mode_row, text="保险（只删默认路径）",
                                       value=STRIP_SAFE, variable=self.var_strip_mode,
                                       command=self._sync_state)
        self.rb_safe.pack(side="left")
        self.rb_full = ttk.Radiobutton(mode_row, text="彻底（自定义目录也清）",
                                       value=STRIP_FULL, variable=self.var_strip_mode,
                                       command=self._sync_state)
        self.rb_full.pack(side="left", padx=(10, 0))

        tk.Frame(body, bg=LINE, height=1).grid(row=6, column=0, columnspan=2,
                                               sticky="ew", pady=(6, 4))

        tk.Label(body, text="武器模型", font=FONT_S, bg=CARD, fg=MUTED,
                 anchor="w").grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 2))

        self.rb_keep = ttk.Radiobutton(body, text="保持原样", value=MODEL_KEEP,
                                       variable=self.var_model, command=self._sync_state)
        self.rb_keep.grid(row=8, column=0, sticky="w", pady=2)

        self.rb_repl = ttk.Radiobutton(body, text="替换成", value=MODEL_REPLACE,
                                       variable=self.var_model, command=self._sync_state)
        self.rb_repl.grid(row=9, column=0, sticky="w", pady=2)
        sub3 = tk.Frame(body, bg=CARD)
        sub3.grid(row=9, column=1, sticky="ew", padx=(8, 0))
        self.cb_target = ttk.Combobox(sub3, textvariable=self.var_target,
                                      font=FONT, state="readonly")
        self.cb_target.pack(side="left", fill="x", expand=True)
        # ★ 下拉直接选的时候不会走 _on_target_picked，得单独绑事件，
        #   否则「epvid 会同步为 X」的提示还停在上一个目标上。
        self.cb_target.bind("<<ComboboxSelected>>",
                            lambda _e: self._on_target_changed())
        ttk.Button(sub3, text="搜索", width=6, command=self.open_search).pack(side="left", padx=(5, 0))
        self.lbl_replace_hint = tk.Label(body, text="", font=FONT_S, bg=CARD,
                                         fg=ACCENT, anchor="w")
        self.lbl_replace_hint.grid(row=10, column=1, sticky="w", padx=(8, 0))
        tk.Label(body, text="只改 mod3 / mrl3 / ctc / evwp / 随刀 epv3；贴图留在原目录不动",
                 font=FONT_S, bg=CARD, fg=MUTED, anchor="w").grid(
            row=11, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        self.rb_strip = ttk.Radiobutton(body, text="只保留特效（删掉模型）", value=MODEL_STRIP,
                                        variable=self.var_model, command=self._sync_state)
        self.rb_strip.grid(row=12, column=0, sticky="w", pady=2)
        tk.Label(body, text="删掉 mod3 / mrl3 / ctc / tex / 部件模型 / 武器音效，只留特效",
                 font=FONT_S, bg=CARD, fg=MUTED, anchor="w").grid(
            row=12, column=1, sticky="w", padx=(8, 0), pady=(0, 2))

        # ---------- ③ 输出 ----------
        card3 = self._card(left)
        card3.pack(fill="x", pady=(6, 0))
        self._section(card3, "③ 输出")

        row = tk.Frame(card3, bg=CARD)
        row.pack(fill="x", padx=10)
        ttk.Checkbutton(row, text="直接覆盖原包（自动备份 .bak）", variable=self.var_overwrite,
                        command=self._sync_state).pack(side="left")
        row2 = tk.Frame(card3, bg=CARD)
        row2.pack(fill="x", padx=10, pady=(4, 10))
        tk.Label(row2, text="输出到", font=FONT_S, bg=CARD, fg=MUTED).pack(side="left")
        self.ent_out = ttk.Entry(row2, textvariable=self.var_out, font=FONT)
        self.ent_out.pack(side="left", fill="x", expand=True, padx=(6, 5))
        ttk.Button(row2, text="另存为", width=7, command=self.pick_output).pack(side="left")

        # ---------- 按钮 ----------
        btns = tk.Frame(left, bg=BG)
        btns.pack(fill="x", pady=(8, 0))
        self.btn_run = ttk.Button(btns, text="执 行", width=12, command=self.run)
        self.btn_run.pack(side="right")
        self.btn_preview = ttk.Button(btns, text="预览变更（不保存）", width=18,
                                      command=self.preview)
        self.btn_preview.pack(side="right", padx=(0, 8))
        ttk.Button(btns, text="关于", width=6,
                   command=self._show_about).pack(side="right", padx=(0, 8))
        self.lbl_status = tk.Label(btns, text="", font=FONT_S, bg=BG, fg=MUTED)
        self.lbl_status.pack(side="left")

        # ---------- 日志 ----------
        bar = tk.Frame(right, bg=BG)
        bar.pack(fill="x")
        tk.Label(bar, text="日志", font=FONT_B, bg=BG, fg=TEXT).pack(side="left")
        ttk.Button(bar, text="清空", width=5, command=self.clear_log).pack(side="right")

        wrap = tk.Frame(right, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        wrap.pack(fill="both", expand=True, pady=(4, 0))
        self.txt_log = tk.Text(wrap, font=FONT_MONO, bg="#ffffff", fg=TEXT, relief="flat",
                               wrap="char", padx=8, pady=6, width=30)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)
        for tag, color in (("ok", OK), ("warn", WARN), ("err", ERR),
                           ("dim", MUTED), ("key", ACCENT)):
            self.txt_log.tag_configure(tag, foreground=color)

    # ------------------------------------------------------------------
    # 检查更新
    def _check_update(self):
        if self._busy:
            return
        self._set_status("检查更新…")
        threading.Thread(target=self._check_update_worker, daemon=True).start()

    def _check_update_worker(self):
        try:
            info = updater.fetch_latest()
        except updater.UpdateError as exc:
            msg = str(exc)
            self.after(0, lambda: (self._set_status(""),
                                   messagebox.showwarning("检查更新", msg)))
            return
        self.after(0, lambda: self._on_update_info(info))

    def _on_update_info(self, info):
        self._set_status("")
        cur = version.VERSION
        if not updater.is_newer(info["version"], cur):
            messagebox.showinfo("检查更新", "已经是最新版 v%s" % cur)
            return

        notes = (info["notes"] or "").strip()
        if len(notes) > 700:
            notes = notes[:700] + "…"
        msg = "发现新版本 v%s（当前 v%s）" % (info["version"], cur)
        if notes:
            msg += "\n\n" + notes
        msg += "\n\n要下载并安装吗？"
        if not messagebox.askyesno("发现新版本", msg):
            return
        if not info["url"]:
            messagebox.showwarning(
                "检查更新",
                "这个版本没有 exe 附件，请到发布页手动下载：\n" + info["page"])
            return
        self._download_update(info["url"])

    def _download_update(self, url):
        dest = os.path.join(tempfile.gettempdir(), "MHW_WP_Tool_new.exe")
        self._set_status("下载中…")

        def work():
            try:
                updater.download(url, dest, progress=self._on_dl_progress)
            except updater.UpdateError as exc:
                msg = str(exc)
                self.after(0, lambda: (self._set_status(""),
                                       messagebox.showerror("下载失败", msg)))
                return
            self.after(0, lambda: self._finish_update(dest))

        threading.Thread(target=work, daemon=True).start()

    def _on_dl_progress(self, done, total):
        if not total:
            text = "下载中 %.1f MB" % (done / 1048576.0)
        else:
            text = "下载中 %d%%（%.1f / %.1f MB）" % (
                done * 100 // total, done / 1048576.0, total / 1048576.0)
        self.after(0, lambda t=text: self._set_status(t))

    def _finish_update(self, dest):
        self._set_status("")
        if not messagebox.askyesno(
                "安装更新",
                "下载完成。程序会关闭并自动替换成新版，然后重新打开。\n\n现在重启吗？"):
            messagebox.showinfo("提示", "新版本已下载到：\n" + dest)
            return
        try:
            updater.install_and_restart(dest)
        except updater.UpdateError as exc:
            messagebox.showerror("更新失败", str(exc))
            return
        self.destroy()

    def _pick_owner(self):
        """纯特效包：问一下这套特效属于哪把武器（用来补 evwp）。"""
        items = weapons.model_list(self.info.abbr) if self.info and self.info.abbr else []
        if not items:
            messagebox.showerror("提示", "识别不出武器类型，没法选所属武器")
            return None

        dlg = tk.Toplevel(self)
        dlg.title("选择所属武器")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.resizable(False, False)
        dlg.grab_set()
        w, h = 500, 210
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + 130
        dlg.geometry("%dx%d+%d+%d" % (w, h, max(20, x), max(20, y)))

        tk.Label(dlg, text="这个包只有特效，没有模型目录", font=FONT_B,
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(dlg, text="选一下这套特效是给哪把武器用的，好把 evwp 补到对应位置。",
                 font=FONT_S, bg=BG, fg=MUTED, wraplength=400,
                 justify="left").pack(anchor="w", padx=16)

        # 默认挑一个独立模型（不以 bs_ 开头的），组合模型放后面
        default = next((it for it in items if not it["dirname"].startswith("bs_")),
                       items[0])
        var = tk.StringVar(value=default["label"])
        cb = ttk.Combobox(dlg, textvariable=var, font=FONT, state="readonly",
                          values=[it["label"] for it in items])
        cb.pack(fill="x", padx=16, pady=(12, 0))

        result = {"item": None}

        def ok(_e=None):
            for it in items:
                if it["label"] == var.get():
                    result["item"] = it
                    break
            dlg.destroy()

        btns = tk.Frame(dlg, bg=BG)
        btns.pack(fill="x", padx=16, pady=14)
        ttk.Button(btns, text="取消", width=8, command=dlg.destroy).pack(side="right")
        ttk.Button(btns, text="确定", width=8, command=ok).pack(side="right", padx=(0, 8))

        dlg.bind("<Return>", ok)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        self.wait_window(dlg)
        return result["item"]

    def _show_about(self):
        self._hide_tip()
        AboutWindow(self, on_check=self._check_update)

    def _open_bili(self):
        self._hide_tip()
        try:
            ok = webbrowser.open(BILI_URL)
        except Exception:
            ok = False
        if not ok:
            messagebox.showinfo("B站主页", BILI_URL)

    def _show_tip(self, text):
        if self._tip is not None:
            return
        x = self.lnk_bili.winfo_rootx()
        y = self.lnk_bili.winfo_rooty() + self.lnk_bili.winfo_height() + 4
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.wm_geometry("+%d+%d" % (x, y))
        tk.Label(tip, text=text, font=FONT_S, bg="#fffbe6", fg=TEXT,
                 relief="solid", borderwidth=1, padx=6, pady=3).pack()
        self._tip = tip

    def _hide_tip(self):
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    def _card(self, parent):
        f = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        return f

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=FONT_B, bg=CARD, fg=TEXT,
                 anchor="w").pack(fill="x", padx=10, pady=(8, 4))

    # ------------------------------------------------------------------
    def pick_zip(self):
        p = filedialog.askopenfilename(
            title="选择 MOD 压缩包",
            filetypes=[("MOD 压缩包", "*.zip"), ("所有文件", "*.*")])
        if p:
            self.var_path.set(p)
            self.load_package()

    def pick_dir(self):
        p = filedialog.askdirectory(title="选择 MOD 文件夹（含 nativePC 或 wp）")
        if p:
            self.var_path.set(p)
            self.load_package()

    def pick_output(self):
        if self.var_overwrite.get():
            return
        init = self.var_out.get() or paths.app_dir()
        p = filedialog.asksaveasfilename(
            title="另存为", defaultextension=".zip",
            initialfile=os.path.basename(init) if init else "mod_converted.zip",
            initialdir=os.path.dirname(init) if init else paths.app_dir(),
            filetypes=[("MOD 压缩包", "*.zip")])
        if p:
            self.var_out.set(p)

    # ------------------------------------------------------------------
    def load_package(self):
        src = self.var_path.get().strip().strip('"')
        if not src:
            messagebox.showinfo("提示", "先选一个 MOD 包（zip 或文件夹）")
            return
        if not os.path.exists(src):
            messagebox.showerror("找不到", "路径不存在：\n%s" % src)
            return
        self._set_status("正在读取…")
        try:
            pkg = package.Package(src)
            info = detect.scan(pkg)
        except Exception as exc:
            traceback.print_exc()
            self._set_status("")
            messagebox.showerror("读取失败", str(exc))
            return
        self.pkg, self.info = pkg, info
        self._render_info(info)
        self._fill_defaults(src, info)
        self._set_status("已读取 %d 个文件" % len(pkg.names()))
        self.log("─" * 60, "dim")
        self.log("读取：%s" % src, "dim")
        self.log("识别：%s · %s · %s" % (info.title, info.form_cn,
                                       info.dir_name or "无模型目录"), "key")

    def _render_info(self, info):
        for w in self.info_box.winfo_children():
            w.destroy()

        if info is None or not info.abbr:
            tk.Label(self.info_box, text="还没识别 MOD。选一个 zip / 文件夹，或把路径粘进上面的框后按回车。",
                     font=FONT, bg="#fbfcfd", fg=MUTED, anchor="w").grid(
                row=0, column=0, sticky="w", padx=10, pady=10)
            return

        b = info.brief()

        top = tk.Frame(self.info_box, bg="#fbfcfd")
        top.grid(row=0, column=0, columnspan=6, sticky="ew", padx=10, pady=(8, 2))
        tk.Label(top, text=b["title"], font=("Microsoft YaHei UI", 11, "bold"),
                 bg="#fbfcfd", fg=TEXT).pack(side="left")
        tk.Label(top, text=b["form"], font=FONT_S, bg="#fbfcfd", fg=ACCENT).pack(
            side="left", padx=(10, 0), pady=(3, 0))

        def cell(col, label, value, width=14):
            tk.Label(self.info_box, text=label, font=FONT_S, bg="#fbfcfd",
                     fg=MUTED, anchor="w").grid(row=1, column=col * 2, sticky="w",
                                                padx=(10 if col == 0 else 4, 4), pady=1)
            tk.Label(self.info_box, text=value, font=FONT, bg="#fbfcfd",
                     fg=TEXT, anchor="w").grid(row=1, column=col * 2 + 1, sticky="w",
                                               padx=(0, 8), pady=1)

        cell(0, "模型目录", b["dir"])
        cell(1, "特效基名", b["base"])

        row2 = tk.Frame(self.info_box, bg="#fbfcfd")
        row2.grid(row=2, column=0, columnspan=6, sticky="w", padx=10, pady=(1, 2))
        tk.Label(row2, text=b["files"], font=FONT_S, bg="#fbfcfd", fg=TEXT).pack(side="left")
        tk.Label(row2, text="  |  " + b["mepv"], font=FONT_S, bg="#fbfcfd",
                 fg=MUTED).pack(side="left")

        r = 3
        for w in info.warnings:
            tk.Label(self.info_box, text="! " + w, font=FONT_S, bg="#fbfcfd",
                     fg=WARN, anchor="w", justify="left", wraplength=560).grid(
                row=r, column=0, columnspan=6, sticky="w", padx=10, pady=(1, 0))
            r += 1
        for i in info.issues:
            tk.Label(self.info_box, text="- " + i, font=FONT_S, bg="#fbfcfd",
                     fg=MUTED, anchor="w", justify="left", wraplength=560).grid(
                row=r, column=0, columnspan=6, sticky="w", padx=10, pady=(1, 0))
            r += 1
        tk.Frame(self.info_box, bg="#fbfcfd", height=4).grid(row=r, column=0)

    def _fill_defaults(self, src, info):
        # 特效 ID 默认 = 武器编号
        num = (info.num or "").lstrip("0") or ""
        if num.isdigit():
            self.var_eid.set(str(int(num)))
        self._eid_synced = False
        self._owner_item = None
        # 按检测结果自动选方向：独立特效默认往「转通用」走，反之亦然
        self.var_effect.set(EFFECT_STAND2COMMON if info.form == "standalone"
                            else EFFECT_COMMON2STAND)
        # 目标武器列表
        self._refresh_targets(info)
        # 输出路径由 _sync_state -> _refresh_out_path 按操作生成
        self._sync_state()

    def _refresh_targets(self, info):
        self._target_items = []
        if not info or not info.abbr:
            self.cb_target.configure(values=[])
            return
        items = weapons.model_list(info.abbr)
        labels = []
        for it in items:
            if info.dir_name and it["dirname"].lower() == info.dir_name.lower():
                continue
            labels.append(it["label"])
            self._target_items.append(it)
        self.cb_target.configure(values=labels)
        if labels and not self.var_target.get():
            # 默认选第一个独立模型（bs_ 组合模型排后面），和「选择所属武器」保持一致
            idx = next((i for i, it in enumerate(self._target_items)
                        if not it["dirname"].startswith("bs_")), 0)
            self.cb_target.current(idx)
        self._on_target_changed()

    def open_search(self):
        if not self.info or not self.info.abbr:
            messagebox.showinfo("提示", "先识别一个 MOD 包")
            return
        WeaponSearch(self, self.info, self._on_target_picked)

    def _on_target_changed(self):
        """目标武器变了：同步特效 ID、刷新提示和输出文件名。"""
        self._sync_eid_from_target()
        self._update_replace_hint()
        self._refresh_out_path()

    def _will_sync_eid(self):
        """特效 ID 是否由「替换目标」决定（这种情况下不给用户改）。"""
        return (self.var_model.get() == MODEL_REPLACE
                and self.var_effect.get() in (EFFECT_COMMON2STAND, EFFECT_NONE)
                and self._current_target() is not None)

    def _sync_eid_from_target(self):
        """选了替换目标时，把「特效 ID」直接改成目标武器编号。

        只弹个提示不够直观 —— 用户看不出 ID 到底会变成多少，
        所以这里直接把输入框的值改掉，改过之后切回「保持原样」再恢复。
        """
        replace = self.var_model.get() == MODEL_REPLACE
        usable = self.var_effect.get() in (EFFECT_COMMON2STAND, EFFECT_NONE)

        if not (replace and usable):
            if self._eid_synced:
                # 取消替换了，ID 恢复成这把武器自己的编号
                num = (self.info.num or "").lstrip("0") if self.info else ""
                if num.isdigit():
                    self.var_eid.set(str(int(num)))
                self._eid_synced = False
                self._update_eid_hint()
            return

        t = self._current_target()
        num = re.sub(r"\D", "", t["dirname"]) if t else ""
        if not num:
            return
        self.var_eid.set(str(int(num)))
        self._eid_synced = True
        self._update_eid_hint()

    def _on_target_picked(self, item):
        self.var_target.set(item["label"])
        # 确保它在当前下拉里
        if item["label"] not in list(self.cb_target.cget("values")):
            vals = list(self.cb_target.cget("values")) + [item["label"]]
            self.cb_target.configure(values=vals)
            self._target_items.append(item)
        self.cb_target.set(item["label"])
        self._on_target_changed()

    def _current_target(self):
        label = self.var_target.get()
        for it in self._target_items:
            if it["label"] == label:
                return it
        return None

    def _sync_state(self):
        effect = self.var_effect.get()
        model = self.var_model.get()
        ov = self.var_overwrite.get()
        # 替换武器时 epvid 由目标编号决定，输入框直接锁住（否则改了又会被拉回，很困惑）
        syncing = self._will_sync_eid()
        self.sp_eid.configure(
            state="normal" if (effect == EFFECT_COMMON2STAND and not syncing) else "disabled")
        self.cb_target.configure(state="readonly" if model == MODEL_REPLACE else "disabled")
        strip_on = "normal" if effect == EFFECT_STRIP_WP else "disabled"
        self.rb_safe.configure(state=strip_on)
        self.rb_full.configure(state=strip_on)
        self.ent_out.configure(state="disabled" if ov else "normal")
        self._sync_eid_from_target()
        self._update_eid_hint()
        self._update_replace_hint()
        self._refresh_out_path()

    def _update_replace_hint(self):
        if self.var_model.get() != MODEL_REPLACE:
            self.lbl_replace_hint.configure(text="")
            return
        # 转成通用特效之后就没有独立 id 了，不用提示
        if self.var_effect.get() in (EFFECT_STAND2COMMON, EFFECT_STRIP_WP):
            self.lbl_replace_hint.configure(text="")
            return
        will_be_standalone = (self.var_effect.get() == EFFECT_COMMON2STAND
                              or (self.info is not None
                                  and self.info.form == "standalone"))
        t = self._current_target()
        num = re.sub(r"\D", "", t["dirname"]) if t else ""
        if will_be_standalone and num:
            self.lbl_replace_hint.configure(
                text="独立特效的 epvid 会同步为 %d" % int(num))
        else:
            self.lbl_replace_hint.configure(text="")

    # 输出名后缀：转换结果直接写进文件名，方便区分（可能同时有两个）
    _SUFFIX_RE = re.compile(r"(?:_(?:通用特效|独立特效\d*|替换.+|仅特效|仅随刀特效|彻底))+$")
    _ILLEGAL = re.compile(r'[\\/:*?"<>|]')

    def _safe_name(self, item):
        """武器名当文件名用：优先中文名，去掉 Windows 非法字符。"""
        if not item:
            return "武器"
        name = (item.get("name") or "").strip()
        if not name or name == "Unavailable":
            name = item.get("dirname") or "武器"
        name = self._ILLEGAL.sub("_", name).strip(" .")
        return name or "武器"

    def _suggest_out(self):
        """按当前操作生成输出文件名，例如 xxx_独立特效28_替换吼虎刀.zip。"""
        src = self.var_path.get().strip().strip('"')
        if not src:
            return ""
        base = os.path.splitext(os.path.basename(src.rstrip("\\/")))[0]
        base = self._SUFFIX_RE.sub("", base)      # 去掉上一次的后缀，避免叠加
        folder = os.path.dirname(os.path.abspath(src))

        bits = []
        effect = self.var_effect.get()
        if effect == EFFECT_COMMON2STAND:
            eid = self.var_eid.get().strip()
            bits.append("独立特效" + (eid if eid.isdigit() else ""))
        elif effect == EFFECT_STAND2COMMON:
            bits.append("通用特效")
        elif effect == EFFECT_STRIP_WP:
            bits.append("仅随刀特效")
            if self.var_strip_mode.get() == STRIP_FULL:
                bits.append("彻底")
        model = self.var_model.get()
        if model == MODEL_REPLACE:
            bits.append("替换" + self._safe_name(self._current_target()))
        elif model == MODEL_STRIP:
            bits.append("仅特效")

        suffix = ("_" + "_".join(bits)) if bits else ""
        return os.path.join(folder, base + suffix + ".zip")

    def _refresh_out_path(self):
        if self.var_overwrite.get():
            self.var_out.set(self.var_path.get())
            return
        if self.pkg is None:
            return
        self.var_out.set(self._suggest_out())

    def _update_eid_hint(self):
        info = self.info
        if not info or not info.abbr:
            self.lbl_eid_hint.configure(text="")
            return
        eid = self.var_eid.get().strip()
        if not eid.isdigit():
            self.lbl_eid_hint.configure(text="", fg=MUTED)
            return
        name = assets.effect_filename(info.abbr, int(eid))
        hint = "→ %s.epv3 / .epvsp" % name if name else ""
        if not info.dir_name and self.var_effect.get() == EFFECT_COMMON2STAND:
            hint += "（纯特效包：执行时按所选武器编号）"
        self.lbl_eid_hint.configure(text=hint, fg=MUTED)
        # 文件名里的 id 跟着变
        if self.var_effect.get() == EFFECT_COMMON2STAND and not self.var_overwrite.get():
            self._refresh_out_path()

    # ------------------------------------------------------------------
    def preview(self):
        self._run(save=False)

    def run(self):
        self._run(save=True)

    def _run(self, save):
        if self._busy:
            return
        if self.pkg is None or self.info is None:
            messagebox.showinfo("提示", "先识别一个 MOD 包")
            return

        effect = self.var_effect.get()
        model = self.var_model.get()
        aggressive = (effect == EFFECT_STRIP_WP
                      and self.var_strip_mode.get() == STRIP_FULL)
        eid = None
        target = None

        owner_dir = None
        fxonly_replace = False
        if effect == EFFECT_COMMON2STAND:
            raw = self.var_eid.get().strip()
            if not raw.isdigit() or not (1 <= int(raw) <= 999):
                messagebox.showerror("特效 ID 不对", "特效 ID 要是 1~999 的整数")
                return
            eid = int(raw)
            if not self.info.dir_name:
                # 纯特效包没有模型目录，得确定这套特效是给哪把武器的
                if model == MODEL_REPLACE:
                    # 已经选了「替换成 X」——直接拿 X 当所属武器，不用再问一遍
                    item = self._current_target()
                else:
                    item = self._owner_item or self._pick_owner()
                    if item is not None:
                        self._owner_item = item
                if item is None:
                    return
                owner_dir = item["dirname"]
                # epvid 必须和所选武器编号一致，否则 evwp 里的 mEpvNo 对不上
                num = re.sub(r"\D", "", owner_dir)
                if num.isdigit():
                    eid = int(num)
                    self.var_eid.set(str(eid))
        if model == MODEL_REPLACE:
            target = self._current_target()
            if target is None:
                messagebox.showinfo("提示", "选了「替换成」就先选目标武器")
                return
            if not self.info.dir_name:
                # 纯特效包本来就没有模型，替换无从谈起。
                # 刚才已经把这个目标当成「所属武器」用了，这里不再做模型替换。
                model = MODEL_KEEP
                target = None
                fxonly_replace = True
        if effect == EFFECT_NONE and model == MODEL_KEEP:
            messagebox.showinfo("提示", "特效和模型都没选，没东西可做")
            return

        out = ""
        if save:
            if self.var_overwrite.get():
                out = self.var_path.get()
            else:
                out = self.var_out.get().strip().strip('"')
                if not out:
                    messagebox.showinfo("提示", "先指定输出路径")
                    return
                if not out.lower().endswith(".zip"):
                    out += ".zip"
                if os.path.abspath(out) == os.path.abspath(self.var_path.get()):
                    messagebox.showerror("路径冲突", "输出路径和原包相同。\n"
                                        "想覆盖原包请勾「直接覆盖原包」。")
                    return

        self._busy = True
        self.btn_run.configure(state="disabled")
        self.btn_preview.configure(state="disabled")
        self._set_status("处理中…")
        threading.Thread(target=self._worker,
                         args=(effect, eid, model, target, save, out, owner_dir,
                             aggressive, fxonly_replace, owner_dir),
                         daemon=True).start()

    def _worker(self, effect, eid, model, target, save, out, owner_dir=None,
                aggressive=False, fxonly_replace=False, bind_dir=None):
        """先做特效转换，再处理模型（替换 / 只留特效）。

        ★ 顺序不能反：特效转换要改 evwp 的 mEpvNo，用的是扫描时的旧路径；
          模型替换会把整个目录搬走，先替换就找不到那些 evwp 了。
        """
        try:
            pkg = package.Package(self.var_path.get())
            info = detect.scan(pkg)
            was_fxonly = not info.dir_name
            log, err = [], None

            if effect == EFFECT_COMMON2STAND:
                part, err = convert.to_standalone(pkg, info, eid, owner_dir)
                log += [("— 特效：通用 → 独立 —", "")] + part
            elif effect == EFFECT_STAND2COMMON:
                part, err = convert.to_common(pkg, info)
                log += [("— 特效：独立 → 通用 —", "")] + part
            elif effect == EFFECT_STRIP_WP:
                part, err = convert.strip_weapon_effect(pkg, info, aggressive)
                log += [("— 特效：删除武器特效 —", "")] + part

            # ---- 模型处理 ----
            if not err and fxonly_replace:
                # 纯特效包选了「替换成」：包里没有模型可换，
                # 这个目标刚才只当「所属武器」用了
                log += [("— 模型 —", ""),
                        ("跳过", "纯特效包没有模型可替换，%s 只用来绑定特效"
                         % (bind_dir or "目标武器"))]
            elif not err and model != MODEL_KEEP:
                if effect != EFFECT_NONE:
                    # 特效转换后形态变了（比如刚转成独立特效），
                    # 重新扫描一遍，才知道要不要同步 epvid / 哪些是特效文件
                    info = detect.scan(pkg)
                if model == MODEL_REPLACE:
                    part, err = convert.replace_weapon(pkg, info, target)
                    log += [("— 模型：替换武器 —", "")] + part
                else:
                    part, err = convert.strip_model(pkg, info)
                    log += [("— 模型：只保留特效 —", "")] + part

            result = (log, err, pkg, info, save, out)
        except Exception:
            result = (None, traceback.format_exc(), None, None, save, out)
        self.after(0, lambda: self._done(result))

    def _render_log(self, log):
        self.log("─" * 60, "dim")
        for action, detail in (log or []):
            if action.startswith("—"):
                # 分组标题（特效 / 模型）
                self.log("")
                self.log(action, "key")
                continue
            tag = "dim" if action in ("保留", "跳过", "缺 epvsp", "多余 epv3",
                                      "多余 epvsp", "贴图未动") else "ok"
            if action in ("跳过", "缺 epvsp", "注意"):
                tag = "warn"
            if detail:
                self.log("  %s  %s" % (action, detail), tag)
            else:
                self.log("  %s" % action, tag)

    @staticmethod
    def _touched_evwp(log):
        """这次有没有动过 evwp（改 mEpvNo / 改名 / 补入 / 搬目录）。

        strip_model 只是「保留」evwp，不算改动 —— 它的日志里不会出现 .evwp。
        """
        for action, detail in (log or []):
            blob = (action + " " + (detail or "")).lower()
            if "mepvno" in blob or ".evwp" in blob:
                return True
        return False

    def _done(self, result):
        log, err, pkg, info, save, out = result
        self._busy = False
        self.btn_run.configure(state="normal")
        self.btn_preview.configure(state="normal")
        self._set_status("")

        if err:
            self._render_log(log)
            self.log("✗ " + err, "err")
            messagebox.showerror("失败", err)
            return

        self._render_log(log)
        need_restart = self._touched_evwp(log)

        if not save:
            self.log("预览完成，未写文件", "key")
            if need_restart:
                self.log("! 执行后需要重启游戏才生效（evwp 会变）", "warn")
            return

        try:
            src = self.var_path.get()
            if self.var_overwrite.get():
                if os.path.isfile(src):
                    bak = src + ".bak"
                    if not os.path.exists(bak):
                        import shutil
                        shutil.copy2(src, bak)
                        self.log("已备份原包 → %s" % bak, "dim")
                    pkg.save(out)
                else:
                    # 覆盖文件夹：整体挪到 .bak 再写新的，避免旧文件名残留
                    pkg.save_over_dir(out)
                    self.log("原文件夹已备份为 %s.bak" % out.rstrip("\\/"), "dim")
            else:
                pkg.save(out)
        except Exception:
            tb = traceback.format_exc()
            self.log("✗ 保存失败：\n" + tb, "err")
            messagebox.showerror("保存失败", tb.splitlines()[-1])
            return

        self.log("✓ 已输出：%s" % out, "ok")
        if need_restart:
            self.log("")
            self.log("! 本次改动了 evwp，需要重启游戏才生效", "warn")
            self.log("  （evwp 在游戏启动时加载，退回标题界面不够，要完全退出重开）", "dim")
            self._set_status("完成（需重启游戏）")
        else:
            self._set_status("完成")

        msg = "已输出：\n%s\n\n要打开所在文件夹吗？" % out
        if need_restart:
            msg = ("已输出：\n%s\n\n"
                   "注意：本次改动了 evwp，需要重启游戏才生效。\n\n"
                   "要打开所在文件夹吗？" % out)
        if messagebox.askyesno("完成", msg):
            self._open_folder(os.path.dirname(os.path.abspath(out)))

    def _open_folder(self, d):
        try:
            os.startfile(d)  # noqa: S606
        except Exception:
            pass

    # ------------------------------------------------------------------
    def log(self, text, tag=None):
        self.txt_log.insert("end", text + "\n", (tag,) if tag else ())
        self.txt_log.see("end")

    def clear_log(self):
        self.txt_log.delete("1.0", "end")

    def _set_status(self, text):
        self.lbl_status.configure(text=text)


class WeaponSearch(tk.Toplevel):
    """按名称 / 编号搜武器，双击选中。"""

    def __init__(self, master, info, on_pick):
        super().__init__(master)
        self.title("搜索目标武器")
        self.geometry("620x460")
        self.configure(bg=BG)
        self.transient(master)
        self.grab_set()
        self.info = info
        self.on_pick = on_pick

        self.var_kw = tk.StringVar()
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=12, pady=10)
        tk.Label(top, text="关键词（武器名 / 编号）", font=FONT_S, bg=BG, fg=MUTED).pack(side="left")
        e = ttk.Entry(top, textvariable=self.var_kw, font=FONT)
        e.pack(side="left", fill="x", expand=True, padx=(8, 0))
        e.bind("<KeyRelease>", lambda _e: self.refresh())
        e.focus_set()

        wrap = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.lb = tk.Listbox(wrap, font=FONT, bg="#fff", fg=TEXT, relief="flat",
                             activestyle="none", selectbackground="#dbeafe")
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lb.pack(side="left", fill="both", expand=True)
        self.lb.bind("<Double-Button-1>", lambda _e: self.pick())

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(bottom, text="取消", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="选这个", command=self.pick).pack(side="right", padx=(0, 8))

        self._items = []
        self.refresh()

    def refresh(self):
        kw = self.var_kw.get().strip().lower()
        self.lb.delete(0, "end")
        self._items = []
        for it in weapons.model_list(self.info.abbr):
            if self.info.dir_name and it["dirname"].lower() == self.info.dir_name.lower():
                continue
            hay = "%s %s %s" % (it["dirname"], it["name"], it["kind"])
            if kw and kw not in hay.lower():
                continue
            self._items.append(it)
            self.lb.insert("end", it["label"])

    def pick(self):
        sel = self.lb.curselection()
        if not sel:
            return
        item = self._items[sel[0]]
        self.on_pick(item)
        self.destroy()


def main():
    dpi_aware()
    app = App()
    # 支持 MHW_WP_Tool.exe --open "D:/path/to/mod.zip" 直接打开
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--open" and i + 1 < len(argv):
            app.var_path.set(argv[i + 1])
            app.after(200, app.load_package)
            if "--preview" in argv:
                app.after(900, app.preview)
            break
    app.mainloop()


if __name__ == "__main__":
    main()
