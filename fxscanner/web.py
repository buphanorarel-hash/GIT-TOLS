from __future__ import annotations

import threading
import time

from flask import Flask, jsonify, render_template_string

from .config import Settings
from .scanner import scan

CACHE_SECONDS = 120

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>FX Scanner</title>
<style>
 body{font-family:system-ui,sans-serif;background:#0f1419;color:#e6e6e6;margin:0;padding:24px}
 h1{margin:0 0 4px} .sub{color:#8b98a5;margin-bottom:16px;font-size:14px}
 table{border-collapse:collapse;width:100%} th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #26303b}
 th{color:#8b98a5;font-weight:600;font-size:13px}
 .BUY{color:#2ecc71;font-weight:700} .SELL{color:#ff5c5c;font-weight:700}
 .bar{background:#26303b;border-radius:4px;width:90px;height:8px;display:inline-block;vertical-align:middle}
 .bar i{display:block;height:100%;border-radius:4px;background:#4da3ff}
 .why{color:#8b98a5;font-size:12px} .warn{margin-top:20px;color:#8b98a5;font-size:12px}
 .err{color:#ffb347;font-size:13px}
</style></head><body>
<h1>FX Scanner</h1>
<div class="sub" id="status">Loading…</div>
<table><thead><tr><th>Pair</th><th>Side</th><th>Score</th><th>Entry</th><th>Stop</th><th>Target</th><th>Risk (pips)</th><th>Why</th></tr></thead>
<tbody id="rows"></tbody></table>
<div class="err" id="errs"></div>
<div class="warn">Signals only, not financial advice. Always size positions to your risk and test on a demo account first.</div>
<script>
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load(){
  try{
    const d = await (await fetch('/api/signals')).json();
    document.getElementById('status').textContent =
      `Scanned ${d.scanned} pairs · updated ${new Date(d.updated*1000).toLocaleTimeString()} · M15 entries, H1 bias`;
    document.getElementById('rows').innerHTML = d.signals.length ? d.signals.map(s => `
      <tr><td><b>${esc(s.pair)}</b></td><td class="${esc(s.direction)}">${esc(s.direction)}</td>
      <td><span class="bar"><i style="width:${Number(s.score)}%"></i></span> ${Number(s.score)}</td>
      <td>${s.entry}</td><td>${s.stop_loss}</td><td>${s.take_profit}</td><td>${s.risk_pips}</td>
      <td class="why">${s.reasons.map(esc).join('<br>')}</td></tr>`).join('')
      : '<tr><td colspan="8">No qualifying setups right now.</td></tr>';
    document.getElementById('errs').textContent = Object.entries(d.errors).map(([p,e]) => p+': '+e).join(' | ');
  }catch(e){ document.getElementById('status').textContent = 'Failed to load: '+e; }
}
load(); setInterval(load, 60000);
</script></body></html>"""


def create_app(settings: Settings = None) -> Flask:
    settings = settings or Settings()
    app = Flask(__name__)
    lock = threading.Lock()
    state = {"at": 0.0, "payload": None}

    @app.get("/")
    def index():
        return render_template_string(PAGE)

    @app.get("/api/signals")
    def api_signals():
        with lock:
            if state["payload"] is None or time.time() - state["at"] > CACHE_SECONDS:
                res = scan(s=settings, cache_ttl=CACHE_SECONDS)
                state["payload"] = {
                    "signals": [x.to_dict() for x in res["signals"]],
                    "errors": res["errors"],
                    "scanned": res["scanned"],
                    "updated": time.time(),
                }
                state["at"] = time.time()
            return jsonify(state["payload"])

    return app
