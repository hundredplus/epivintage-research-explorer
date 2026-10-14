"""Integration check using locally downloaded public ACEFA estimates."""

from pathlib import Path

import pytest

from epivintage.estimates import get_comparison, load_csvs


def test_acefa_act_influenza_a_revisions():
    folder = Path(__file__).resolve().parents[1] / "downloads"

    paths = [
        folder / "modelled_estimates_cases2025-07-17.csv",
        folder / "modelled_estimates_cases2025-08-07.csv",
    ]

    if not all(path.is_file() for path in paths):
        pytest.skip("ACEFA CSVs not downloaded locally")

    result = get_comparison(
        load_csvs(paths),
        "ACT",
        "Influenza A",
        "2025-07-17",
        "2025-08-07",
    )

    assert result["stats"] == {
        "overlapping_days": 1072,
        "mean_abs_revision": 0.04,
        "max_abs_revision": 2.48,
    }