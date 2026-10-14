from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from epivintage.app import app, table
from epivintage.demo_data import create_demo
from epivintage.estimates import InvalidEstimates, get_comparison, load_csvs, validate


def test_reproducible_demo(tmp_path):
    one = create_demo(tmp_path / "one.csv")
    two = create_demo(tmp_path / "two.csv")
    assert one.read_bytes() == two.read_bytes()


def test_valid_invariants(tmp_path):
    df = load_csvs([create_demo(tmp_path / "data.csv")])
    assert len(df) > 100
    assert (df.lb_95 <= df.lb_50).all()
    assert (df.lb_50 <= df.y).all()
    assert (df.y <= df.ub_50).all()
    assert (df.ub_50 <= df.ub_95).all()


def test_reject_bad_interval(tmp_path):
    df = load_csvs([create_demo(tmp_path / "data.csv")])
    df.loc[0, "lb_95"] = df.loc[0, "ub_95"] + 1
    with pytest.raises(InvalidEstimates):
        validate(df)


def test_vintage_comparison(tmp_path):
    df = load_csvs([create_demo(tmp_path / "data.csv")])
    c = get_comparison(df, "VIC", "Influenza total", "2025-07-17", "2025-08-07")
    assert c["stats"]["overlapping_days"] > 0
    assert c["stats"]["mean_abs_revision"] >= 0
    assert c["revisions"][0]["delta"] == round(c["second"][0]["y"] - c["first"][0]["y"], 2)


def test_http_api(monkeypatch, tmp_path):
    p = create_demo(tmp_path / "source.csv")
    monkeypatch.setenv("EPIVINTAGE_FILES", str(p))
    table.cache_clear()
    with TestClient(app) as client:
        resp = client.get("/api/options")
        assert resp.status_code == 200
        assert "VIC" in resp.json()["locations"]
        response = client.get("/api/compare", params={"location":"VIC", "pathogen":"RSV", "first":"2025-07-17", "second":"2025-08-07"})
        assert response.status_code == 200
        assert response.json()["stats"]["overlapping_days"] > 0
        assert client.get("/").status_code == 200
    table.cache_clear()
