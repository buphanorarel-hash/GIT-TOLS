from __future__ import annotations

from dataclasses import dataclass

MAJOR_PAIRS = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
]

# Typical retail spread in pips, used by the backtester.
DEFAULT_SPREAD_PIPS = {
    "EURUSD": 0.8,
    "GBPUSD": 1.2,
    "USDJPY": 1.0,
    "USDCHF": 1.5,
    "AUDUSD": 1.2,
    "USDCAD": 1.5,
    "NZDUSD": 1.8,
    "EURJPY": 1.8,
    "GBPJPY": 2.5,
    "EURGBP": 1.5,
}


def pip_size(pair: str) -> float:
    return 0.01 if pair.endswith("JPY") else 0.0001


@dataclass(frozen=True)
class Settings:
    entry_interval: str = "15m"
    htf_interval: str = "1h"
    entry_period: str = "59d"  # yfinance caps 15m history at 60 days
    htf_period: str = "59d"
    threshold: float = 65.0  # minimum |score| (0-100) to emit a signal
    atr_sl_mult: float = 1.5  # stop distance = ATR * this
    rr: float = 2.0  # take profit = risk * this
    min_atr_pips: float = 3.0  # skip dead markets
    max_hold_bars: int = 48  # backtest time stop (12h on M15)
