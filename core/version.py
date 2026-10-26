# -*- coding: utf-8 -*-
"""版本号与更新日志。

改版本号时记得同步 version_info.txt 和 README。
"""

VERSION = "1.5.0"
BUILD_DATE = "2026-10-24"

AUTHOR = "真夜中のloop"
BILI_URL = "https://space.bilibili.com/478832252?spm_id_from=333.1007.0.0"
APP_TITLE = "MHW 武器 MOD 工具"

# (版本, [改动条目]) —— 新的放最前面
CHANGELOG = [
    ("1.5.0", [
        "新增「检查更新」，可以直接在软件里下载安装新版",
        "转独立特效时自动隔离特效文件，不再影响使用通用特效的武器",
    ]),
    ("1.4.0", [
        "删武器特效支持两种力度：保险 / 彻底",
        "只删默认路径，作者自定义目录不动，避免误删模型贴图",
    ]),
    ("1.3.0", [
        "支持只有特效、没有模型的 MOD 包转独立特效",
        "纯特效包会提示选择所属武器",
    ]),
    ("1.2.0", [
        "新增「删武器特效（保留随刀特效）」",
        "替换武器时特效 ID 自动跟随目标武器",
        "改动 evwp 后提示需要重启游戏",
    ]),
    ("1.1.0", [
        "新增「只保留特效（删掉模型）」",
        "特效转换和换模型可以同时做",
        "输出文件名带上转换结果",
    ]),
    ("1.0.0", [
        "通用特效 ⇄ 独立特效互转",
        "替换武器模型",
        "预览变更、覆盖前自动备份",
    ]),
]


def changelog_text(limit=None):
    """纯文本版更新日志，给「关于」窗口用。"""
    rows = CHANGELOG[:limit] if limit else CHANGELOG
    out = []
    for ver, items in rows:
        out.append("v%s" % ver)
        for it in items:
            out.append("  · %s" % it)
        out.append("")
    return "\n".join(out).rstrip()
