from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from .backtest import backtest
from .config import DEFAULT_SPREAD_PIPS, MAJOR_PAIRS, Settings
from .data import fetch
from .scanner import scan


def _settings(args) -> Settings:
    return replace(Settings(), threshold=args.threshold, rr=args.rr, atr_sl_mult=args.sl_atr)


def cmd_scan(args) -> int:
    pairs = [p.upper() for p in args.pairs] or MAJOR_PAIRS
    res = scan(pairs, _settings(args))
    sigs = res["signals"]
    if not sigs:
        print(f"No setups >= {args.threshold:.0f} score across {res['scanned']} pairs right now.")
    for sg in sigs:
        print(f"\n{sg.direction:4} {sg.pair}  score {sg.score}  ({sg.time})")
        print(f"  entry {sg.entry}  SL {sg.stop_loss} ({sg.risk_pips} pips)  TP {sg.take_profit}  R:R 1:{sg.rr:g}")
        for r in sg.reasons:
            print(f"   - {r}")
    for pair, err in res["errors"].items():
        print(f"! {pair}: {err}", file=sys.stderr)
    return 0


def cmd_backtest(args) -> int:
    s = _settings(args)
    pairs = [p.upper() for p in args.pairs] or MAJOR_PAIRS
    print(f"{'pair':8}{'trades':>7}{'win%':>7}{'avgR':>8}{'PF':>7}{'totR':>8}{'maxDD':>8}")
    all_r = []
    for pair in pairs:
        try:
            entry = fetch(pair, s.entry_interval, s.entry_period)
            htf = fetch(pair, s.htf_interval, s.htf_period)
        except Exception as exc:
            print(f"{pair:8} data error: {exc}", file=sys.stderr)
            continue
        r = backtest(entry, htf, pair, s, DEFAULT_SPREAD_PIPS.get(pair, 1.5))
        all_r += r.r_multiples
        print(
            f"{pair:8}{r.trades:>7}{r.win_rate * 100:>6.0f}%{r.avg_r:>8.2f}"
            f"{r.profit_factor:>7.2f}{r.total_r:>8.1f}{r.max_drawdown_r:>8.1f}"
        )
    if all_r:
        wins = sum(x for x in all_r if x > 0)
        loss = -sum(x for x in all_r if x < 0)
        print(
            f"\nAll: {len(all_r)} trades, avg {sum(all_r) / len(all_r):.2f}R, "
            f"PF {wins / loss if loss else float('inf'):.2f}"
        )
    print("\nPast performance on ~2 months of data says little about the future. Treat as a sanity check only.")
    return 0


def cmd_web(args) -> int:
    from .web import create_app

    create_app(_settings(args)).run(host=args.host, port=args.port)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="fxscanner", description="Intraday forex setup scanner (signals only).")
    p.add_argument("--threshold", type=float, default=65.0, help="min score 0-100 (default 65)")
    p.add_argument("--rr", type=float, default=2.0, help="reward:risk (default 2)")
    p.add_argument("--sl-atr", type=float, default=1.5, help="stop = ATR * this (default 1.5)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scan", help="scan pairs now")
    sp.add_argument("pairs", nargs="*")
    sp.set_defaults(fn=cmd_scan)

    bp = sub.add_parser("backtest", help="backtest the scoring on recent history")
    bp.add_argument("pairs", nargs="*")
    bp.set_defaults(fn=cmd_backtest)

    wp = sub.add_parser("web", help="start the dashboard")
    wp.add_argument("--host", default="127.0.0.1")
    wp.add_argument("--port", type=int, default=5000)
    wp.set_defaults(fn=cmd_web)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
