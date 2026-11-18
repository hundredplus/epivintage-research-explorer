"""FIFO resource-constrained event model of an invented one-way corridor."""
from dataclasses import asdict, dataclass, replace
import math
import random
import statistics


@dataclass(frozen=True)
class Scenario:
    name: str
    trains: int = 16
    segments: int = 3
    interval: int = 240
    run: int = 180
    clearance: int = 30
    dwell: int = 45
    recovery: int = 0
    initial_delay_max: int = 60
    extra_dwell_max: int = 90

    def validate(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a nonempty string")
        for key, val in asdict(self).items():
            if key == "name":
                continue
            if type(val) is not int or val < 0:
                raise ValueError(f"{key} must be a non-negative integer")
        if min(self.trains, self.segments, self.interval, self.run) <= 0:
            raise ValueError("trains, segments, interval and run must be positive")


@dataclass(frozen=True)
class Event:
    train: int
    segment: int
    planned_entry: int
    entry: int
    exit: int
    queue_seconds: int


def simulate(s: Scenario, seed: int = 0) -> tuple[list[Event], list[int]]:
    s.validate()
    rng = random.Random(seed)
    # Draw disturbances before scheduling so paired scenarios use identical inputs.
    initial = [int(rng.random() * (s.initial_delay_max + 1)) for _ in range(s.trains)]
    extra = [[int(rng.random() * (s.extra_dwell_max + 1)) for _ in range(s.segments - 1)]
             for _ in range(s.trains)]
    free = [0] * s.segments
    events, terminal_delays = [], []
    for train in range(s.trains):
        ready = train * s.interval + initial[train]
        for seg in range(s.segments):
            planned = train * s.interval + seg * (s.run + s.dwell + s.recovery)
            entry = max(planned, ready, free[seg])
            events.append(Event(train, seg, planned, entry, entry + s.run,
                                max(0, free[seg] - max(planned, ready))))
            free[seg] = entry + s.run + s.clearance
            if seg < s.segments - 1:
                ready = entry + s.run + s.dwell + extra[train][seg]
        terminal_delays.append(events[-1].exit - (planned + s.run))
    return events, terminal_delays


def percentile(values: list[int], q: float) -> float:
    """Nearest-rank percentile, explicitly defined for a finite sample."""
    if not values or not 0 < q <= 1:
        raise ValueError("Need values and 0 < q <= 1")
    return float(sorted(values)[math.ceil(len(values) * q) - 1])


def experiment(s: Scenario, repetitions: int = 200, seed: int = 20261118) -> tuple[dict, list[float], list[Event]]:
    if type(repetitions) is not int or repetitions < 2:
        raise ValueError("At least two replications required")
    means, delays, queues = [], [], []
    example = []
    for rep in range(repetitions):
        events, d = simulate(s, seed + rep)
        means.append(statistics.mean(d))
        delays.extend(d)
        queues.append(sum(e.queue_seconds for e in events) / s.trains)
        if rep == 0:
            example = events
    se = statistics.stdev(means) / math.sqrt(repetitions)
    result = {**asdict(s), "replications": repetitions, "seed": seed,
              "mean_terminal_delay_seconds": statistics.mean(means),
              "mean_delay_monte_carlo_se_seconds": se,
              "p95_terminal_delay_seconds": percentile(delays, .95),
              "within_60_seconds_pct": 100 * sum(d <= 60 for d in delays) / len(delays),
              "mean_queue_seconds_per_train": statistics.mean(queues),
              "scheduled_journey_seconds": s.segments * s.run + (s.segments - 1) * (s.dwell + s.recovery),
              "block_occupancy_seconds": s.run + s.clearance,
              "nominal_trains_per_hour": 3600 / s.interval}
    return result, means, example


def compare(repetitions: int = 200, seed: int = 20261118):
    base = Scenario("Base four minute service")
    scenarios = [base, replace(base, name="Three minute service", interval=180),
                 replace(base, name="Thirty second timetable recovery", recovery=30),
                 replace(base, name="Lower dwell variability", extra_dwell_max=30)]
    results, all_means, traces = [], [], {}
    for s in scenarios:
        result, means, events = experiment(s, repetitions, seed)
        results.append(result)
        all_means.append(means)
        traces[s.name] = [asdict(e) for e in events]
    for result, means in zip(results, all_means):
        differences = [b - a for a, b in zip(all_means[0], means)]
        result["paired_mean_delay_change_seconds"] = statistics.mean(differences)
        result["paired_change_monte_carlo_se_seconds"] = statistics.stdev(differences) / math.sqrt(repetitions)
    return results, traces
