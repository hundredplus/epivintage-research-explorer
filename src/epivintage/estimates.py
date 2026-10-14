"""Validate and compare publication-date vintages of modelled epidemic estimates.

The tool consumes ACEFA situational assessment *estimates*, not incident case
observations or validated future forecasts.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

FIELDS = ["time", "origin", "location", "pathogen", "y", "lb_50", "ub_50", "lb_95", "ub_95"]
VALUES = ["y", "lb_50", "ub_50", "lb_95", "ub_95"]
KEYS = ["origin", "time", "location", "pathogen"]


class InvalidEstimates(ValueError):
    """An input file cannot be safely represented or compared."""


def validate(frame: pd.DataFrame) -> pd.DataFrame:
    """Check the expected ACEFA output contract and credible interval nesting.

    This is not an independent audit of the underlying statistical model.
    Extra source columns (such as ACEFA's t_step) are accepted but ignored.
    """
    missing = [field for field in FIELDS if field not in frame.columns]
    if missing:
        raise InvalidEstimates(f"Missing columns: {', '.join(missing)}")
    if frame.empty:
        raise InvalidEstimates("No estimate rows in input")

    wanted = FIELDS + (["source_file"] if "source_file" in frame.columns else [])
    df = frame[wanted].copy()
    for field in ("time", "origin"):
        df[field] = pd.to_datetime(df[field], errors="coerce").dt.normalize()
    if df[["time", "origin"]].isna().any().any():
        raise InvalidEstimates("Invalid time or origin date (expected ISO YYYY-MM-DD)")

    for field in ("location", "pathogen"):
        if df[field].isna().any() or df[field].astype(str).str.strip().eq("").any():
            raise InvalidEstimates(f"Missing {field} identifier")
        df[field] = df[field].astype(str).str.strip()

    for field in VALUES:
        df[field] = pd.to_numeric(df[field], errors="coerce")
    if not np.isfinite(df[VALUES].to_numpy(dtype=float)).all():
        raise InvalidEstimates("Missing or non-finite estimate/credible-interval value")
    if (df[VALUES] < 0).any().any():
        raise InvalidEstimates("Negative case estimate or credible-interval bound")

    ordered = (
        (df["lb_95"] <= df["lb_50"])
        & (df["lb_50"] <= df["y"])
        & (df["y"] <= df["ub_50"])
        & (df["ub_50"] <= df["ub_95"])
    )
    if not ordered.all():
        raise InvalidEstimates(f"Invalid credible interval ordering in {int((~ordered).sum())} row(s)")
    if df.duplicated(KEYS).any():
        raise InvalidEstimates("Repeated origin/time/location/pathogen combination")
    if "source_file" in df.columns:
        if df["source_file"].isna().any():
            raise InvalidEstimates("Missing source filename")
        df["source_file"] = df["source_file"].astype(str)

    return df.sort_values(KEYS).reset_index(drop=True)


def load_csvs(paths: list[Path]) -> pd.DataFrame:
    """Load file(s) once and retain filename provenance for each observation."""
    if not paths:
        raise InvalidEstimates("No CSV input files were provided")
    frames = []
    for path in paths:
        try:
            frame = pd.read_csv(path)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            raise InvalidEstimates(f"Cannot read {path}: {exc}") from exc
        frame["source_file"] = path.name
        frames.append(frame)
    return validate(pd.concat(frames, ignore_index=True))


def data_paths() -> list[Path]:
    configured = os.getenv("EPIVINTAGE_FILES", "").strip()
    if configured:
        return [Path(item.strip()).expanduser() for item in configured.split(os.pathsep) if item.strip()]
    return [Path(__file__).resolve().parents[2] / "data" / "demo_estimates.csv"]


def get_options(df: pd.DataFrame) -> dict:
    """Report only observed location/pathogen/vintage combinations."""
    availability: dict[str, dict[str, list[str]]] = {}
    for (location, pathogen), sub in df.groupby(["location", "pathogen"], sort=True):
        availability.setdefault(location, {})[pathogen] = sorted(
            sub.origin.dt.strftime("%Y-%m-%d").unique().tolist()
        )
    return {
        "locations": sorted(df.location.unique().tolist()),
        "pathogens": sorted(df.pathogen.unique().tolist()),
        "vintages": sorted(df.origin.dt.strftime("%Y-%m-%d").unique().tolist()),
        "availability": availability,
    }


def get_comparison(df: pd.DataFrame, location: str, pathogen: str, first: str, second: str) -> dict:
    """Compare only overlapping estimate dates from two ordered vintages."""
    try:
        first_ts, second_ts = pd.Timestamp(first), pd.Timestamp(second)
    except (ValueError, TypeError) as exc:
        raise InvalidEstimates("Reporting dates must use ISO YYYY-MM-DD") from exc
    if pd.isna(first_ts) or pd.isna(second_ts) or first_ts >= second_ts:
        raise InvalidEstimates("Select an earlier and a strictly later reporting date")

    subset = df[(df.location == location) & (df.pathogen == pathogen)]
    left = subset.loc[subset.origin.eq(first_ts)]
    right = subset.loc[subset.origin.eq(second_ts)]
    for label, data in ((first, left), (second, right)):
        if data.empty:
            raise InvalidEstimates(f"No model estimates for {location}, {pathogen}, reporting date {label}")

    paired = left.merge(right, on="time", how="inner", suffixes=("_first", "_second"), validate="one_to_one")
    paired = paired.sort_values("time")
    if paired.empty:
        raise InvalidEstimates("Selected reporting vintages have no overlapping estimate dates")

    def series(suffix: str) -> list[dict]:
        return [
            {"date": row.time.date().isoformat(), **{key: float(getattr(row, key + suffix)) for key in VALUES}}
            for row in paired.itertuples(index=False)
        ]

    revisions = paired["y_second"] - paired["y_first"]
    provenance = {}
    for label, data in (("first", left), ("second", right)):
        provenance[label] = sorted(data["source_file"].unique().tolist()) if "source_file" in data else []

    return {
        "first": series("_first"),
        "second": series("_second"),
        "stats": {
            "overlapping_days": int(len(paired)),
            "mean_abs_revision": round(float(revisions.abs().mean()), 2),
            "max_abs_revision": round(float(revisions.abs().max()), 2),
        },
        "revisions": [
            {"date": time.date().isoformat(), "delta": round(float(delta), 2)}
            for time, delta in zip(paired["time"], revisions)
        ],
        "provenance": provenance,
    }
