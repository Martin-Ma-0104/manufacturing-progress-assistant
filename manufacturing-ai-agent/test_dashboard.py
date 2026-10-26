"""Meaningful regression coverage with synthetic records, never real production data."""
import sqlite3
import unittest
from copy import deepcopy
import re
from xml.etree import ElementTree
from production import import_records
from production_dashboard import aggregate_machines, coverage_text, filter_records, summarize
from production_report import render_report
from production_trends import METRICS, get_trend_data, render_trends
from test_production import record


CONFIRMED_EVENT = '已确认换产（夜班）：SPEC-A → SPEC-B'


def trend_points():
    """Three observations: a missing Jan 2, then an explicitly recorded zero."""
    return [dict(machine_id='TEST1', production_date=f'2026-01-0{day}',
                 input_rolls=value, planned_rolls=10, qualified_rolls=value*10,
                 actual_output_m2=value*100, qualified_output_m2=value*80,
                 shift_count=1, changeover=CONFIRMED_EVENT if day==3 else None)
            for day, value in ((1,5),(3,0),(4,7))]


def svg_series(report):
    """Read chart geometry without counting table rows or calendar labels as points."""
    chart=ElementTree.fromstring(re.search(r'<svg\b.*?</svg>',report,re.S).group())
    points=[(float(c.attrib['cx']),float(c.attrib['cy'])) for c in chart.findall('circle')
            if c.attrib.get('r')=='5']
    actual=[((float(line.attrib['x1']),float(line.attrib['y1'])),
             (float(line.attrib['x2']),float(line.attrib['y2'])))
            for line in chart.findall('line') if line.attrib.get('stroke')=='#2563a6']
    plan_points=[(float(c.attrib['cx']),float(c.attrib['cy'])) for c in chart.findall('circle')
                 if c.attrib.get('r')=='4']
    planned=[((float(line.attrib['x1']),float(line.attrib['y1'])),
              (float(line.attrib['x2']),float(line.attrib['y2'])))
             for line in chart.findall('line') if line.attrib.get('class')=='planned-line']
    return chart,points,actual,plan_points,planned


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
                self.assertIn('class="planned-line"',report)
                self.assertIn('仅有一个班次记录',report)
                self.assertIn('计划投入（标准线）',report)
            single=render_trends(get_trend_data(db,'2026-01-01',7),'2026-01-01',7)
            self.assertIn('只有 1 个日期',single)

    def test_confirmed_events_obey_date_machine_and_shift(self):
        with sqlite3.connect(':memory:') as db:
            import_records([record(),record(shift='Night'),record(machine_id='TEST2'),
                            record(production_date='2026-01-03')],db)
            db.execute('CREATE TABLE changeover_events (production_date, machine_id, shift, from_product, to_product)')
            db.execute("INSERT INTO changeover_events VALUES ('2026-01-01','TEST1','Day','A','B')")
            db.execute("INSERT INTO changeover_events VALUES ('2026-01-03','TEST1','Day','B','C')")
            day=get_trend_data(db,'2026-01-01',7,'Day')
            night=get_trend_data(db,'2026-01-01',7,'Night')
            self.assertIsNotNone(day[0]['changeover'])
            self.assertIsNone(night[0]['changeover'])
            self.assertEqual({r['production_date'] for r in day},{'2026-01-01'})
            for visible in (False,True):
                selected=render_trends(day,'2026-01-01',7,machine='TEST1',show_changeovers=visible)
                self.assertIn('stroke="#7c3aed"',selected)
                self.assertNotIn('B → C',selected)  # The later event is outside the query window.
                for rows,shift,machine in ((day,'Day','TEST2'),(night,'Night','TEST1')):
                    report=render_trends(rows,'2026-01-01',7,shift=shift,machine=machine,
                                         show_changeovers=visible)
                    self.assertNotIn('stroke="#7c3aed"',report)
                    self.assertNotIn('class="changes"',report)

    def test_all_shifts_connect_observations_without_filling_dates(self):
        rows=trend_points()
        before=deepcopy(rows)
        for days in (7,30):
            for metric in METRICS:
                for shift in (None,'Day','Night'):
                    with self.subTest(days=days,metric=metric,shift=shift):
                        report=render_trends(rows,'2026-01-07',days,metric,shift,'TEST1')
                        chart,points,actual,plan_points,planned=svg_series(report)
                        self.assertEqual(len(points),3)
                        self.assertEqual(points[1][1],230)  # The recorded zero is a real point.
                        expected=list(zip(points,points[1:]))
                        self.assertEqual(actual,expected)
                        self.assertNotIn('<td>2026-01-02</td>',report)
                        self.assertNotIn('<td>2026-01-05</td>',report)
                        if metric=='投入卷数（实际 / 计划）':
                            self.assertEqual(len(plan_points),3)
                            expected_plan=list(zip(plan_points,plan_points[1:]))
                            self.assertEqual(planned,expected_plan)
                            self.assertTrue(all(line.attrib.get('stroke-dasharray') for line in chart.findall('line')
                                                if line.attrib.get('class')=='planned-line'))
                        else:
                            self.assertEqual(planned,[])
        self.assertEqual(rows,before)

    def test_input_labels_follow_their_own_series_above_below_equal_and_zero(self):
        cases = ((19,16),(8,16),(16,16),(17,16),(15,16),(0,16),(19,0),(0,0))
        for days in (7,30):
            for shift in (None,'Day','Night'):
                for actual_value,planned_value in cases:
                    with self.subTest(days=days,shift=shift,actual=actual_value,planned=planned_value):
                        row=dict(trend_points()[0],production_date='2026-01-07',
                                 input_rolls=actual_value,planned_rolls=planned_value)
                        report=render_trends([row],'2026-01-07',days,'投入卷数（实际 / 计划）',shift,'TEST1')
                        chart,points,lines,plan_points,plan_lines=svg_series(report)
                        labels={e.attrib.get('class'):e for e in chart.findall('text')}
                        actual=labels['point-label actual-label']
                        planned=labels['point-label plan-label']
                        self.assertEqual(actual.text,f'实际 {actual_value}')
                        self.assertEqual(planned.text,f'计划 {planned_value}')
                        self.assertEqual(actual.attrib['style'],'fill:#2563a6')
                        self.assertEqual(planned.attrib['style'],'fill:#64748b')
                        self.assertEqual(float(actual.attrib['x']),points[0][0])
                        self.assertEqual(float(planned.attrib['x']),plan_points[0][0])
                        actual_y=float(actual.attrib['y'])
                        planned_y=float(planned.attrib['y'])
                        if actual_value>planned_value:
                            self.assertLess(actual_y,points[0][1])
                            self.assertGreater(planned_y,plan_points[0][1])
                        else:
                            self.assertGreater(actual_y,points[0][1])
                            self.assertLess(planned_y,plan_points[0][1])
                        self.assertGreaterEqual(abs(actual_y-planned_y),38)
                        self.assertEqual(actual.attrib['text-anchor'],'end')
                        self.assertEqual(planned.attrib['text-anchor'],'end')
                        self.assertIn(f'2026-01-07 · 实际投入 {actual_value:,.1f} 卷',report)
                        self.assertIn(f'2026-01-07 · 计划投入 {planned_value:,.0f} 卷',report)
                        self.assertEqual(lines,[])
                        self.assertEqual(plan_lines,[])

    def test_changeover_graphics_persist_and_only_details_are_optional(self):
        rows=trend_points()
        before=deepcopy(rows)
        for days in (7,30):
            default=render_trends(rows,'2026-01-07',days,shift='Night')
            hidden=render_trends(rows,'2026-01-07',days,shift='Night',show_changeovers=False)
            shown=render_trends(rows,'2026-01-07',days,shift='Night',show_changeovers=True)
            self.assertEqual(default,hidden)
            self.assertNotIn('class="changes"',hidden)
            self.assertIn(CONFIRMED_EVENT,hidden)  # Details remain available in SVG tooltips.
            self.assertIn('class="changes"',shown)
            self.assertIn(f'<li><b>2026-01-03</b> · {CONFIRMED_EVENT}</li>',shown)
            charts=[svg_series(report)[0] for report in (default,hidden,shown)]
            self.assertEqual(ElementTree.tostring(charts[0]),ElementTree.tostring(charts[1]))
            self.assertEqual(ElementTree.tostring(charts[0]),ElementTree.tostring(charts[2]))
            for chart in charts:
                markers=[line for line in chart.findall('line') if line.attrib.get('stroke')=='#7c3aed']
                rings=[c for c in chart.findall('circle') if c.attrib.get('stroke')=='#7c3aed']
                self.assertEqual(len(markers),1)
                self.assertTrue(markers[0].attrib.get('stroke-dasharray'))
                self.assertEqual([(c.attrib['r'],c.attrib['fill']) for c in rings],[('9','none')])
                self.assertEqual([label.text for label in chart.findall('text')
                                  if label.text=='换产'],['换产'])
            no_events=[dict(row,changeover=None) for row in rows]
            for visible in (False,True):
                report=render_trends(no_events,'2026-01-07',days,shift='Night',show_changeovers=visible)
                self.assertNotIn('stroke="#7c3aed"',report)
                self.assertNotIn('class="changes"',report)
            for metric in METRICS:
                with self.subTest(days=days,metric=metric):
                    single=render_trends([rows[1]],'2026-01-07',days,metric,'Night')
                    _,points,actual,plan_points,planned=svg_series(single)
                    self.assertEqual(len(points),1)
                    self.assertEqual(points[0][1],230)
                    self.assertEqual(actual,[])
                    self.assertEqual(planned,[])
                    self.assertEqual(len(plan_points),int(metric=='投入卷数（实际 / 计划）'))
                    self.assertIn('只有 1 个日期',single)
        self.assertEqual(rows,before)


if __name__=='__main__':
    unittest.main()
