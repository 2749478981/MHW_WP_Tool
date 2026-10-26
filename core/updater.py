# -*- coding: utf-8 -*-
"""检查更新：从 GitHub Releases 拉最新版本，下载并替换自身。

仓库地址写死在 REPO 里，不需要用户配置。
"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

REPO = "2749478981/MHW_WP_Tool"
API_LATEST = "https://api.github.com/repos/%s/releases/latest" % REPO
PAGE = "https://github.com/%s/releases" % REPO
UA = "MHW_WP_Tool-Updater"


class UpdateError(Exception):
    pass


def parse_version(text):
    """'v1.4.0' / '1.4.0' → (1, 4, 0)。解析不了的部分当 0。"""
    if not text:
        return (0,)
    s = str(text).strip().lstrip("vV")
    parts = []
    for seg in s.split("."):
        digits = "".join(ch for ch in seg if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote, local):
    """remote 版本是否比 local 新。"""
    a, b = parse_version(remote), parse_version(local)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a > b


def fetch_latest(timeout=10):
    """拉最新 release 信息。

    返回 dict：version / url / size / page / notes / name
    url 是 exe 附件地址，没有 exe 附件时为 None。
    """
    req = urllib.request.Request(
        API_LATEST,
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError("仓库里还没有发布任何版本")
        raise UpdateError("GitHub 返回 %d" % exc.code)
    except urllib.error.URLError as exc:
        raise UpdateError("连不上 GitHub：%s" % exc.reason)
    except Exception as exc:                      # noqa: BLE001
        raise UpdateError("检查更新失败：%s" % exc)

    assets = data.get("assets") or []
    exe = next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)
    return {
        "version": str(data.get("tag_name") or "").lstrip("vV"),
        "url": exe.get("browser_download_url") if exe else None,
        "size": exe.get("size", 0) if exe else 0,
        "page": data.get("html_url") or PAGE,
        "notes": data.get("body") or "",
        "name": data.get("name") or "",
    }


def download(url, dest, progress=None, timeout=60):
    """下载到 dest，progress(已下载, 总大小) 可选回调。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as fh:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except Exception as exc:                      # noqa: BLE001
        raise UpdateError("下载失败：%s" % exc)
    if not os.path.exists(dest) or os.path.getsize(dest) < 1024:
        raise UpdateError("下载的文件不完整")
    return dest


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def current_exe():
    return os.path.abspath(sys.executable if is_frozen() else sys.argv[0])


def install_and_restart(new_exe):
    """把 new_exe 替换掉当前程序并重启。

    Windows 下运行中的 exe 不能被覆盖，所以写一个 bat：等本进程退出后
    再 move + start，最后自删。
    """
    if not is_frozen():
        raise UpdateError("源码运行时不能自动替换，请手动替换 exe")

    target = current_exe()
    tmp = tempfile.gettempdir()
    bat = os.path.join(tmp, "mhw_wp_tool_update.bat")
    script = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        'move /y "{new}" "{target}" >nul\r\n'
        'start "" "{target}"\r\n'
        'del "%~f0"\r\n'
    ).format(new=new_exe, target=target)
    with open(bat, "w", encoding="utf-8", newline="") as fh:
        fh.write(script)

    subprocess.Popen(
        ["cmd", "/c", bat],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
