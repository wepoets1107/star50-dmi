# -*- coding: utf-8 -*-
"""
Wilder 标准 DMI（Directional Movement Index）计算模块
—— 纯 Python 标准库实现，零第三方依赖，可直接 import 复用。

口径（严格对齐 Wilder 1978 原始定义，与 TA-Lib 一致）：

    TR[t]   = max( H-L , |H-Cprev| , |L-Cprev| )
    +DM[t]  = H-Hprev   若 (H-Hprev) > (Lprev-L) 且 (H-Hprev) > 0，否则 0
    -DM[t]  = Lprev-L   若 (Lprev-L) > (H-Hprev) 且 (Lprev-L) > 0，否则 0

    平滑    使用 Wilder RMA（α = 1/n 的递归平滑），**不是 EMA（α=2/(n+1)）**
            初学者最常踩的坑：用 EMA 会让 ADX 数值偏差 30%+，金叉死叉时点全乱。
    初值    RMA 首值 = 前 n 个原始值之和（Wilder 累积法），之后逐期递推。

    +DI[t]  = 100 × RMA(+DM) / RMA(TR)
    -DI[t]  = 100 × RMA(-DM) / RMA(TR)
    DX[t]   = 100 × |+DI − -DI| / (+DI + -DI)
    ADX[t]  = RMA(DX, n)   （首个 ADX 取前 n 个 DX 的简单均值，Wilder 原法）
    ADXR[t] = ( ADX[t] + ADX[t-n] ) / 2

预热长度：首个 ADX 出现在第 2n 根 K 线（n=14 → 第 28 根）；
          首个 ADXR 出现在第 3n 根（n=14 → 第 42 根）。
          ADX 要真正稳定建议喂 100 根以上。

用法：
    from dmi import compute_dmi, trend_state
    d = compute_dmi(high_list, low_list, close_list, n=14)
    d["plus_di"][-1], d["minus_di"][-1], d["adx"][-1]
    trend_state(d["plus_di"][-1], d["minus_di"][-1], d["adx"][-1], d["adx"][-2])
"""

from __future__ import annotations

__all__ = ["compute_dmi", "trend_state"]
__version__ = "1.0.0"


def compute_dmi(high, low, close, n: int = 14) -> dict:
    """计算 Wilder 标准 DMI。

    Args:
        high, low, close: 等长的价格序列（list / tuple / 可索引序列）。
        n: 周期，默认 14。

    Returns:
        dict，键均为与输入等长的 list，无值处为 None：
            tr, plus_dm, minus_dm          —— 原始分量
            tr_rma, plus_dm_rma, minus_dm_rma —— Wilder 平滑值
            plus_di, minus_di, dx, adx, adxr  —— 指标线
    """
    N = len(close)
    if not (len(high) == len(low) == N):
        raise ValueError("high / low / close 长度必须一致")
    if n < 2:
        raise ValueError("周期 n 必须 >= 2")
    if N < 2 * n + 1:
        raise ValueError(f"数据不足：DMI(n={n}) 至少需要 {2 * n + 1} 根 K 线，当前 {N}")

    # ── 1) 原始 TR / +DM / -DM（index 0 无前收盘，留 None）────────────
    tr = [None] * N
    pdm = [None] * N
    mdm = [None] * N
    for i in range(1, N):
        h, l, c = high[i], low[i], close[i]
        hp, lp, cp = high[i - 1], low[i - 1], close[i - 1]
        tr[i] = max(h - l, abs(h - cp), abs(l - cp))
        up = h - hp          # 今日高点 − 昨日高点
        dn = lp - l          # 昨日低点 − 今日低点
        pdm[i] = up if (up > dn and up > 0) else 0.0
        mdm[i] = dn if (dn > up and dn > 0) else 0.0

    # ── 2) Wilder RMA 平滑（初值 = 前 n 个原始值之和，随后 α=1/n 递推）
    def _wilder_rma(src):
        out = [None] * N
        acc = sum(src[1:n + 1])      # TR[1..n]，共 n 个
        out[n] = acc
        for i in range(n + 1, N):
            acc = acc - acc / n + src[i]
            out[i] = acc
        return out

    tr_rma = _wilder_rma(tr)
    pdm_rma = _wilder_rma(pdm)
    mdm_rma = _wilder_rma(mdm)

    # ── 3) ±DI 与 DX ────────────────────────────────────────────────
    plus_di = [None] * N
    minus_di = [None] * N
    dx = [None] * N
    for i in range(n, N):
        if tr_rma[i]:
            p = 100.0 * pdm_rma[i] / tr_rma[i]
            m = 100.0 * mdm_rma[i] / tr_rma[i]
            plus_di[i] = p
            minus_di[i] = m
            s = p + m
            dx[i] = 100.0 * abs(p - m) / s if s else 0.0

    # ── 4) ADX：首值 = DX[n .. 2n-1] 的简单均值（Wilder 原法），随后 α=1/n
    adx = [None] * N
    first_adx_idx = 2 * n - 1
    if first_adx_idx < N:
        adx[first_adx_idx] = sum(dx[n:2 * n]) / n
        for i in range(first_adx_idx + 1, N):
            adx[i] = (adx[i - 1] * (n - 1) + dx[i]) / n

    # ── 5) ADXR = (ADX[t] + ADX[t-n]) / 2 ───────────────────────────
    adxr = [None] * N
    for i in range(0, N):
        if adx[i] is not None and i - n >= 0 and adx[i - n] is not None:
            adxr[i] = (adx[i] + adx[i - n]) / 2.0

    return {
        "tr": tr, "plus_dm": pdm, "minus_dm": mdm,
        "tr_rma": tr_rma, "plus_dm_rma": pdm_rma, "minus_dm_rma": mdm_rma,
        "plus_di": plus_di, "minus_di": minus_di,
        "dx": dx, "adx": adx, "adxr": adxr,
        "n": n,
    }


def trend_state(plus_di, minus_di, adx, adx_prev=None) -> dict:
    """依据 ±DI 与 ADX 给出趋势状态判断。

    Args:
        plus_di, minus_di: 最新 +DI / -DI
        adx: 最新 ADX
        adx_prev: 上一期 ADX（用于判断 ADX 上升/回落，可为 None）

    Returns:
        dict:
            direction: 'bull' | 'bear' | None
            strength:  'strong' | 'mild' | 'weak' | None   (strong: ADX>=25, mild: 20~25, weak: <20)
            adx_rising: True | False | None
            label: 一句话中文结论
            phase: 'trend_up_strong' / 'trend_down_fading' / 'range' ... 便于前端取色
    """
    if plus_di is None or minus_di is None or adx is None:
        return {"direction": None, "strength": None, "adx_rising": None,
                "label": "数据不足，无法判断", "phase": "na"}

    direction = "bull" if plus_di > minus_di else "bear"
    if adx >= 25:
        strength = "strong"
    elif adx >= 20:
        strength = "mild"
    else:
        strength = "weak"

    adx_rising = None if adx_prev is None else (adx > adx_prev)

    dir_cn = "多头" if direction == "bull" else "空头"

    if strength == "weak":
        label = f"无趋势 / 震荡（ADX {adx:.1f} < 20），方向偏{dir_cn}但强度不足，信号易失效"
        phase = "range"
    else:
        if adx_rising is None:
            label = f"{dir_cn}趋势（ADX {adx:.1f}）"
            phase = "trend_up" if direction == "bull" else "trend_down"
        elif adx_rising:
            label = f"{dir_cn}趋势，强度增强（ADX {adx:.1f} 上升中）"
            phase = ("trend_up_strong" if direction == "bull" else "trend_down_strong")
        else:
            label = f"{dir_cn}趋势，动能衰竭（ADX {adx:.1f} 回落中），警惕反转"
            phase = ("trend_up_fading" if direction == "bull" else "trend_down_fading")

    return {"direction": direction, "strength": strength,
            "adx_rising": adx_rising, "label": label, "phase": phase}


# ── 自测 ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import math
    # 构造一段合成的趋势行情自测：先涨 60 根，再跌 60 根
    h, l, c = [], [], []
    px = 100.0
    for i in range(120):
        px += 1.2 if i < 60 else -1.5
        h.append(px + 0.8)
        l.append(px - 0.8)
        c.append(px)
    d = compute_dmi(h, l, c, 14)
    st = trend_state(d["plus_di"][-1], d["minus_di"][-1], d["adx"][-1], d["adx"][-2])
    print("bars:", len(c))
    print(f"+DI={d['plus_di'][-1]:.2f}  -DI={d['minus_di'][-1]:.2f}  "
          f"ADX={d['adx'][-1]:.2f}  ADXR={d['adxr'][-1]:.2f}")
    print("state:", st["label"])
