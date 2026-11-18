from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from railops.simulation import Scenario, compare, experiment, simulate
from railops.timetable import DataError, headways, load, seconds

ROOT = Path(__file__).resolve().parent.parent


class DataTests(unittest.TestCase):
    def test_after_midnight(self):
        self.assertEqual(seconds('25:10:00'), 90600)

    def test_bad_times(self):
        for value in ('12:60:00', '-1:00:00', '12:00', 'nan', ' 12:00:00'):
            with self.subTest(value=value), self.assertRaises(DataError):
                seconds(value)

    def test_sql_hand_calculated_spacings(self):
        table = load(ROOT / 'data/example')
        rows = headways(table, ROOT / 'sql/headways.sql')
        a = [r for r in rows if r['stop_id'] == 'A']
        self.assertEqual([r['headway_seconds'] for r in a], [None, 240, 180, 300])
        self.assertEqual(sum(r['below_threshold'] for r in rows), 3)
        self.assertEqual(len(rows), 12)  # terminal arrivals excluded
        self.assertEqual(set(table.provenance), {'stops.csv', 'trips.csv', 'stop_times.csv'})

    def mutate(self, before, after, filename='stop_times.csv'):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'input'
            shutil.copytree(ROOT / 'data/example', folder)
            p = folder / filename
            p.write_text(p.read_text().replace(before, after))
            with self.assertRaises(DataError):
                load(folder)

    def test_unknown_stop(self):
        self.mutate('T01,A,1', 'T01,Z,1')

    def test_duplicate_sequence(self):
        self.mutate('T01,B,2', 'T01,B,1')

    def test_time_backwards(self):
        self.mutate('07:03:00,07:03:45', '06:03:00,06:03:45')

    def test_negative_dwell(self):
        self.mutate('07:03:00,07:03:45', '07:03:00,07:02:45')

    def test_missing_header(self):
        self.mutate('stop_id,stop_name', 'wrong,stop_name', 'stops.csv')

    def test_duplicate_stop(self):
        self.mutate('B,Example Junction', 'A,Example Junction', 'stops.csv')

    def test_empty_field(self):
        self.mutate('T01,A,1', 'T01,,1')


class ModelTests(unittest.TestCase):
    def test_zero_disturbance_feasible_timetable(self):
        s = Scenario('Deterministic', initial_delay_max=0, extra_dwell_max=0)
        events, delays = simulate(s)
        self.assertEqual(delays, [0] * s.trains)
        self.assertTrue(all(e.queue_seconds == 0 for e in events))

    def test_hand_calculated_capacity_queue(self):
        s = Scenario('Two trains', trains=2, segments=1, interval=180,
                     initial_delay_max=0, extra_dwell_max=0)
        events, delays = simulate(s)
        self.assertEqual([e.entry for e in events], [0, 210])
        self.assertEqual(delays, [0, 30])

    def test_clearance_no_early_departure_and_continuity(self):
        s = Scenario('Stress', interval=150)
        events, _ = simulate(s, 91)
        for seg in range(s.segments):
            group = [e for e in events if e.segment == seg]
            for a, b in zip(group, group[1:]):
                self.assertGreaterEqual(b.entry, a.exit + s.clearance)
        for e in events:
            self.assertGreaterEqual(e.entry, e.planned_entry)
            self.assertEqual(e.exit - e.entry, s.run)
            if e.segment:
                previous = events[e.train * s.segments + e.segment - 1]
                self.assertGreaterEqual(e.entry, previous.exit + s.dwell)

    def test_repeatability(self):
        self.assertEqual(compare(5, 91), compare(5, 91))

    def test_lower_dwell_shared_draws_cannot_increase_arrival_times(self):
        base = Scenario('Base')
        for seed in range(10):
            a, _ = simulate(base, seed)
            b, _ = simulate(replace(base, extra_dwell_max=30), seed)
            self.assertTrue(all(y.exit <= x.exit for x, y in zip(a, b)))

    def test_recovery_can_increase_absolute_journey(self):
        # Extra schedule padding can delay absolute arrivals despite lower lateness.
        s = Scenario('Base', initial_delay_max=0, extra_dwell_max=0)
        a, _ = simulate(s)
        b, _ = simulate(replace(s, recovery=30))
        self.assertEqual(b[2].exit - a[2].exit, 60)

    def test_invalid_parameters(self):
        for changes in ({'interval': 0}, {'clearance': -1}, {'run': float('nan')}, {'trains': True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                simulate(replace(Scenario('Bad'), **changes))
        with self.assertRaises(ValueError):
            experiment(Scenario('Bad'), 1)

    def test_paired_baseline_is_zero(self):
        rows, _ = compare(5)
        self.assertEqual(rows[0]['paired_mean_delay_change_seconds'], 0)
        self.assertEqual(rows[0]['paired_change_monte_carlo_se_seconds'], 0)


if __name__ == '__main__':
    unittest.main()
