"""Reproduce the Part C report experiments without modifying the graded config.

Run: python scripts/run_report_experiments.py
Results: reports/gameday/experiments.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gameday_lab.client import ResilientClient
from gameday_lab.sim.config import load_config
from gameday_lab.sim.engine import run_scenario


class UnfilteredClient(ResilientClient):
    """Experiment only: allow a tool call to reach a provider without tools."""

    def ladder(self, task: str) -> list[str]:
        return list(self.order)


def main() -> None:
    cfg = load_config()
    bad_breaker = {**cfg.client["breaker"], "min_calls": 1000000000}
    variants = {
        "budget_on_bad_breaker": {
            "max_attempts_per_provider": 5, "breaker": bad_breaker,
        },
        "budget_off_bad_breaker": {
            "max_attempts_per_provider": 5, "breaker": bad_breaker,
            "retry_budget_ratio": 100, "retry_budget_max_tokens": 1e9,
            "retry_budget_min_per_s": 1e6,
        },
        "timeout_30": {"attempt_timeout_s": 30},
        "unfiltered_tools": {},
    }
    results = {}
    for name, overrides in variants.items():
        variant = replace(cfg, client={**cfg.client, **overrides})
        if name.startswith("budget_"):
            keys = ["G2_overload_storm", "G3_brownout"]
        elif name == "timeout_30":
            keys = ["G6_provider_outage", "G4_slow_region"]
        else:
            keys = ["G6_provider_outage"]
        runs = {}
        for key in keys:
            client_cls = UnfilteredClient if name == "unfiltered_tools" else ResilientClient
            client = client_cls(variant.provider_infos(), variant.fallback_order, variant.client, seed=1)
            metrics = run_scenario(variant, key, client, seed=25).metrics()
            runs[key] = metrics
            print(f"{name} {key}: availability={metrics['availability']} "
                  f"amplification={metrics['amplification']} retry_ratio={metrics['retry_ratio']} "
                  f"recovery_s={metrics['recovery_s']} p95={metrics['latency_p95_s']} "
                  f"give_up_reasons={metrics['give_up_reasons']} "
                  f"incompatible_routes={metrics['incompatible_routes']}")
        results[name] = {"settings": variant.client, "metrics": runs}
    out = Path("reports/gameday/experiments.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
