from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import Settings, pip_size
from .indicators import adx, atr, ema, macd_hist, rsi

# Max points per component; they sum to 100.
W_HTF, W_TREND, W_MOMO, W_RSI, W_ADX = 30, 20, 20, 15, 15


@dataclass
class Signal:
    pair: str
    direction: str  # "BUY" | "SELL"
    score: float  # 0-100 strength
    time: str
    entry: float
    stop_loss: float
    take_profit: float
    risk_pips: float
    rr: float
    reasons: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _htf_trend(htf: pd.DataFrame) -> pd.Series:
    e50, e200 = ema(htf["Close"], 50), ema(htf["Close"], 200)
    raw = 0.5 * np.sign(e50 - e200) + 0.5 * np.sign(htf["Close"] - e50)
    return (raw * W_HTF).where(e200.notna())


def _rsi_component(r: pd.Series) -> pd.Series:
    """Healthy momentum scores in the 30-70 band; extremes flip toward mean reversion."""
    base = ((r - 50) / 15).clip(-1, 1)
    over = (1 - (r - 70) / 10).clip(-1, 1)
    under = -(1 - (30 - r) / 10).clip(-1, 1)
    return pd.Series(np.select([r > 70, r < 30], [over, under], base), index=r.index).where(r.notna()) * W_RSI


def compute_frame(entry: pd.DataFrame, htf: pd.DataFrame, pair: str, s: Settings) -> pd.DataFrame:
    """Per-bar signed score (-100..100) plus ATR; no lookahead into unfinished HTF bars."""
    close = entry["Close"]
    ema20, ema50 = ema(close, 20), ema(close, 50)
    hist = macd_hist(close)
    rsi14 = rsi(close)
    atr14 = atr(entry)
    trend_dir = np.sign(ema20 - ema50)

    # HTF bars are stamped at open; shift by one so a bar is only used once it has closed.
    htf_score = _htf_trend(htf).shift(1)
    htf_aligned = htf_score.reindex(entry.index.union(htf_score.index)).ffill().reindex(entry.index)

    comp = pd.DataFrame(index=entry.index)
    comp["htf"] = htf_aligned
    comp["trend"] = (0.5 * trend_dir + 0.5 * np.sign(close - ema50)) * W_TREND
    comp["momentum"] = (0.5 * np.sign(hist) + 0.5 * np.sign(hist.diff())) * W_MOMO
    comp["rsi"] = _rsi_component(rsi14)
    comp["adx"] = trend_dir * (((adx(entry) - 15) / 15).clip(0, 1)) * W_ADX

    out = comp.copy()
    out["score"] = comp.sum(axis=1, skipna=False)
    out["close"] = close
    out["atr"] = atr14
    out["rsi14"] = rsi14
    out["atr_pips"] = atr14 / pip_size(pair)
    # Dead markets give noisy signals and spreads eat the move.
    out.loc[out["atr_pips"] < s.min_atr_pips, "score"] = 0.0
    return out.dropna(subset=["score", "atr"])


def _reasons(row: pd.Series, direction: str) -> List[str]:
    sign = 1 if direction == "BUY" else -1
    word = "bullish" if sign > 0 else "bearish"
    out = []
    if row["htf"] * sign > W_HTF * 0.5:
        out.append(f"H1 trend {word} (price/EMA50/EMA200 aligned)")
    if row["trend"] * sign > W_TREND * 0.5:
        out.append(f"M15 trend {word} (EMA20 vs EMA50)")
    if row["momentum"] * sign > W_MOMO * 0.5:
        out.append(f"MACD momentum {word} and building")
    if row["rsi"] * sign > W_RSI * 0.5:
        out.append(f"RSI {row['rsi14']:.0f} supports {word} move")
    if row["adx"] * sign > W_ADX * 0.5:
        out.append("ADX shows trending market")
    return out


def build_signal(frame: pd.DataFrame, pair: str, s: Settings, idx: int = -1) -> Optional[Signal]:
    """Return a Signal for the bar at `idx` if its |score| clears the threshold."""
    if frame.empty:
        return None
    row = frame.iloc[idx]
    if abs(row["score"]) < s.threshold:
        return None
    direction = "BUY" if row["score"] > 0 else "SELL"
    risk = row["atr"] * s.atr_sl_mult
    sign = 1 if direction == "BUY" else -1
    entry = float(row["close"])
    digits = 3 if pair.endswith("JPY") else 5
    return Signal(
        pair=pair,
        direction=direction,
        score=round(float(abs(row["score"])), 1),
        time=frame.index[idx].isoformat(),
        entry=round(entry, digits),
        stop_loss=round(entry - sign * risk, digits),
        take_profit=round(entry + sign * risk * s.rr, digits),
        risk_pips=round(risk / pip_size(pair), 1),
        rr=s.rr,
        reasons=_reasons(row, direction),
    )
