# FX Scanner

Scans major forex pairs on **M15** (entries) with an **H1** trend bias and lists scored trade setups
with entry, ATR-based stop-loss and take-profit. **Signals only: it never places orders.**

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Use

```bash
.venv/bin/python -m fxscanner.cli scan                 # scan all majors now
.venv/bin/python -m fxscanner.cli scan EURUSD GBPUSD   # specific pairs
.venv/bin/python -m fxscanner.cli --threshold 50 scan  # lower the score cutoff
.venv/bin/python -m fxscanner.cli backtest             # test the scoring on ~2 months of history
.venv/bin/python -m fxscanner.cli web                  # dashboard at http://127.0.0.1:5000
.venv/bin/python -m pytest                             # tests
```

## How the score works (0-100, signed)

| Component | Max | Meaning |
|---|---|---|
| H1 trend | 30 | price vs EMA50 vs EMA200 (closed H1 bars only, no lookahead) |
| M15 trend | 20 | EMA20 vs EMA50, price vs EMA50 |
| Momentum | 20 | MACD histogram sign and direction |
| RSI | 15 | healthy 30-70 momentum; extremes flip to mean reversion |
| ADX | 15 | trend strength, signed by trend direction |

A signal needs `|score| >= threshold` (default 65). Stop = 1.5 x ATR, target = 2 x risk. Markets with
ATR under 3 pips are skipped.

## Important: no proven edge yet

On the last ~59 days of data (all 10 pairs, spreads included) the default scoring **loses**
(about -0.19R per trade, profit factor ~0.7), and no threshold / R:R / stop combination fixed it.
A pullback-in-trend variant came out near breakeven, still not profitable. Treat this as a
framework for building and testing strategies, not as a money machine. Use `backtest` on any
change, and demo-trade before risking real money.

Data comes from Yahoo Finance via `yfinance`: free but delayed and unofficial, and 15m history is
capped at ~60 days. Swap `fxscanner/data.py` for OANDA or another broker feed for live use.

Not financial advice.
