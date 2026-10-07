# 588000 DMI 趋势看板 / STAR50 ETF DMI Dashboard

用 **Wilder 标准 DMI（动向指标）** 分析 588000 科创50ETF 的走势与趋势强度。
纯 Python 标准库实现，**零第三方依赖**，含可复用计算模块 + 本地可视化看板。

**在线看板**：https://wepoets1107.github.io/star50-dmi/

---

## 快速开始

```bash
# 直接启动（后台无窗口）
pythonw.exe server.py

# 或双击
start_service.bat
```

浏览器打开 **http://localhost:5059**

---

## DMI 计算模块（可复用）

`dmi.py` 是独立模块，其他脚本可直接 `import`：

```python
from dmi import compute_dmi, trend_state

d = compute_dmi(high_list, low_list, close_list, n=14)
# d["plus_di"], d["minus_di"], d["dx"], d["adx"], d["adxr"]  —— 等长 list，无值处为 None

st = trend_state(d["plus_di"][-1], d["minus_di"][-1], d["adx"][-1], d["adx"][-2])
# st["direction"]  'bull' / 'bear'
# st["strength"]   'strong'(ADX>=25) / 'mild'(20~25) / 'weak'(<20)
# st["adx_rising"] True / False
# st["label"]      一句话中文结论
# st["phase"]      便于取色的枚举：trend_up_strong / trend_down_fading / range ...
```

---

## 指标口径（严格对齐 Wilder 1978 / TA-Lib）

| 项 | 公式 |
|---|---|
| TR | `max(H−L, \|H−Cprev\|, \|L−Cprev\|)` |
| +DM | `H−Hprev`，当且仅当 `H−Hprev > Lprev−L` 且 `> 0`，否则 0 |
| −DM | `Lprev−L`，当且仅当 `Lprev−L > H−Hprev` 且 `> 0`，否则 0 |
| 平滑 | **Wilder RMA（α = 1/n）**，首值 = 前 n 个原始值之和，随后递推 |
| +DI / −DI | `100 × RMA(±DM) / RMA(TR)` |
| DX | `100 × \|+DI − −DI\| / (+DI + −DI)` |
| ADX | `RMA(DX, n)`，首值取前 n 个 DX 的简单均值 |
| ADXR | `(ADX[t] + ADX[t−n]) / 2` |

> **三个坑（本模块已避开）**
> 1. **平滑方式**：必须用 Wilder RMA，不能用 EMA——很多库用 EMA 会让 ADX 偏差 30%+、金叉死叉时点全乱。
> 2. **DM 定义**：是"方向性移动"的比较结果，不是简单高低差。
> 3. **预热长度**：首个 ADX 在第 `2n` 根（n=14 → 第 28 根），首个 ADXR 在第 `3n` 根；实际要 100+ 根才稳定。

---

## 趋势判断标准

| +DI / −DI | ADX 走向 | 结论 |
|---|---|---|
| +DI > −DI | 上升 | 多头趋势，强度增强 |
| +DI > −DI | 下降 | 多头趋势，动能衰竭 |
| −DI > +DI | 上升 | 空头趋势，强度增强 |
| −DI > +DI | 下降 | 空头趋势，动能衰竭 |
| 任意 | ADX < 20 | 无趋势 / 震荡，信号易失效 |
| 任意 | ADX > 25 | 趋势确立 |

---

## 文件结构

| 文件 | 说明 |
|---|---|
| `dmi.py` | **可复用 DMI 模块**（Wilder 标准，零依赖），含自测 |
| `fetch.py` | Yahoo Finance 日线 OHLC 拉取 + 本地缓存（标准库 urllib） |
| `server.py` | 看板后端（标准库 http.server，无需 Flask） |
| `templates/dashboard.html` | 前端看板（Chart.js 三图联动） |
| `start_service.bat` | 一键启动（含端口占用守卫） |
| `build.py` | 生成静态快照 → `docs/index.html`（GitHub Pages 用） |

数据源：Yahoo Finance chart API（免鉴权），588000.SS 自 2020-09-28 上市起全历史。

---

## 部署到 GitHub Pages

GitHub Pages 是纯静态托管、**没有后端**，`/api/report` 不可用。
因此 `build.py` 会把 DMI 报告序列化后**内联**注入页面（`window.__REPORT__`），
前端优先读内联快照，读不到才回退到 fetch —— 同一份模板本地服务和静态部署都能跑。

```bash
python build.py          # 生成 docs/index.html + docs/.nojekyll
```

推送后仓库 Settings → Pages 选 `main` 分支 `/docs` 目录即可。

> ⚠️ **静态页是生成时刻的快照**（页面顶部会显示"数据至 XXXX-XX-XX"）。
> 要看最新行情，请本地启动服务，或重新跑一次 `build.py`。

---

## 看板内容

1. 顶部：最新价 + 涨跌 + 趋势状态徽章
2. 指标卡：+DI / −DI / ADX / ADXR
3. 图①：价格走势
4. 图②：+DI / −DI（方向）
5. 图③：ADX（强度，含 20/25 参考线）
6. 表④：历史信号（±DI 交叉 / ADX 穿越，最近 25 条）
7. 表⑤：趋势分段（ADX ≥ 25 的连续区间）

---

## 已知局限

- **ADX 只衡量趋势强弱，不带方向**，须与 ±DI 配合解读。
- 震荡市（ADX < 20）中 ±DI 交叉会频繁假信号，这正是 ADX 过滤门槛存在的意义。
- 日线 DMI 滞后于价格，属于**趋势确认**工具而非**择时**工具。
- 数据源为 Yahoo（有零星缺日），已按缺失跳过处理。
