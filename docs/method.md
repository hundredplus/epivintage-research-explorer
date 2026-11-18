# Model method and assumptions

## Question and scope

How do a shorter service interval, timetable recovery and lower dwell variability
affect lateness for a finite group of trains on an invented corridor? This model
tests programming, accounting of constraints and interpretation. It is not a
microscopic railway simulator, timetable optimiser or Melbourne network model.

## Event recurrence

For train `i` and segment `j`, in seconds relative to the start of the experiment:

```
planned_entry(i,j) = i * interval + j * (run + dwell + recovery)
ready(i,0) = i * interval + origin_delay(i)
ready(i,j) = exit(i,j-1) + dwell + extra_dwell(i,j-1)  # j > 0
entry(i,j) = max(planned_entry(i,j), ready(i,j), segment_free(j))
exit(i,j) = entry(i,j) + run
segment_free(j) = exit(i,j) + clearance
terminal_delay(i) = exit(i,last) - (planned_entry(i,last) + run)
```

The queue metric counts only waiting imposed by segment unavailability after
the train is otherwise ready and its scheduled departure time has passed. It
excludes waiting for the schedule and origin/dwell disturbances themselves.
There are unlimited waiting spaces between segments; upstream trains are never
blocked by a full downstream platform. This is a strong simplification.

## Inputs

All values are assumed for teaching: 16 trains, 3 segments, 180 seconds running
per segment, 30 seconds resource clearance, 45 seconds minimum intermediate
dwell. Origin delay is discrete uniform 0–60 seconds. Extra dwell at each of two
intermediate stops is discrete uniform 0–90 seconds in the baseline. No
additional dwell is applied after the terminal arrival.

Recovery is schedule padding; it is not a physical reduction in running or dwell
time. Adding 30 seconds at each intermediate stop lengthens the planned journey
by 60 seconds. The punctuality denominator includes all 16 trains in every run;
the model has no cancellations or observation-window truncation.

The three-minute scenario is deliberately overloaded relative to the assumed
210-second per-segment occupancy. It illustrates a failed assumption for review,
not a viable operating proposal. `3600 / interval` is a nominal scheduled
frequency, not a measured throughput or rail network capacity.

## Replications and paired comparisons

Each replication starts empty and uses a fresh seeded `random.Random` instance.
All origin and dwell draws are made before event scheduling. Corresponding
scenarios use the same uniform variates mapped to each scenario's discrete
range; lower variability therefore never increases an individual dwell draw.

For each run, calculate mean terminal delay. Report the mean over 200 run means
and Monte Carlo standard error `stdev(run_means) / sqrt(200)`. A paired change
is scenario run mean minus baseline run mean for the same seed, with its own
standard error. These errors quantify random simulation noise under the assumed
model. They exclude model misspecification, parameter uncertainty and real-world
measurement error. No causal inference about actual operations is justified.

The P95 is the nearest-rank percentile of all simulated terminal delays pooled
across runs. It is neither a confidence bound nor a percentile of run averages.

## Timetable quality example

The separate extract assumes all trips run on the same service day. A route and
direction partition avoids comparing unrelated service groups. Shared-track
resources across routes, overtaking patterns, different stopping patterns and
station platform assignments are unavailable. A minimum spacing screen cannot
resolve them. Actual train operations cannot be inferred from scheduled times.

The parser rejects invalid inputs rather than silently coercing them, checks
each trip in stop-sequence order, and preserves source hashes. Sequence values
need not be consecutive. Empty times and on-demand services are not supported
by this deliberately restricted schema.

## Next steps before practical use

Obtain permitted timetables, topology and observed run/dwell records; expand
service calendars and establish consistent service-day/time-zone rules. Agree
resource definitions and performance metrics with an operations specialist.
Calibrate distributions, model correlations and held-out disruptions; compare
against independently observed performance. Add resource contention at
junctions and finite station capacity only with tested domain assumptions.
Record versions, uncertainties and review decisions for every proposed use.
