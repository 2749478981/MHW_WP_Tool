# -*- coding: utf-8 -*-
"""「关于」窗口：版本号、作者、B站链接、更新日志。"""
import tkinter as tk
import webbrowser
from tkinter import ttk

from core import version

BG = "#f5f6f8"
CARD = "#ffffff"
TEXT = "#1f2328"
MUTED = "#6b7280"
LINE = "#dfe3e8"
ACCENT = "#2f6feb"

FONT = ("Microsoft YaHei UI", 9)
FONT_S = ("Microsoft YaHei UI", 8)
FONT_MONO = ("Consolas", 9)


class AboutWindow(tk.Toplevel):
    def __init__(self, master, on_check=None):
        super().__init__(master)
        self._on_check = on_check
        self.title("关于 %s" % version.APP_TITLE)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(master)

        w, h = 520, 430
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + 60
        self.geometry("%dx%d+%d+%d" % (w, h, max(20, x), max(20, y)))

        # ---- 头部 ----
        head = tk.Frame(self, bg=CARD, highlightthickness=1,
                        highlightbackground=LINE)
        head.pack(fill="x", padx=14, pady=(14, 0))

        row = tk.Frame(head, bg=CARD)
        row.pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(row, text=version.APP_TITLE, font=("Microsoft YaHei UI", 13, "bold"),
                 bg=CARD, fg=TEXT).pack(side="left")
        tk.Label(row, text="v" + version.VERSION, font=FONT_S,
                 bg="#eef4ff", fg=ACCENT, padx=6, pady=1).pack(side="left", padx=(8, 0))

        tk.Label(head, text="by %s   ·   %s" % (version.AUTHOR, version.BUILD_DATE),
                 font=FONT_S, bg=CARD, fg=MUTED).pack(anchor="w", padx=14)

        link = tk.Label(head, text="B站主页  space.bilibili.com/478832252",
                        font=("Microsoft YaHei UI", 8, "underline"),
                        bg=CARD, fg=ACCENT, cursor="hand2")
        link.pack(anchor="w", padx=14, pady=(4, 12))
        link.bind("<Button-1>", lambda _e: webbrowser.open(version.BILI_URL))

        # ---- 更新日志 ----
        tk.Label(self, text="更新内容", font=("Microsoft YaHei UI", 9, "bold"),
                 bg=BG, fg=TEXT).pack(anchor="w", padx=16, pady=(12, 4))

        wrap = tk.Frame(self, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        wrap.pack(fill="both", expand=True, padx=14)
        # width=1 是必须的：Text 默认 80 字符宽，会把窗口撑出去
        txt = tk.Text(wrap, font=FONT_MONO, bg=CARD, fg=TEXT, relief="flat",
                      wrap="char", padx=10, pady=8, width=1, height=12)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.tag_configure("ver", foreground=ACCENT, font=("Consolas", 9, "bold"))
        txt.tag_configure("dim", foreground=MUTED)
        for ver, items in version.CHANGELOG:
            txt.insert("end", "v%s\n" % ver, "ver")
            for it in items:
                txt.insert("end", "  · %s\n" % it)
            txt.insert("end", "\n")
        txt.configure(state="disabled")

        # ---- 底部 ----
        btns = tk.Frame(self, bg=BG)
        btns.pack(fill="x", padx=14, pady=12)
        ttk.Button(btns, text="关闭", width=8,
                   command=self.destroy).pack(side="right")
        ttk.Button(btns, text="打开 B 站", width=10,
                   command=lambda: webbrowser.open(version.BILI_URL)).pack(side="right", padx=(0, 8))
        if self._on_check:
            ttk.Button(btns, text="检查更新", width=10,
                       command=self._do_check).pack(side="left")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(80, lambda: self.lift())

    def _do_check(self):
        """关掉关于窗口，交给主窗口去查（进度和结果都显示在主窗口）。"""
        cb = self._on_check
        self.destroy()
        if cb:
            cb()
