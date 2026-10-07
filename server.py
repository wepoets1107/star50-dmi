# -*- coding: utf-8 -*-
"""
588000 科创50ETF · DMI 趋势看板 —— 后端
标准库 http.server 实现，零第三方依赖（无需 Flask）。

接口：
    GET /              → 看板页面
    GET /api/report    → JSON（指标、序列、信号、趋势分段）

启动：pythonw.exe server.py   （后台无窗口，端口 5059）
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from fetch import get_ohlc          # noqa: E402
from dmi import compute_dmi, trend_state   # noqa: E402

PORT = 5059
SYMBOL = "588000.SS"
NAME = "科创50ETF"
N = 14
SHOW_BARS = 260                     # 图表展示最近多少根 K 线
TPL_FILE = os.path.join(BASE_DIR, "templates", "dashboard.html")

_rep_cache = {"ts": 0.0, "data": None}
REP_TTL = 60                        # 报告内存缓存 60s


# ══════════════════════════════════════════════════════════════
#  报告构建
# ══════════════════════════════════════════════════════════════

def _detect_signals(dates, d):
    """识别 ±DI 金叉/死叉 与 ADX 穿越 20/25 时点。"""
    out = []
    p, m, a = d["plus_di"], d["minus_di"], d["adx"]
    for i in range(1, len(dates)):
        if None in (p[i], m[i], p[i - 1], m[i - 1]):
            continue
        if p[i - 1] <= m[i - 1] and p[i] > m[i]:
            out.append({"date": dates[i], "kind": "golden", "level": None,
                        "label": "+DI 上穿 −DI（金叉 / 转多）", "value": round(p[i], 2)})
        elif p[i - 1] >= m[i - 1] and p[i] < m[i]:
            out.append({"date": dates[i], "kind": "death", "level": None,
                        "label": "+DI 下穿 −DI（死叉 / 转空）", "value": round(m[i], 2)})
        if a[i] is not None and a[i - 1] is not None:
            for lvl in (20, 25):
                if a[i - 1] < lvl <= a[i]:
                    out.append({"date": dates[i], "kind": "adx_up", "level": lvl,
                                "label": f"ADX 上穿 {lvl}（趋势增强）", "value": round(a[i], 2)})
                elif a[i - 1] >= lvl > a[i]:
                    out.append({"date": dates[i], "kind": "adx_down", "level": lvl,
                                "label": f"ADX 下穿 {lvl}（趋势减弱）", "value": round(a[i], 2)})
    return out


def _detect_segments(dates, d, close, min_days=5):
    """识别 ADX>=25 的连续区间为趋势段，方向按段内平均 ±DI 判定。"""
    segs = []
    p, m, a = d["plus_di"], d["minus_di"], d["adx"]
    n = len(dates)
    i = 0
    while i < n:
        if a[i] is not None and a[i] >= 25:
            j = i
            while j < n and a[j] is not None and a[j] >= 25:
                j += 1
            if j - i >= min_days:
                seg_a = [a[k] for k in range(i, j) if a[k] is not None]
                seg_p = [p[k] for k in range(i, j) if p[k] is not None]
                seg_m = [m[k] for k in range(i, j) if m[k] is not None]
                avg_p = sum(seg_p) / len(seg_p) if seg_p else 0.0
                avg_m = sum(seg_m) / len(seg_m) if seg_m else 0.0
                direction = "bull" if avg_p > avg_m else "bear"
                px_chg = (close[j - 1] / close[i] - 1) * 100 if close[i] else 0.0
                segs.append({
                    "start": dates[i], "end": dates[j - 1], "days": j - i,
                    "direction": direction,
                    "adx_peak": round(max(seg_a), 1) if seg_a else None,
                    "price_change": round(px_chg, 1),
                })
            i = j
        else:
            i += 1
    return segs


def build_report():
    rows = get_ohlc(SYMBOL)
    dates = [r["date"] for r in rows]
    high = [r["high"] for r in rows]
    low = [r["low"] for r in rows]
    close = [r["close"] for r in rows]

    d = compute_dmi(high, low, close, N)

    def last_valid(seq):
        for v in reversed(seq):
            if v is not None:
                return v
        return None

    pdi = last_valid(d["plus_di"])
    mdi = last_valid(d["minus_di"])
    adx = last_valid(d["adx"])
    adxr = last_valid(d["adxr"])

    # 上一期 ADX
    idx = len(close) - 1
    while idx >= 0 and d["adx"][idx] is None:
        idx -= 1
    adx_prev = d["adx"][idx - 1] if idx - 1 >= 0 else None

    st = trend_state(pdi, mdi, adx, adx_prev)

    px = close[-1]
    prev_px = close[-2] if len(close) > 1 else px
    chg = (px / prev_px - 1) * 100 if prev_px else 0.0

    start = max(0, len(close) - SHOW_BARS)
    series = []
    for i in range(start, len(close)):
        r2 = lambda v: round(v, 2) if v is not None else None   # noqa: E731
        series.append({
            "date": dates[i],
            "close": round(close[i], 4),
            "plus_di": r2(d["plus_di"][i]),
            "minus_di": r2(d["minus_di"][i]),
            "adx": r2(d["adx"][i]),
        })

    return {
        "symbol": SYMBOL, "name": NAME, "n": N,
        "date": dates[-1], "price": round(px, 4), "change_pct": round(chg, 2),
        "dmi": {
            "plus_di": round(pdi, 2), "minus_di": round(mdi, 2),
            "adx": round(adx, 2),
            "adxr": round(adxr, 2) if adxr is not None else None,
            "adx_prev": round(adx_prev, 2) if adx_prev is not None else None,
        },
        "state": st,
        "series": series,
        "signals": _detect_signals(dates, d)[::-1],     # 最近在前
        "segments": _detect_segments(dates, d, close)[::-1],
        "bars": len(close),
        "range": [dates[0], dates[-1]],
    }


def get_report():
    now = time.time()
    if _rep_cache["data"] is not None and now - _rep_cache["ts"] < REP_TTL:
        return _rep_cache["data"]
    rep = build_report()
    _rep_cache.update(ts=now, data=rep)
    return rep


# ══════════════════════════════════════════════════════════════
#  HTTP 服务
# ══════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    server_version = "Star50DMI/1.0"

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                with open(TPL_FILE, "r", encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/report":
                self._send(200, json.dumps(get_report(), ensure_ascii=False))
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:                       # noqa: BLE001
            tb = traceback.format_exc()
            sys.stderr.write(tb)
            self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False))

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"588000 DMI dashboard → http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
