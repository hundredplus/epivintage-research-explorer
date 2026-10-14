"""Offline contract tests modelled on ACEFA's published CSV layout.

The production-sized CSVs are downloaded separately on the user's machine.
"""
from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
import pytest

from epivintage.demo_data import create_demo
from epivintage.estimates import InvalidEstimates, get_comparison, get_options, load_csvs, validate
from epivintage.fetch_acefa import BASE_URL, download_vintage


def test_r_output_layout_with_additional_t_step(tmp_path):
    """ACEFA 2025 outputs include t_step, which is not required by our adapter."""
    source = pd.read_csv(create_demo(tmp_path / "example.csv"))
    source.insert(1, "t_step", np.arange(1, len(source) + 1))
    a, b = (source[source.origin.eq(day)].copy() for day in ("2025-07-17", "2025-08-07"))
    p, q = tmp_path / "vintage_one.csv", tmp_path / "vintage_two.csv"
    a.to_csv(p, index=False)
    b.to_csv(q, index=False)
    actual = load_csvs([p, q])
    assert len(actual) == len(source)
    assert "source_file" in actual.columns
    assert "t_step" not in actual.columns
    comparison = get_comparison(actual, "VIC", "RSV", "2025-07-17", "2025-08-07")
    assert comparison["provenance"] == {"first": [p.name], "second": [q.name]}
    assert [row["date"] for row in comparison["first"]] == [row["date"] for row in comparison["second"]]


def test_only_valid_options_are_advertised(tmp_path):
    data = load_csvs([create_demo(tmp_path / "example.csv")])
    data = data[~((data.location.eq("VIC")) & (data.pathogen.eq("RSV")) & (data.origin.eq(pd.Timestamp("2025-08-07"))))]
    options = get_options(data)
    assert options["availability"]["VIC"]["RSV"] == ["2025-07-17"]
    assert options["availability"]["NSW"]["RSV"] == ["2025-07-17", "2025-08-07"]


@pytest.mark.parametrize("first,second", [
    ("2025-08-07", "2025-07-17"),
    ("2025-07-17", "2025-07-17"),
    ("bad-date", "2025-08-07"),
])
def test_reject_invalid_reporting_order(tmp_path, first, second):
    df = load_csvs([create_demo(tmp_path / "example.csv")])
    with pytest.raises(InvalidEstimates):
        get_comparison(df, "VIC", "RSV", first, second)


def test_reject_non_finite_values(tmp_path):
    df = load_csvs([create_demo(tmp_path / "example.csv")])
    df.loc[0, "y"] = float("inf")
    with pytest.raises(InvalidEstimates, match="non-finite"):
        validate(df)


def test_reject_duplicate_scientific_keys(tmp_path):
    df = load_csvs([create_demo(tmp_path / "example.csv")])
    with pytest.raises(InvalidEstimates, match="Repeated"):
        validate(pd.concat([df, df.iloc[[0]]], ignore_index=True))


def test_download_acefa_public_file_with_mocked_network(tmp_path, monkeypatch):
    """Exercise actual downloader/CSV checks without depending on GitHub availability."""
    df = pd.read_csv(create_demo(tmp_path / "demo.csv"))
    df = df[df.origin.eq("2025-07-17")].copy()
    df["t_step"] = range(1, len(df) + 1)
    payload = df.to_csv(index=False).encode()

    import epivintage.fetch_acefa as download_module

    def fake_open(request, timeout):
        assert request.full_url == BASE_URL.format(date="2025-07-17")
        return BytesIO(payload)

    monkeypatch.setattr(download_module, "urlopen", fake_open)
    out = download_vintage("2025-07-17", tmp_path / "downloads")
    assert out["rows"] == len(df)
    assert out["bytes"] == len(payload)
    assert len(out["sha256"]) == 64
    assert (tmp_path / "downloads" / out["filename"]).read_bytes() == payload


def test_reject_mismatched_origin_from_download(tmp_path, monkeypatch):
    df = pd.read_csv(create_demo(tmp_path / "demo.csv"))
    wrong = df[df.origin.eq("2025-08-07")].to_csv(index=False).encode()
    import epivintage.fetch_acefa as download_module
    monkeypatch.setattr(download_module, "urlopen", lambda req, timeout: BytesIO(wrong))
    dest = tmp_path / "downloads"
    with pytest.raises(InvalidEstimates, match="unexpected origin"):
        download_vintage("2025-07-17", dest)
    assert not list(dest.glob("*.csv"))
    assert not list(dest.glob(".epivintage-*"))
