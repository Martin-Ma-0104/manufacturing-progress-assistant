"""Synthetic SQLite contracts for the production assistant's bounded data tools."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from ai_production_data import (
    METRICS, _readonly_connection, catalog, export_preview, normalize_scope,
    query_facts, read_snapshot,
)
from cloud_data import EVENT_SCHEMA
from production import FIELDS, import_records
from production_dashboard import aggregate_machines, summarize


def record(day='2026-01-01', machine='FX1', shift='Day', product='A', **changes):
    row = dict(production_date=day, machine_id=machine, shift=shift, product=product,
               planned_rolls=10, input_rolls=5, qualified_rolls=25,
               actual_output_m2=100.0, qualified_output_m2=80.0,
               reported_yield_pct=71.5, source_report_date=day, source_shift_label=shift,
               source_name='PRIVATE-image.png', notes='PRIVATE-source-note')
    row.update(changes)
    return row


class ProductionDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / 'synthetic.db'
        self.rows = [
            record(),
            record(product='B', planned_rolls=20, input_rolls=20,
                   actual_output_m2=200.0, qualified_output_m2=100.0),
            record(shift='Night', planned_rolls=5, input_rolls=10,
                   actual_output_m2=50.0, qualified_output_m2=40.0),
            record(machine='FX2', planned_rolls=5, input_rolls=0,
                   actual_output_m2=0.0, qualified_output_m2=0.0),
            record(day='2026-01-03', shift='Night', product='C'),
            record(day='2025-12-01', machine='OLD9'),
        ]
        self.events = [
            ('2026-01-01', 'Day', 'FX1', 'OLD', 'A', 'PRIVATE-confirm-note'),
            ('2026-01-01', 'Night', 'FX1', 'A', 'C', 'PRIVATE-confirm-note'),
            ('2026-01-02', 'Day', 'FX1', 'C', 'D', 'PRIVATE-unmatched-note'),
        ]
        with sqlite3.connect(self.db) as connection:
            import_records(self.rows, connection)
            connection.execute(EVENT_SCHEMA)
            connection.executemany('INSERT INTO changeover_events VALUES (?,?,?,?,?,?)', self.events)
            connection.execute('CREATE TABLE orders(secret TEXT)')
            connection.execute("INSERT INTO orders VALUES ('PRIVATE-order')")
        self.scope = normalize_scope('2026-01-01', '2026-01-03')

    def tearDown(self):
        self.tmp.cleanup()

    def query(self, view='overview', **changes):
        result = dict(view=view, start_date='2026-01-01', end_date='2026-01-03',
                      shift='All', machines=[], metrics=['qualified_output_m2', 'attainment', 'qualification'])
        result.update(changes)
        return result

    def test_scope_strict_types_iso_and_thirty_day_bound(self):
        self.assertEqual(normalize_scope('2026-01-01', '2026-01-30', machines=['FX10', 'FX2', 'FX2'])['machines'], ['FX2', 'FX10'])
        for args in [('2026-01-01', '2026-01-31'), ('2026-01-03', '2026-01-01'),
                     ('20260101', '2026-01-03'), (1, '2026-01-03')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                normalize_scope(*args)
        for changes in [dict(shift='All'), dict(shift=True), dict(machines='FX1'),
                        dict(machines=[1]), dict(machines=[''])]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_scope('2026-01-01', '2026-01-03', **changes)

    def test_snapshot_agrees_with_existing_dashboard_and_reads_only_numeric_rows(self):
        snapshot = read_snapshot(self.scope, self.db)
        expected = [row for row in self.rows if row['production_date'] >= '2026-01-01']
        self.assertEqual(snapshot['summary'], summarize(expected))
        self.assertEqual(snapshot['machines'], aggregate_machines(expected))
        # A simple percentage average would disagree with this weighted ratio.
        self.assertEqual(snapshot['summary']['qualification'], '66.7%')
        self.assertEqual(snapshot['summary']['attainment'], '80.0%')
        self.assertEqual(set(snapshot['rows'][0]), set(FIELDS) -
                         {'source_report_date', 'source_shift_label', 'source_name', 'notes'})
        self.assertNotIn('PRIVATE', json.dumps(snapshot))
        self.assertEqual(snapshot['available_machines'], ['FX1', 'FX2', 'OLD9'])
        json.dumps(snapshot, allow_nan=False)

    def test_catalog_without_production_tables_does_not_initialize_or_create_db(self):
        before = self.db.read_bytes()
        self.assertEqual(catalog(self.db)['dates'], ['2025-12-01', '2026-01-01', '2026-01-03'])
        self.assertEqual(self.db.read_bytes(), before)
        empty = Path(self.tmp.name) / 'empty.db'
        sqlite3.connect(empty).close()
        self.assertEqual(catalog(empty), {'dates': [], 'machines': []})
        self.assertEqual(read_snapshot(self.scope, empty)['rows'], [])
        missing = Path(self.tmp.name) / 'not-created.db'
        with self.assertRaises(ValueError):
            catalog(missing)
        self.assertFalse(missing.exists())

    def test_connection_enforces_read_only_and_no_application_mutation(self):
        before = self.db.read_bytes()
        with _readonly_connection(self.db) as connection:
            self.assertEqual(connection.execute('PRAGMA query_only').fetchone()[0], 1)
            for statement in ('DELETE FROM slitting_records', 'CREATE TABLE changed(value TEXT)',
                              'PRAGMA user_version = 77'):
                with self.subTest(statement=statement), self.assertRaises(sqlite3.OperationalError):
                    connection.execute(statement)
        read_snapshot(self.scope, self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_coverage_missing_dates_and_partial_shifts_never_create_zero_rows(self):
        snapshot = read_snapshot(self.scope, self.db)
        coverage = snapshot['coverage']
        self.assertEqual(coverage['missing_dates'], ['2026-01-02'])
        self.assertEqual([row['production_date'] for row in snapshot['daily']], ['2026-01-01', '2026-01-03'])
        partial = coverage['partial_machine_dates']
        self.assertIn(dict(production_date='2026-01-01', machine_id='FX2',
                           observed_shifts=['Day'], missing_shifts=['Night']), partial)
        self.assertEqual(coverage['day']['record_count'], 3)
        self.assertEqual(coverage['night']['record_count'], 2)
        self.assertIn('不代表全厂数据完整', coverage['message'])
        facts = query_facts(snapshot, self.query(view='daily'))
        self.assertIn('2026-01-02', facts['facts'][0]['text'])
        self.assertFalse(any('2026-01-02：实际' in fact['text'] for fact in facts['facts']))

    def test_tool_shrinks_dates_machines_and_shifts_with_multi_product_sums(self):
        snapshot = read_snapshot(self.scope, self.db)
        result = query_facts(snapshot, self.query(start_date='2026-01-01', end_date='2026-01-01',
                            shift='Day', machines=['FX1'], metrics=['input_rolls', 'attainment']))
        self.assertEqual(result['scope']['machines'], ['FX1'])
        texts = ' '.join(fact['text'] for fact in result['facts'])
        self.assertIn('实际投入 25 卷', texts)
        self.assertIn('83.3%', texts)
        self.assertIn('25.0 卷 ÷ 30.0 卷', texts)
        comparison = query_facts(snapshot, self.query(view='comparison', metrics=['qualified_output_m2']))
        self.assertTrue(any('FX2：合格产出 0.0 m²' in f['text'] for f in comparison['facts']))
        inherited = read_snapshot(normalize_scope('2026-01-01', '2026-01-03', 'Day', ['FX1']), self.db)
        self.assertEqual(query_facts(inherited, self.query(shift='Day'))['scope']['machines'], ['FX1'])

    def test_tool_rejects_unknown_and_out_of_ui_scope_queries(self):
        snapshot = read_snapshot(normalize_scope('2026-01-01', '2026-01-03', 'Day', ['FX1']), self.db)
        cases = [dict(start_date='2025-12-31'), dict(end_date='2026-01-04'),
                 dict(shift='All'), dict(shift='Night'), dict(machines=['FX2']),
                 dict(machines=['UNKNOWN']), dict(machines=None), dict(sql='DELETE FROM slitting_records'),
                 dict(metrics=['reported_yield_pct']), dict(metrics=[]), dict(metrics=['input_rolls'] * 2),
                 dict(metrics=list(METRICS[:4])), dict(view='execute')]
        for changes in cases:
            query = self.query(shift='Day', **{k: v for k, v in changes.items() if k != 'shift'})
            query.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                query_facts(snapshot, query)
        with self.assertRaises(ValueError):
            read_snapshot(dict(self.scope, machines=['UNKNOWN']), self.db)

    def test_historical_machine_and_no_records_do_not_become_zero_production(self):
        snapshot = read_snapshot(normalize_scope('2026-01-02', '2026-01-02', machines=['OLD9']), self.db)
        result = query_facts(snapshot, self.query(start_date='2026-01-02', end_date='2026-01-02', machines=['OLD9']))
        self.assertEqual(snapshot['rows'], [])
        self.assertEqual(snapshot['daily'], [])
        text = ' '.join(f['text'] for f in result['facts'])
        self.assertIn('暂无生产记录', text)
        self.assertNotIn('0.0 m²', text)
        mixed = read_snapshot(self.scope, self.db)
        compared = query_facts(mixed, self.query(view='comparison', machines=['FX1', 'OLD9']))
        self.assertTrue(any('OLD9：暂无记录' in f['text'] for f in compared['facts']))

    def test_zero_denominators_show_unavailable(self):
        with sqlite3.connect(self.db) as connection:
            import_records([record(day='2026-01-02', machine='FXZERO', planned_rolls=0,
                                   input_rolls=0, qualified_rolls=0, actual_output_m2=0.0,
                                   qualified_output_m2=0.0, reported_yield_pct=None)], connection)
        snapshot = read_snapshot(self.scope, self.db)
        result = query_facts(snapshot, self.query(machines=['FXZERO'], metrics=['attainment', 'qualification']))
        self.assertEqual(sum('不可用（分母为零）' in f['text'] for f in result['facts']), 2)

    def test_only_confirmed_events_with_exact_production_date_machine_shift(self):
        snapshot = read_snapshot(self.scope, self.db)
        self.assertEqual(len(snapshot['changeovers']), 2)
        result = query_facts(snapshot, self.query(view='changeovers', shift='Day'))
        text = ' '.join(f['text'] for f in result['facts'])
        self.assertIn('OLD → A', text)
        self.assertNotIn('A → C', text)
        self.assertNotIn('C → D', text)
        self.assertNotIn('confirmation_note', json.dumps(result))
        # Multiple source product codes never add inferred changeovers.
        self.assertEqual(sum('已确认换产，' in f['text'] for f in result['facts']), 1)

    def test_transport_preview_reconstructs_field_whitelist(self):
        snapshot = read_snapshot(self.scope, self.db)
        snapshot['private_path'] = '/PRIVATE/database.db'
        snapshot['summary']['source_name'] = 'PRIVATE-source'
        snapshot['coverage']['notes'] = 'PRIVATE-note'
        snapshot['changeovers'][0]['confirmation_note'] = 'PRIVATE-confirm'
        preview = export_preview(snapshot)
        encoded = json.dumps(preview, ensure_ascii=False, allow_nan=False)
        self.assertNotIn('PRIVATE', encoded)
        self.assertNotIn('reported_yield_pct', encoded)
        self.assertNotIn('rows', preview)
        self.assertNotIn('available_machines', preview)
        self.assertEqual(set(preview), {'scope', 'summary', 'machines', 'daily', 'coverage', 'changeovers', 'diagnostics'})
        self.assertEqual(preview['summary']['qualified_output_m2'], snapshot['summary']['qualified_output_m2'])
        self.assertNotIn('source_name', json.dumps(query_facts(snapshot, self.query())))

    def test_snapshot_version_and_fact_ids_are_stable_and_change_with_data(self):
        snapshot = read_snapshot(self.scope, self.db)
        self.assertEqual(snapshot, read_snapshot(self.scope, self.db))
        self.assertEqual(query_facts(snapshot, self.query()), query_facts(copy.deepcopy(snapshot), self.query()))
        with sqlite3.connect(self.db) as connection:
            connection.execute('UPDATE slitting_records SET input_rolls=input_rolls+1 WHERE production_date=? AND machine_id=?', ('2026-01-01', 'FX1'))
        changed = read_snapshot(self.scope, self.db)
        self.assertNotEqual(snapshot['version'], changed['version'])
        original_ids = {f['id'] for f in query_facts(snapshot, self.query())['facts']}
        changed_ids = {f['id'] for f in query_facts(changed, self.query())['facts']}
        self.assertNotEqual(original_ids, changed_ids)


if __name__ == '__main__':
    unittest.main()
