"""Download permitted *public* ACEFA situational assessment estimate CSVs.

Explicitly downloads selected vintage files; never fetches confidential data.
The files remain local and are not included in the EpiVintage source package.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

from .estimates import InvalidEstimates, validate

BASE_URL = ("https://raw.githubusercontent.com/acefa-hubs/SitAssessmentPaper2025/"
            "main/smoothed_estimates/modelled_estimates_cases{date}.csv")
MAX_BYTES = 30 * 1024 * 1024


def download_vintage(vintage: str, dest: Path) -> dict:
    """Download, validate, checksum and atomically publish one public CSV."""
    try:
        day = date.fromisoformat(vintage)
    except ValueError as exc:
        raise InvalidEstimates("Vintage must be an ISO date (YYYY-MM-DD)") from exc
    if day.isoformat() != vintage:
        raise InvalidEstimates("Vintage must be an ISO date (YYYY-MM-DD)")

    url = BASE_URL.format(date=vintage)
    dest.mkdir(parents=True, exist_ok=True)
    filename = f"modelled_estimates_cases{vintage}.csv"
    target = dest / filename
    digest = hashlib.sha256()
    total = 0
    tmp = None
    try:
        req = Request(url, headers={"User-Agent": "EpiVintage-public-research-demo/0.2"})
        with urlopen(req, timeout=40) as stream, NamedTemporaryFile(
            mode="wb", dir=dest, prefix=".epivintage-", suffix=".csv", delete=False
        ) as out:
            tmp = Path(out.name)
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise InvalidEstimates(f"Remote file exceeds {MAX_BYTES // (1024 * 1024)} MiB limit")
                digest.update(chunk)
                out.write(chunk)
        frame = validate(pd.read_csv(tmp))
        observed = set(frame.origin.dt.strftime("%Y-%m-%d"))
        if observed != {vintage}:
            raise InvalidEstimates(f"Source {filename} has unexpected origin dates: {sorted(observed)}")
        tmp.replace(target)
    except (HTTPError, URLError) as exc:
        raise InvalidEstimates(f"Could not download the public ACEFA file {url}: {exc}") from exc
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise InvalidEstimates(f"Invalid CSV downloaded from {url}: {exc}") from exc
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return {
        "vintage": vintage,
        "filename": filename,
        "source": url,
        "sha256": digest.hexdigest(),
        "rows": len(frame),
        "bytes": total,
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Download selected public ACEFA estimate vintages")
    parser.add_argument("vintages", nargs="+", help="Reporting dates, such as 2025-07-17 2025-08-07")
    parser.add_argument("--output", type=Path, default=Path("downloads"))
    args = parser.parse_args()
    manifest = [download_vintage(vintage, args.output) for vintage in args.vintages]
    (args.output / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    paths = [str((args.output / record["filename"]).resolve()) for record in manifest]
    print(f"Downloaded {len(paths)} ACEFA public files; manifest saved in {args.output}")
    print("To run locally on macOS/Linux:")
    print("  export EPIVINTAGE_FILES=" + shlex.quote(os.pathsep.join(paths)))
    print("  uvicorn epivintage.app:app --reload")


if __name__ == "__main__":
    main()
