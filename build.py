# -*- coding: utf-8 -*-
"""
生成静态 HTML 快照（GitHub Pages 部署用）。

GitHub Pages 是纯静态托管，没有后端，无法访问 /api/report。
因此这里把 build_report() 的结果序列化后内联注入页面，
前端 load() 会优先读 window.__REPORT__，读不到才回退到 fetch。

用法：
    python build.py
产出：
    docs/index.html   +   docs/.nojekyll
"""

from __future__ import annotations

import json
import os

import server

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TPL_FILE = os.path.join(BASE_DIR, "templates", "dashboard.html")
OUT_DIR = os.path.join(BASE_DIR, "docs")
OUT_FILE = os.path.join(OUT_DIR, "index.html")

# 前端脚本锚点：在这行之前插入内联数据
ANCHOR = "const C = {up:'#d64545'"


def build() -> None:
    report = server.build_report()

    # 安全序列化：避免数据里出现 </script> 提前闭合标签
    snap = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")

    with open(TPL_FILE, "r", encoding="utf-8") as f:
        tpl = f.read()

    if ANCHOR not in tpl:
        raise SystemExit(f"锚点未找到，模板可能已改动：{ANCHOR!r}")

    inject = (
        "/* ---- 静态快照（GitHub Pages 用，自动生成）---- */\n"
        f"window.__REPORT__ = {snap};\n\n"
    )
    html = tpl.replace(ANCHOR, inject + ANCHOR, 1)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    # GitHub Pages 跳过 Jekyll 处理，避免下划线开头资源被忽略
    with open(os.path.join(OUT_DIR, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    dmi = report["dmi"]
    print(f"生成 {os.path.relpath(OUT_FILE, BASE_DIR)}  ({len(html):,} bytes)")
    print(f"  标的 {report['symbol']} {report['name']}  数据至 {report['date']}")
    print(f"  最新价 {report['price']}  +DI {dmi['plus_di']}  -DI {dmi['minus_di']}  ADX {dmi['adx']}")
    print(f"  序列 {len(report['series'])} 点 · 信号 {len(report['signals'])} 条 · 趋势段 {len(report['segments'])} 段")
    print(f"  状态 {report['state']['label']}")


if __name__ == "__main__":
    build()
