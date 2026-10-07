# -*- coding: utf-8 -*-
"""
行情数据拉取（Yahoo Finance chart API，标准库零依赖）+ 本地缓存。

Yahoo chart 接口免鉴权、免 crumb，直接 GET 即可返回 OHLCV。
DMI 必须依赖 High / Low / Close，因此这里取完整 OHLC。

用法：
    from fetch import get_ohlc
    rows = get_ohlc("588000.SS")     # [{"date","open","high","low","close","volume"}, ...]
"""

from __future__ import annotations

import json
import os
import pickle
import time
import urllib.request
from datetime import datetime, timezone

__all__ = ["get_ohlc", "fetch_yahoo"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "price_cache.pkl")
CACHE_TTL = 2 * 3600          # 缓存 2 小时

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_yahoo(symbol: str = "588000.SS", rng: str = "10y", interval: str = "1d") -> list:
    """从 Yahoo Finance 拉取日线 OHLCV。"""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval={interval}")
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    res = payload["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]

    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        rows.append({
            "date": d, "open": float(o), "high": float(h),
            "low": float(l), "close": float(c),
            "volume": q["volume"][i] or 0,
        })
    rows.sort(key=lambda r: r["date"])
    return rows


def get_ohlc(symbol: str = "588000.SS", force: bool = False) -> list:
    """带本地缓存的取数入口。"""
    if not force and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
            entry = cache.get(symbol)
            if entry and (time.time() - entry.get("_ts", 0) < CACHE_TTL):
                return entry["data"]
        except Exception:
            pass

    rows = fetch_yahoo(symbol)
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "rb") as f:
                cache = pickle.load(f)
        except Exception:
            cache = {}
    cache[symbol] = {"_ts": time.time(), "data": rows}
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)
    return rows


if __name__ == "__main__":
    data = get_ohlc("588000.SS", force=True)
    print(f"symbol=588000.SS  bars={len(data)}")
    print(f"first: {data[0]['date']}  close={data[0]['close']}")
    print(f"last : {data[-1]['date']}  O={data[-1]['open']} H={data[-1]['high']} "
          f"L={data[-1]['low']} C={data[-1]['close']}")
