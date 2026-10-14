"""Meaningful regression coverage with synthetic records, never real production data."""
import sqlite3
import unittest
from production import import_records
from production_dashboard import aggregate_machines, coverage_text, filter_records, summarize
from production_report import render_report
from production_trends import get_trend_data, render_trends
from test_production import record


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.rows = [record(planned_rolls=10,input_rolls=5),
                     record(shift='Night',planned_rolls=30,input_rolls=30),
                     record(machine_id='TEST2',product='OTHER',planned_rolls=10,input_rolls=0)]

    def test_weighted_ratio_and_unique_devices(self):
        s=summarize(self.rows)
        self.assertEqual(s['attainment'],'70.0%')
        self.assertEqual(s['qualification'],'80.0%')
        self.assertEqual(s['machine_count'],2)
        self.assertEqual(aggregate_machines(self.rows)[0]['planned_rolls'],40)

    def test_filters_and_coverage(self):
        selected=filter_records(self.rows,'Night','TEST1')
        self.assertEqual(len(selected),1)
        self.assertEqual(summarize(selected)['attainment'],'100.0%')
        text=coverage_text(self.rows)
        self.assertIn('白班有记录 2 台',text)
        self.assertIn('夜班有记录 1 台',text)
        self.assertIn('两班均有记录 1 台',text)

    def test_zero_denominators_and_no_data(self):
        zero=record(planned_rolls=0,input_rolls=0,actual_output_m2=0,qualified_output_m2=0)
        for rows in ([zero],[]):
            s=summarize(rows)
            self.assertEqual(s['attainment'],'—')
            self.assertEqual(s['qualification'],'—')
        self.assertEqual(summarize([])['machine_count'],0)
        self.assertIn('暂无生产记录',render_report([],'2026-01-01'))

    def test_multiple_products_aggregate_but_details_preserve(self):
        rows=[record(product='A'),record(product='B')]
        self.assertEqual(len(aggregate_machines(rows)),1)
        self.assertEqual(aggregate_machines(rows)[0]['input_rolls'],10)
        report=render_report(rows,'2026-01-01')
        self.assertIn('<td>A</td>',report)
        self.assertIn('<td>B</td>',report)
        self.assertNotIn('口径与来源',report)

    def test_trend_gaps_plan_and_unconfirmed_code_change(self):
        with sqlite3.connect(':memory:') as db:
            import_records([record(),record(production_date='2026-01-03',product='OTHER')],db)
            for days in (7,30):
                rows=get_trend_data(db,'2026-01-03',days)
                self.assertTrue(all(r['changeover'] is None for r in rows))
                report=render_trends(rows,'2026-01-03',days,'投入卷数（实际 / 计划）')
                self.assertNotIn('class="planned-line"',report)
                self.assertIn('仅有一个班次记录',report)
                self.assertIn('计划投入（标准线）',report)
            single=render_trends(get_trend_data(db,'2026-01-01',7),'2026-01-01',7)
            self.assertIn('只有 1 个日期',single)

    def test_confirmed_events_obey_shift(self):
        with sqlite3.connect(':memory:') as db:
            import_records([record(),record(shift='Night')],db)
            db.execute('CREATE TABLE changeover_events (production_date, machine_id, shift, from_product, to_product)')
            db.execute("INSERT INTO changeover_events VALUES ('2026-01-01','TEST1','Day','A','B')")
            self.assertIsNotNone(get_trend_data(db,'2026-01-01',7,'Day')[0]['changeover'])
            self.assertIsNone(get_trend_data(db,'2026-01-01',7,'Night')[0]['changeover'])


if __name__=='__main__':
    unittest.main()
