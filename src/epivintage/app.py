"""FastAPI backend for the independent EpiVintage demonstration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .estimates import InvalidEstimates, data_paths, get_comparison, get_options, load_csvs

app = FastAPI(title="EpiVintage Research Explorer", version="0.2.0")
HTML = Path(__file__).with_name("index.html")


@lru_cache(maxsize=1)
def table():
    return load_csvs(data_paths())


@app.get("/")
def home():
    return FileResponse(HTML)


@app.get("/api/options")
def options():
    try:
        return get_options(table())
    except (InvalidEstimates, OSError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/compare")
def compare(location: str, pathogen: str, first: str, second: str):
    try:
        return get_comparison(table(), location, pathogen, first, second)
    except (InvalidEstimates, OSError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
