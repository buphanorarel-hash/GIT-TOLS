import numpy as np
import pandas as pd
import pytest

from fxscanner.backtest import backtest
from fxscanner.config import Settings
from fxscanner.indicators import adx, atr, ema, rsi
from fxscanner.signals import build_signal, compute_frame


def make_ohlc(n, freq, drift=0.00005, noise=0.0002, seed=1, start=1.1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq=freq, tz="UTC")
    close = start + np.cumsum(drift + rng.normal(0, noise, n))
    open_ = np.concatenate([[start], close[:-1]])
    spread = np.abs(rng.normal(0, noise, n)) + 0.00005
    return pd.DataFrame(
        {"Open": open_, "High": np.maximum(open_, close) + spread, "Low": np.minimum(open_, close) - spread, "Close": close},
        index=idx,
    )


def test_rsi_bounds_and_trend():
    up = pd.Series(np.linspace(1, 2, 100))
    r = rsi(up)
    assert r.dropna().between(0, 100).all()
    assert r.iloc[-1] == 100


def test_ema_matches_pandas():
    s = pd.Series(np.arange(50, dtype=float))
    assert ema(s, 10).iloc[-1] == pytest.approx(s.ewm(span=10, adjust=False).mean().iloc[-1])


def test_atr_adx_positive():
    df = make_ohlc(300, "15min")
    assert (atr(df).dropna() > 0).all()
    assert adx(df).dropna().between(0, 100).all()


def _frames(drift):
    entry = make_ohlc(3000, "15min", drift=drift)
    htf = entry.resample("1h").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    return entry, htf


def test_uptrend_gives_buy_and_downtrend_gives_sell():
    s = Settings(threshold=50)
    up = compute_frame(*_frames(0.00008), "EURUSD", s)
    down = compute_frame(*_frames(-0.00008), "EURUSD", s)
    assert up["score"].tail(500).mean() > 20
    assert down["score"].tail(500).mean() < -20


def test_signal_levels_are_consistent():
    s = Settings(threshold=0)
    frame = compute_frame(*_frames(0.00008), "EURUSD", s)
    frame.loc[frame.index[-1], "score"] = 80.0
    sig = build_signal(frame, "EURUSD", s)
    assert sig.direction == "BUY"
    assert sig.stop_loss < sig.entry < sig.take_profit
    assert (sig.take_profit - sig.entry) == pytest.approx((sig.entry - sig.stop_loss) * s.rr, abs=3e-5)
    frame.loc[frame.index[-1], "score"] = -80.0
    sig = build_signal(frame, "EURUSD", s)
    assert sig.direction == "SELL" and sig.take_profit < sig.entry < sig.stop_loss


def test_below_threshold_gives_no_signal():
    s = Settings(threshold=65)
    frame = compute_frame(*_frames(0.00008), "EURUSD", s)
    frame.loc[frame.index[-1], "score"] = 10.0
    assert build_signal(frame, "EURUSD", s) is None


def test_htf_uses_only_closed_bars():
    entry, htf = _frames(0.00008)
    s = Settings()
    base = compute_frame(entry, htf, "EURUSD", s)["htf"]
    # Corrupt the very last H1 bar; entry bars before its close must not change.
    htf2 = htf.copy()
    htf2.iloc[-1] = htf2.iloc[-1] * 0.5
    changed = compute_frame(entry, htf2, "EURUSD", s)["htf"]
    cutoff = htf.index[-1] + pd.Timedelta(hours=1)
    assert base[base.index < cutoff].equals(changed[changed.index < cutoff])


def test_backtest_runs_and_is_sane():
    entry, htf = _frames(0.00008)
    res = backtest(entry, htf, "EURUSD", Settings(threshold=55), spread_pips=0.8)
    assert res.trades > 0
    assert -1.5 <= res.avg_r <= 2.5
    assert 0 <= res.win_rate <= 1
