"""Generate completely synthetic research-estimate vintages.

Not disease surveillance data and not ACEFA estimates. Used only to show UI behaviour.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def create_demo(path: Path, seed: int = 2026) -> Path:
    rng = np.random.default_rng(seed)
    jurisdictions = ["VIC", "NSW", "QLD"]
    pathogens = ["Influenza total", "RSV", "SARS-CoV-2"]
    days = pd.date_range("2025-06-01", "2025-08-10", freq="D")
    vintages = [pd.Timestamp("2025-07-17"), pd.Timestamp("2025-08-07")]
    records = []
    for loc_index, location in enumerate(jurisdictions):
        for pathogen_index, pathogen in enumerate(pathogens):
            center = 38 + (pathogen_index * 4) + (loc_index * 2)
            base = 15 + 160 * np.exp(-0.5 * ((np.arange(len(days)) - center) / 12) ** 2)
            base *= 0.65 + 0.16 * loc_index + 0.09 * pathogen_index
            persistent = rng.normal(0, 3.0, len(days))
            for vintage in vintages:
                for j, day in enumerate(days):
                    if day > vintage:
                        continue
                    lag_days = (vintage - day).days
                    revision = 9 * np.exp(-lag_days / 12.0) if vintage == vintages[0] else -3 * np.exp(-lag_days / 12.0)
                    median = max(0.0, float(base[j] + persistent[j] + revision))
                    unc = 7.5 + 0.14 * median + 12 * np.exp(-lag_days / 10.0)
                    records.append({
                        "time": day.date().isoformat(),
                        "origin": vintage.date().isoformat(),
                        "location": location,
                        "pathogen": pathogen,
                        "y": round(median, 2),
                        "lb_50": round(max(0, median - 0.674 * unc), 2),
                        "ub_50": round(median + 0.674 * unc, 2),
                        "lb_95": round(max(0, median - 1.96 * unc), 2),
                        "ub_95": round(median + 1.96 * unc, 2),
                    })
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(path, index=False)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description="Generate synthetic example estimates")
    p.add_argument("--output", type=Path, default=Path("data/demo_estimates.csv"))
    p.add_argument("--seed", type=int, default=2026)
    a = p.parse_args()
    print(create_demo(a.output, a.seed))


if __name__ == "__main__":
    main()
