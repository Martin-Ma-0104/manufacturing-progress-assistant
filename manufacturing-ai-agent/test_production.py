"""Standard-library tests using synthetic data and an isolated database."""
import sqlite3
import unittest
from production import import_records, get_records
from production_report import render_report, percent


def record(**changes):
    result = dict(production_date='2026-01-01', shift='Day', machine_id='TEST1', product='TEST',
                  planned_rolls=10, input_rolls=5, qualified_rolls=20, actual_output_m2=100.0,
                  qualified_output_m2=80.0, reported_yield_pct=None,
                  source_report_date='2026-01-01', source_shift_label='Day',
                  source_name='synthetic', notes='Synthetic test record')
    result.update(changes)
    return result


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(':memory:')

    def tearDown(self):
        self.connection.close()

    def test_idempotence_and_shift_separation(self):
        rows = [record(), record(shift='Night', source_report_date='2026-01-02')]
        self.assertEqual(import_records(rows, self.connection), 2)
        self.assertEqual(import_records(rows, self.connection), 0)
        stored = get_records(self.connection, '2026-01-01')
        self.assertEqual(stored, rows)

    def test_conflict_rolls_back_entire_batch(self):
        import_records([record()], self.connection)
        with self.assertRaises(ValueError):
            import_records([record(machine_id='TEST2'), record(input_rolls=6)], self.connection)
        self.assertEqual(get_records(self.connection, '2026-01-01'), [record()])

    def test_invalid_data(self):
        for changes in [dict(planned_rolls=-1), dict(input_rolls=1.2), dict(shift='Other'),
                        dict(actual_output_m2=float('nan')), dict(qualified_output_m2=101),
                        dict(reported_yield_pct=101), dict(production_date='2026-02-30')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                import_records([record(**changes)], self.connection)

    def test_report_and_zero_denominators(self):
        self.assertEqual(percent(0, 0), '—')
        self.assertEqual(percent(5, 10), '50.0%')
        report = render_report([record(product='<script>')], '2026-01-01')
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('<script>', report)
        self.assertIn('50.0%', report)
        self.assertIn('80.0%', report)
        self.assertEqual(report.count('<svg '), 2)


if __name__ == '__main__':
    unittest.main()
