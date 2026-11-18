"""Reproduce both case studies with python -m railops."""
from pathlib import Path
import argparse
import csv
import html
import json

from .simulation import compare
from .chart import chart
from .timetable import DataError, headways, load


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def report(rows, checks, provenance):
    headings = ["Scenario", "Mean arrival delay s", "P95 arrival delay s", "Within 60 s %", "Scheduled journey s", "Paired change s"]
    body = ""
    for r in rows:
        vals = [r['name'], *[f"{r[k]:.1f}" for k in ('mean_terminal_delay_seconds', 'p95_terminal_delay_seconds', 'within_60_seconds_pct', 'scheduled_journey_seconds', 'paired_mean_delay_change_seconds')]]
        body += '<tr>' + ''.join(f'<td>{html.escape(str(v))}</td>' for v in vals) + '</tr>'
    flags = sum(r['below_threshold'] for r in checks)
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rail Operations Lab case study report</title><style>
body{font:17px/1.6 system-ui,sans-serif;color:#18283b;background:#f2f6f8;margin:auto;max-width:1100px;padding:36px}
h1{font-size:38px;line-height:1.15}h2{margin-top:2em}table{border-collapse:collapse;width:100%;background:white;font-size:15px}
th,td{padding:12px;border:1px solid #cbd4dd;text-align:left}th{background:#173c4c;color:white}small{color:#435464}
.note{padding:20px;background:#e0edf0;border-left:5px solid #287785}.scroll{overflow:auto}code{overflow-wrap:anywhere}svg{width:100%;height:auto}
</style><h1>Rail Operations Lab</h1><p>Timetable quality and corridor resilience • Independent learning portfolio • Eric Tran</p>
<p class="note">All inputs are invented. This educational model is not calibrated to Melbourne's network and cannot establish operational feasibility or safety.</p>
<h2>1. Validate before modelling</h2><p>The single-day timetable extract passes structural, reference and time-order checks. The SQL spacing screen finds ''' + str(flags) + ''' departures below an illustrative 240-second threshold. These are review flags, not proven infrastructure conflicts.</p>
<h2>2. Compare four operating scenarios</h2><p>''' + str(rows[0]['replications']) + ''' replications per scenario, seed ''' + str(rows[0]['seed']) + '''. The same random streams support paired comparisons. Delays are measured against each scenario's own scheduled terminal arrival.</p><div class="scroll"><table><thead><tr>''' + ''.join(f'<th>{h}</th>' for h in headings) + '''</tr></thead><tbody>''' + body + '''</tbody></table></div>
''' + chart(rows) + '''
<h2>What would I discuss with a planner?</h2><p>The three-minute scenario schedules trains every 180 seconds against an assumed 210-second combined block occupancy and clearance. It creates structural queueing in this toy model. First check resource assumptions and the timetable before increasing frequency.</p>
<p>Recovery time can improve arrival punctuality partly by allowing a longer journey. Lower dwell variability tests a different mechanism. Neither scenario establishes a real-world benefit without observed run and dwell distributions, passenger demand, and operator review.</p>
<h2>What the model omits</h2><p>Opposing movements, junctions, signals, braking curves, station capacity, rolling stock, crew, cancellations, passenger loading and finite upstream storage. Trains retain timetable order. No warm-up or steady-state claim: this is a finite cohort of 16 trains initially entering an empty corridor.</p>
<h2>Audit trail</h2><p>CSV metrics, event traces, parameter values and Monte Carlo standard errors accompany this report. Standard errors describe simulation sampling noise, not uncertainty about real operations.</p><details><summary>Input SHA-256 hashes</summary><pre>''' + html.escape(json.dumps(provenance, indent=2)) + '</pre></details></html>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent.parent
    parser.add_argument('--data', type=Path, default=root / 'data/example')
    parser.add_argument('--output', type=Path, default=root / 'reports')
    parser.add_argument('--replications', type=int, default=200)
    parser.add_argument('--seed', type=int, default=20261118)
    args = parser.parse_args()
    try:
        timetable = load(args.data)
        checks = headways(timetable, root / 'sql/headways.sql')
        results, traces = compare(args.replications, args.seed)
        args.output.mkdir(parents=True, exist_ok=True)
        write_csv(args.output / 'headways.csv', checks)
        write_csv(args.output / 'scenarios.csv', results)
        (args.output / 'results.json').write_text(json.dumps({'scenarios': results, 'example_traces': traces, 'source_sha256': timetable.provenance}, indent=2) + '\n')
        (args.output / 'report.html').write_text(report(results, checks, timetable.provenance), encoding='utf-8')
        (args.output / 'scenario_comparison.svg').write_text(chart(results), encoding='utf-8')
        print(f'Validated {len(timetable.trips)} trips / {len(timetable.times)} stop times; {sum(r["below_threshold"] for r in checks)} spacing flags.')
        for r in results:
            print(f'{r["name"]}: mean terminal delay {r["mean_terminal_delay_seconds"]:.1f}s; P95 {r["p95_terminal_delay_seconds"]:.0f}s')
        print(f'Report: {(args.output / "report.html").resolve()}')
    except (DataError, ValueError, OSError) as exc:
        parser.exit(2, f'Input/report error: {exc}\n')


if __name__ == '__main__':
    main()
