"""Validate a deliberately small GTFS-inspired single-service-day CSV extract."""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import re
import sqlite3


class DataError(ValueError):
    """An input cannot be used without correcting its source."""


@dataclass(frozen=True)
class StopTime:
    trip_id: str
    stop_id: str
    sequence: int
    arrival: int
    departure: int


@dataclass(frozen=True)
class Timetable:
    stops: dict[str, str]
    trips: dict[str, tuple[str, str]]
    times: tuple[StopTime, ...]
    provenance: dict[str, str]


def seconds(value: str) -> int:
    """GTFS service-day hours may exceed 23 (e.g. 25:10:00)."""
    if not re.fullmatch(r"[0-9]{2,}:[0-5][0-9]:[0-5][0-9]", value):
        raise DataError(f"Invalid time {value!r}; expected HH:MM:SS")
    h, m, s = map(int, value.split(":"))
    return h * 3600 + m * 60 + s


def _rows(folder: Path, name: str, required: set[str]):
    try:
        with (folder / name).open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not required <= set(reader.fieldnames or []):
                raise DataError(f"{name}: missing columns {sorted(required - set(reader.fieldnames or []))}")
            rows = list(reader)
    except OSError as exc:
        raise DataError(f"Cannot read {name}: {exc}") from exc
    if not rows:
        raise DataError(f"{name}: empty file")
    for i, row in enumerate(rows, 2):
        if None in row or any(row.get(k) is None or not row[k].strip() for k in required):
            raise DataError(f"{name} row {i}: blank field or malformed row")
    return rows


def load(folder: Path) -> Timetable:
    stops, trips, times, seen = {}, {}, [], set()
    for row in _rows(folder, "stops.csv", {"stop_id", "stop_name"}):
        if row["stop_id"] in stops:
            raise DataError(f"Duplicate stop {row['stop_id']}")
        stops[row["stop_id"]] = row["stop_name"]
    for row in _rows(folder, "trips.csv", {"trip_id", "route_id", "direction_id"}):
        if row["trip_id"] in trips or row["direction_id"] not in {"0", "1"}:
            raise DataError(f"Duplicate trip or invalid direction: {row['trip_id']}")
        trips[row["trip_id"]] = (row["route_id"], row["direction_id"])
    for row in _rows(folder, "stop_times.csv", {"trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"}):
        if row["trip_id"] not in trips or row["stop_id"] not in stops:
            raise DataError(f"Unknown trip/stop: {row['trip_id']}/{row['stop_id']}")
        if not re.fullmatch(r"[0-9]+", row["stop_sequence"]):
            raise DataError("stop_sequence must be a non-negative integer")
        seq = int(row["stop_sequence"])
        key = (row["trip_id"], seq)
        if key in seen:
            raise DataError(f"Duplicate trip/sequence: {key}")
        seen.add(key)
        a, d = seconds(row["arrival_time"]), seconds(row["departure_time"])
        if d < a:
            raise DataError(f"Departure before arrival: {key}")
        times.append(StopTime(row["trip_id"], row["stop_id"], seq, a, d))
    for trip in trips:
        ordered = sorted((t for t in times if t.trip_id == trip), key=lambda t: t.sequence)
        if len(ordered) < 2:
            raise DataError(f"Trip {trip} needs at least two timed stops")
        if any(b.arrival < a.departure for a, b in zip(ordered, ordered[1:])):
            raise DataError(f"Time goes backwards in trip {trip}")
    provenance = {n: hashlib.sha256((folder / n).read_bytes()).hexdigest()
                  for n in ("stops.csv", "trips.csv", "stop_times.csv")}
    return Timetable(stops, trips, tuple(times), provenance)


def headways(table: Timetable, sql: Path, minimum_seconds: int = 240) -> list[dict]:
    if type(minimum_seconds) is not int or minimum_seconds <= 0:
        raise DataError("minimum_seconds must be a positive integer")
    with sqlite3.connect(":memory:") as db:
        db.row_factory = sqlite3.Row
        db.execute("CREATE TABLE departures (trip_id TEXT, stop_id TEXT, route_id TEXT, direction_id TEXT, departure_seconds INTEGER)")
        # Exclude each trip's terminal: arrival is not a departure service there.
        last = {trip: max(t.sequence for t in table.times if t.trip_id == trip) for trip in table.trips}
        db.executemany("INSERT INTO departures VALUES (?, ?, ?, ?, ?)",
                       [(t.trip_id, t.stop_id, *table.trips[t.trip_id], t.departure)
                        for t in table.times if t.sequence != last[t.trip_id]])
        return [dict(row) for row in db.execute(sql.read_text(), {"minimum_seconds": minimum_seconds})]
