# -*- coding: utf-8 -*-
"""MOD 包抽象：zip 或文件夹，统一按「不含 nativePC 前缀」的相对路径操作。

包里常见两种结构：
    nativePC/wp/swo/swo028/mod/...
    wp/swo/swo028/mod/...
内部一律存成 `wp/swo/...`，保存时再按原来的前缀还原，保证结构不变。
"""
import os
import shutil
import zipfile

# 这些顶层目录说明包根就是游戏根，不需要 nativePC 前缀
GAME_ROOTS = ("wp", "vfx", "pl", "chunk", "sound", "em", "ot", "Assets", "accessory")


def split_prefix(name):
    """把 'nativePC/wp/swo/...' 拆成 ('nativePC/', 'wp/swo/...')。"""
    norm = name.replace("\\", "/").lstrip("/")
    parts = norm.split("/")
    # 取最后一个 nativePC 段（有的包是 nativePC/nativePC/...）
    last = -1
    for i, p in enumerate(parts[:-1]):
        if p.lower() == "nativepc":
            last = i
    if last >= 0:
        return "/".join(parts[:last + 1]) + "/", "/".join(parts[last + 1:])
    if parts and parts[0] in GAME_ROOTS:
        return "", norm
    return "", norm


class Package:
    """一个 MOD 包。files 的 key 是不含 nativePC 的相对路径。"""

    def __init__(self, source):
        self.source = source
        self.is_zip = os.path.isfile(source) and zipfile.is_zipfile(source)
        if not self.is_zip and not os.path.isdir(source):
            raise ValueError("既不是 zip 也不是文件夹：%s" % source)
        self.prefix = "nativePC/"
        self.files = {}
        self.origin = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self):
        if self.is_zip:
            with zipfile.ZipFile(self.source) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                prefixes = {}
                for info in infos:
                    try:
                        raw = info.filename
                    except Exception:
                        raw = info.filename
                    pre, rel = split_prefix(raw)
                    prefixes[pre] = prefixes.get(pre, 0) + 1
                # 出现最多的前缀就是包根
                if prefixes:
                    self.prefix = max(prefixes.items(), key=lambda kv: kv[1])[0]
                for info in infos:
                    pre, rel = split_prefix(info.filename)
                    if pre != self.prefix:
                        # 前缀不一致的文件（少见），仍然按它的真实位置放回
                        rel = info.filename.replace("\\", "/").lstrip("/")
                    if not rel:
                        continue
                    try:
                        data = z.read(info)
                    except Exception:
                        continue
                    self.files[rel] = data
                    self.origin[rel] = "zip"
        else:
            root = self.source
            # 如果用户选的是上一级目录（里面有 nativePC），自动进去
            sub = os.path.join(root, "nativePC")
            if os.path.isdir(sub) and not os.path.isdir(os.path.join(root, "wp")):
                self.prefix = "nativePC/"
                root = sub
            else:
                self.prefix = ""
            for cur, _dirs, names in os.walk(root):
                for f in names:
                    full = os.path.join(cur, f)
                    rel = os.path.relpath(full, root).replace("\\", "/")
                    with open(full, "rb") as fp:
                        self.files[rel] = fp.read()
                    self.origin[rel] = "dir"

    # ------------------------------------------------------------------
    def names(self):
        return sorted(self.files)

    def exists(self, rel):
        return rel in self.files

    def read(self, rel):
        return self.files.get(rel)

    def write(self, rel, data):
        self.files[rel] = data
        self.origin[rel] = "new"

    def remove(self, rel):
        self.files.pop(rel, None)
        self.origin.pop(rel, None)

    def rename(self, old, new):
        """改名（目标已存在则覆盖）。返回是否成功。"""
        if old not in self.files:
            return False
        if old == new:
            return False
        data = self.files.pop(old)
        self.origin.pop(old, None)
        self.files[new] = data
        self.origin[new] = "renamed"
        return True

    def glob(self, prefix="", suffix=None):
        out = []
        for n in self.files:
            if prefix and not n.startswith(prefix):
                continue
            if suffix and not n.lower().endswith(suffix):
                continue
            out.append(n)
        return sorted(out)

    # ------------------------------------------------------------------
    def save_zip(self, out_path):
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            # 先写目录项，保持资源管理器的层级观感
            dirs = set()
            for rel in self.files:
                full = self.prefix + rel
                parts = full.split("/")[:-1]
                for i in range(1, len(parts) + 1):
                    dirs.add("/".join(parts[:i]) + "/")
            for d in sorted(dirs):
                z.writestr(zipfile.ZipInfo(d), b"")
            for rel in sorted(self.files):
                z.writestr(self.prefix + rel, self.files[rel])
        return out_path

    def save_dir(self, out_dir):
        root = os.path.join(out_dir, self.prefix.replace("/", os.sep).rstrip(os.sep)) \
            if self.prefix else out_dir
        for rel, data in self.files.items():
            full = os.path.join(root, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)
        return root

    def save(self, out_path):
        if out_path.lower().endswith(".zip"):
            return self.save_zip(out_path)
        return self.save_dir(out_path)

    def save_over_dir(self, out_dir):
        """覆盖文件夹：先把旧目录整体挪到 .bak，写新的，失败再挪回来。

        ★ 不能直接 save_dir：改名后的文件是新名字，旧名字的文件还留在磁盘上，
          游戏会同时读到两套（比如 swo028.mod3 和 swo032.mod3 并存）。
        """
        src = out_dir.rstrip("\\/")
        bak = src + ".bak"
        if os.path.exists(bak):
            shutil.rmtree(bak, ignore_errors=True)
        shutil.move(src, bak)
        try:
            self.save_dir(src)
        except Exception:
            shutil.rmtree(src, ignore_errors=True)
            shutil.move(bak, src)
            raise
        return src


def copy_into(src_dir, dst_dir):
    """把源文件夹内容复制到目标（保留结构）。"""
    os.makedirs(dst_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        if os.path.isdir(s):
            copy_into(s, d)
        else:
            shutil.copy2(s, d)
