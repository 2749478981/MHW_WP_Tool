# -*- coding: utf-8 -*-
"""入口。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def selftest():
    """打包后自检：资源是否都进 exe 了。--selftest 运行后直接退出。

    --windowed 打包没有控制台，结果同时写到 exe 同目录的 selftest.log。
    """
    from core import assets, evwp, paths, weapons

    lines = []

    def p(*args):
        s = " ".join(str(a) for a in args)
        lines.append(s)
        try:
            print(s)
        except Exception:
            pass

    p("base:", paths.base_dir())
    p("assets/wp:", os.path.isdir(paths.asset("wp")))
    n_evwp, n_epv, n_snd = assets.asset_stats()
    p("evwp=%d epv3=%d sound=%d" % (n_evwp, n_epv, n_snd))
    p("weapons:", len(weapons.load()))
    p("model_list(swo):", len(weapons.model_list("swo")))
    p("epv_base(swo):", assets.epv_base("swo"))
    p("effect_filename(28):", assets.effect_filename("swo", 28))
    ok = (n_evwp > 900 and n_epv > 20 and len(weapons.load()) > 4000)
    # 抽一个内置 evwp 校验格式
    fname, data = assets.evwp_for("swo", "swo028")
    p("内置 swo028 evwp:", fname, len(data or b""),
      evwp.read_epv_no(data) if data else None)
    ok = ok and data is not None and evwp.is_evwp(data)
    p("SELFTEST", "OK" if ok else "FAIL")

    try:
        log = os.path.join(paths.app_dir(), "selftest.log")
        with open(log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception:
        pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from ui.app import main as run
    run()


if __name__ == "__main__":
    main()
