from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

from .config import MAJOR_PAIRS, Settings
from .data import fetch
from .signals import Signal, build_signal, compute_frame


def scan_pair(pair: str, s: Settings, cache_ttl: int = 0) -> Tuple[Optional[Signal], Optional[str]]:
    """Returns (signal or None, error message or None)."""
    try:
        entry = fetch(pair, s.entry_interval, s.entry_period, cache_ttl)
        htf = fetch(pair, s.htf_interval, s.htf_period, cache_ttl)
        frame = compute_frame(entry, htf, pair, s)
        return build_signal(frame, pair, s), None
    except Exception as exc:  # one bad pair must not kill the scan
        return None, f"{type(exc).__name__}: {exc}"


def scan(pairs: List[str] = None, s: Settings = None, cache_ttl: int = 0) -> Dict[str, object]:
    pairs = pairs or MAJOR_PAIRS
    s = s or Settings()
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda p: scan_pair(p, s, cache_ttl), pairs))
    signals = sorted((sig for sig, _ in results if sig), key=lambda x: -x.score)
    errors = {p: err for p, (_, err) in zip(pairs, results) if err}
    return {"signals": signals, "errors": errors, "scanned": len(pairs)}
