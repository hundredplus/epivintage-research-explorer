# Presenter walkthrough and learning exercises

This AI-assisted prototype is a starting point for learning. Present only the
parts you can explain and reproduce. Keep professional scheduling experience
separate from these new rail concepts.

## First 30 minutes

Run the tests, then `python -m railops`. Open the HTML report and the two CSVs.
Explain the input hashes, why terminal departures are excluded, and how the
three flagged records arise from one short gap at three stops.

Read `sql/headways.sql`. Describe `PARTITION BY`, `ORDER BY` and `LAG`. Calculate
the departures at A: 07:00, 07:04, 07:07, 07:12. The gaps are 4, 3 and 5 minutes.
Change one time and trace the resulting flag; do not overwrite the reference
fixture unless you intend to update its expected results.

## Next 45 minutes

Read the event recurrence in `method.md`. Calculate a two-train, one-segment
example: run 180, clearance 30, service interval 180, no disturbances. Entries
are 0 and 210; the second train has 30 seconds of terminal delay.

Explain why the model keeps train order, forbids early departures and requires
exclusive segment occupancy. Name two important omissions, such as signals and
junctions. Explain why extra recovery does not make trains physically faster.

## Excel exercise

Import `reports/headways.csv` using Data → From Text/CSV. Preserve trip/stop IDs
as text and times as integer seconds. Filter `below_threshold = 1`; expect three
records. Check that the first departure in each group has a blank spacing, not
zero. Use a pivot table by stop to count flags and a column chart to show gaps.

Import `reports/scenarios.csv`. Format delay fields to one decimal place. Build
a bar chart comparing mean delay and a separate table for planned journey time.
Calculate baseline mean minus each scenario mean and verify against the signed
paired change field. Explain the difference between a mean and a P95.

Use AI to draft a formula, then verify one row manually and inspect its input
range. Learn filtering, structured tables, SUMIFS, COUNTIFS, XLOOKUP and pivot
tables through these files before claiming them as existing skills.

## Useful interview answers

**What did the exercise teach you?** Data validity comes before simulation;
resource constraints can make a nominal timetable unrealistic; changing the
schedule changes the interpretation of punctuality.

**What would you validate next?** Ask which resource constraints matter, obtain
permitted observed data, compare simulated and observed distributions, and have
an experienced modeller review assumptions.

**What did AI do?** Helped construct code, tests and documentation. Be explicit
about which parts you have reviewed, modified and independently verified.

**What tools do you still need to learn?** The operator's specialist simulation
package and railway operating rules. This project does not establish expertise
in either. Python and SQL are transferable foundations.
