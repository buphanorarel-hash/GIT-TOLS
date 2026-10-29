from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd

from .config import Settings, pip_size
from .signals import compute_frame


@dataclass
class BacktestResult:
    pair: str
    trades: int
    win_rate: float
    avg_r: float  # expectancy in R (risk multiples), after spread
    profit_factor: float
    total_r: float
    max_drawdown_r: float
    r_multiples: List[float]


def backtest(
    entry: pd.DataFrame, htf: pd.DataFrame, pair: str, s: Settings, spread_pips: float = 1.0
) -> BacktestResult:
    return backtest_frame(compute_frame(entry, htf, pair, s), entry, pair, s, spread_pips)


def backtest_frame(
    frame: pd.DataFrame, entry: pd.DataFrame, pair: str, s: Settings, spread_pips: float = 1.0
) -> BacktestResult:
    """Fresh-signal entries at next bar open; SL checked before TP inside a bar (conservative)."""
    score = frame["score"].to_numpy()
    atr_v = frame["atr"].to_numpy()
    idx = frame.index
    o, h, l, c = (entry.loc[idx, k].to_numpy() for k in ("Open", "High", "Low", "Close"))
    spread = spread_pips * pip_size(pair)

    results: List[float] = []
    i, n = 1, len(frame)
    while i < n - 1:
        prev, cur = score[i - 1], score[i]
        fresh = abs(cur) >= s.threshold and (abs(prev) < s.threshold or np.sign(prev) != np.sign(cur))
        if not fresh:
            i += 1
            continue
        side = 1 if cur > 0 else -1
        risk = atr_v[i] * s.atr_sl_mult
        # Longs fill at ask (open + spread), shorts at bid (open).
        fill = o[i + 1] + (spread if side > 0 else 0.0)
        sl, tp = fill - side * risk, fill + side * risk * s.rr
        exit_price, j = fill, i + 1
        for k in range(i + 1, min(i + 2 + s.max_hold_bars, n)):
            # Prices are bid-side: longs exit at bid, shorts exit at ask (bid + spread).
            if side > 0:
                hit_sl, hit_tp = l[k] <= sl, h[k] >= tp
            else:
                hit_sl, hit_tp = h[k] + spread >= sl, l[k] + spread <= tp
            if hit_sl:
                exit_price, j = sl, k
                break
            if hit_tp:
                exit_price, j = tp, k
                break
            j = k
            exit_price = c[k] if side > 0 else c[k] + spread
        results.append(side * (exit_price - fill) / risk)
        i = j + 1

    r = np.array(results, dtype=float)
    if len(r) == 0:
        return BacktestResult(pair, 0, 0.0, 0.0, 0.0, 0.0, 0.0, [])
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    equity = np.cumsum(r)
    dd = float((np.maximum.accumulate(equity) - equity).max())
    return BacktestResult(
        pair=pair,
        trades=len(r),
        win_rate=float((r > 0).mean()),
        avg_r=float(r.mean()),
        profit_factor=float(wins / losses) if losses > 0 else float("inf"),
        total_r=float(r.sum()),
        max_drawdown_r=dd,
        r_multiples=[float(x) for x in r],
    )
