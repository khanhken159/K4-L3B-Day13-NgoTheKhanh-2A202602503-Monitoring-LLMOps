from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percent / 100
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _number(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def _threshold_status(value: float | None, threshold: dict[str, Any]) -> str:
    if value is None:
        return "No data"
    threshold_value = float(threshold["value"])
    operator = threshold["operator"]
    good = value <= threshold_value if operator == "lte" else value >= threshold_value
    return "Within threshold" if good else "Threshold exceeded"


def load_dashboard_data(
    log_path: Path, config_path: Path, *, now: datetime | None = None
) -> dict[str, Any]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    dashboard = config["dashboard"]
    window_minutes = int(dashboard["time_range_minutes"])
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_minutes)

    records: list[dict[str, Any]] = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
                timestamp = datetime.fromisoformat(str(record["ts"]).replace("Z", "+00:00"))
                if timestamp >= cutoff:
                    records.append(record)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue

    by_event: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_event.setdefault(str(record.get("event", "")), []).append(record)

    requests = by_event.get("request_received", [])
    responses = by_event.get("response_sent", [])
    failures = by_event.get("request_failed", [])
    retrieval_attempts = [
        record
        for record in records
        if record.get("tool_name") == "retrieval" and isinstance(record.get("tool_success"), bool)
    ]
    success_rate = (
        sum(record["tool_success"] is True for record in retrieval_attempts)
        / len(retrieval_attempts)
        * 100
        if retrieval_attempts
        else None
    )

    values = {
        "latency": {
            "p50": _percentile([float(r["latency_ms"]) for r in responses if r.get("latency_ms") is not None], 50),
            "p95": _percentile([float(r["latency_ms"]) for r in responses if r.get("latency_ms") is not None], 95),
            "p99": _percentile([float(r["latency_ms"]) for r in responses if r.get("latency_ms") is not None], 99),
            "ttft_p95": _percentile([float(r["ttft_ms"]) for r in responses if r.get("ttft_ms") is not None], 95),
            "count": len(responses),
        },
        "traffic": {"count": len(requests), "per_minute": len(requests) / window_minutes},
        "errors": {
            "error_rate_pct": len(failures) / len(requests) * 100 if requests else None,
            "failed": len(failures),
            "requests": len(requests),
            "retrieval_success_pct": success_rate,
            "retrieval_attempts": len(retrieval_attempts),
        },
        "cost": {
            "total_usd": sum(float(r.get("cost_usd", 0) or 0) for r in responses),
            "response_count": len(responses),
        },
        "tokens": {
            "input": sum(int(r.get("tokens_in", 0) or 0) for r in responses),
            "output": sum(int(r.get("tokens_out", 0) or 0) for r in responses),
        },
        "quality": {
            "mean": mean([float(r["quality_score"]) for r in responses if r.get("quality_score") is not None])
            if any(r.get("quality_score") is not None for r in responses)
            else None,
            "count": sum(r.get("quality_score") is not None for r in responses),
        },
    }
    return {"dashboard": dashboard, "values": values, "record_count": len(records), "cutoff": cutoff, "now": now}


def render_dashboard(data: dict[str, Any]) -> str:
    dashboard = data["dashboard"]
    values = data["values"]
    generated = data["now"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    panels = {
        "latency": [
            ("P50 latency", _number(values["latency"]["p50"], 0), "ms"),
            ("P95 latency", _number(values["latency"]["p95"], 0), "ms"),
            ("P99 latency", _number(values["latency"]["p99"], 0), "ms"),
            ("TTFT P95", _number(values["latency"]["ttft_p95"], 0), "ms"),
        ],
        "traffic": [
            ("Requests", str(values["traffic"]["count"]), "in window"),
            ("Request rate", _number(values["traffic"]["per_minute"], 2), "requests/min"),
        ],
        "errors": [
            ("Error rate", _number(values["errors"]["error_rate_pct"], 2), "%"),
            ("Failed requests", str(values["errors"]["failed"]), "requests"),
            ("Retrieval success", _number(values["errors"]["retrieval_success_pct"], 1), "%"),
        ],
        "cost": [("Total cost", _number(values["cost"]["total_usd"], 6), "USD")],
        "tokens": [
            ("Input tokens", f"{values['tokens']['input']:,}", "tokens"),
            ("Output tokens", f"{values['tokens']['output']:,}", "tokens"),
        ],
        "quality": [("Mean quality proxy", _number(values["quality"]["mean"], 2), "score / 1")],
    }

    cards: list[str] = []
    for panel in dashboard["panels"]:
        panel_id = panel["id"]
        threshold = panel["threshold"]
        aggregate_values = {
            "p50": values["latency"]["p50"],
            "p95": values["latency"]["p95"],
            "p99": values["latency"]["p99"],
            "ttft_p95": values["latency"]["ttft_p95"],
            "rate_per_minute": values["traffic"]["per_minute"],
            "error_rate_pct": values["errors"]["error_rate_pct"],
            "tool_success_rate_pct": values["errors"]["retrieval_success_pct"],
            "total": values["cost"]["total_usd"],
            "sum_by_field": values["tokens"]["input"] + values["tokens"]["output"],
            "mean": values["quality"]["mean"],
        }
        threshold_value = aggregate_values.get(threshold["aggregation"])
        status = _threshold_status(threshold_value, threshold)
        status_class = "ok" if status == "Within threshold" else "alert" if status == "Threshold exceeded" else "empty"
        metrics = "".join(
            "<div class='metric'>"
            f"<span>{html.escape(label)}</span>"
            f"<strong>{html.escape(value)}</strong>"
            f"<small>{html.escape(unit)}</small>"
            "</div>"
            for label, value, unit in panels[panel_id]
        )
        cards.append(
            f"<section class='panel'><div class='panel-head'><h2>{html.escape(panel['title'])}</h2>"
            f"<span class='status {status_class}'>{html.escape(status)}</span></div>"
            f"<div class='metrics'>{metrics}</div>"
            f"<div class='threshold'>Threshold: {html.escape(threshold['aggregation'])} "
            f"{html.escape(threshold['operator'])} {html.escape(str(threshold['value']))} {html.escape(panel['unit'])}</div>"
            f"<div class='source'>Source: {html.escape(panel['source'])} · events: {html.escape(', '.join(panel['events']))}</div></section>"
        )

    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Day 13 Monitoring Dashboard</title><style>
:root{color-scheme:dark;--bg:#10131b;--surface:#191e29;--line:#2b3342;--text:#edf2fa;--muted:#a5b0c2;--blue:#80b7ff;--green:#77d5a3;--red:#ff8989}
*{box-sizing:border-box}body{margin:0;padding:34px;background:radial-gradient(ellipse at 20% -10%,#1d3150 0,transparent 42%),var(--bg);color:var(--text);font:15px/1.45 Segoe UI,Arial,sans-serif}
header{max-width:1200px;margin:0 auto 24px}h1{font-size:28px;margin:0 0 8px}header p{color:var(--muted);margin:0}.grid{max-width:1200px;margin:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.panel{background:linear-gradient(145deg,#1b2230,#171b25);border:1px solid var(--line);border-radius:14px;padding:20px;min-height:190px;box-shadow:0 12px 28px #0003}.panel-head{display:flex;justify-content:space-between;align-items:start;gap:10px}h2{font-size:17px;margin:0 0 18px}.status{font-size:11px;font-weight:700;border-radius:99px;padding:5px 9px;white-space:nowrap}.ok{color:var(--green);background:#18372b}.alert{color:var(--red);background:#402323}.empty{color:#ffd67c;background:#3b321c}
.metrics{display:flex;flex-wrap:wrap;gap:12px}.metric{flex:1 1 115px;display:flex;flex-direction:column;gap:3px}.metric span,.metric small{color:var(--muted);font-size:12px}.metric strong{font-size:24px;color:var(--blue);letter-spacing:-.4px}.threshold{margin-top:18px;border-top:1px solid var(--line);padding-top:12px;font-size:12px;color:#d4dceb}.source{margin-top:7px;font-size:11px;color:#8995a8}footer{max-width:1200px;margin:18px auto 0;color:#8591a3;font-size:12px}
@media(max-width:760px){body{padding:20px}.grid{grid-template-columns:1fr}}
</style></head><body>
<header><h1>""" + html.escape(dashboard["title"]) + """</h1>
<p>Last """ + str(dashboard["time_range_minutes"]) + """ minutes · refresh target """ + str(dashboard["refresh_seconds"]) + """ seconds · generated """ + generated + """</p></header>
<main class="grid">""" + "".join(cards) + """</main>
<footer>""" + str(data["record_count"]) + """ structured log records in the selected window · generated from data/logs.jsonl</footer>
</body></html>"""


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Render the six-panel dashboard from JSONL logs")
    parser.add_argument("--logs", type=Path, default=REPO_ROOT / "data" / "logs.jsonl")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "dashboard.yaml")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "submission" / "evidence" / "11-dashboard-overview.html",
    )
    args = parser.parse_args()
    data = load_dashboard_data(args.logs, args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_dashboard(data), encoding="utf-8")
    print(f"Dashboard written: {args.output}")
    print(f"Records in {data['dashboard']['time_range_minutes']}m window: {data['record_count']}")
    print("Panels: 6/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
