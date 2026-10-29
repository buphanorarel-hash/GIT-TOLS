from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import pandas as pd

CACHE_DIR = Path(".cache")
INTERVAL_MINUTES = {"15m": 15, "30m": 30, "1h": 60}


def yf_symbol(pair: str) -> str:
    return f"{pair}=X"


def fetch(pair: str, interval: str, period: str, cache_ttl: int = 0) -> pd.DataFrame:
    """Download OHLC bars and drop the still-forming last bar.

    cache_ttl: seconds a cached CSV stays valid (0 disables caching).
    """
    cache_file: Optional[Path] = None
    if cache_ttl > 0:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file = CACHE_DIR / f"{pair}_{interval}_{period}.csv"
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < cache_ttl:
            return pd.read_csv(cache_file, index_col=0, parse_dates=True)

    import yfinance as yf

    df = yf.Ticker(yf_symbol(pair)).history(period=period, interval=interval, auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError(f"No data returned for {pair} ({interval})")
    df = df[["Open", "High", "Low", "Close"]].dropna()
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[~df.index.duplicated(keep="last")].sort_index()

    # Last bar is incomplete if its close time is still in the future.
    bar = pd.Timedelta(minutes=INTERVAL_MINUTES[interval])
    if len(df) and df.index[-1] + bar > pd.Timestamp.now(tz="UTC"):
        df = df.iloc[:-1]

    if cache_file is not None:
        df.to_csv(cache_file)
    return df
