"""PDF export selection, weighted metrics, gaps, and pagination regressions."""
import unittest
from copy import deepcopy
from datetime import date,timedelta
from unittest.mock import patch
from reportlab.graphics.shapes import Circle,Drawing,Line,String
from reportlab.platypus import Paragraph,Table
import production_pdf as pdf
from test_production import record
from test_dashboard import CONFIRMED_EVENT,svg_series,trend_points
from production_trends import METRICS,render_trends


def texts(story):
    result=[]
    for item in story:
        if isinstance(item,Paragraph): result.append(item.getPlainText())
        elif isinstance(item,Table):
            result.extend(cell.getPlainText() for row in item._cellvalues for cell in row if isinstance(cell,Paragraph))
    return '\n'.join(result)


def drawing_series(drawing):
    points=[(item.cx,item.cy) for item in drawing.contents
            if isinstance(item,Circle) and item.r==3]
    # The plan-comparison legend sits above the plot at y=201.
    actual=[((item.x1,item.y1),(item.x2,item.y2)) for item in drawing.contents
            if isinstance(item,Line) and item.strokeColor==pdf.BLUE and item.y1!=201]
    plan_points=[(item.cx,item.cy) for item in drawing.contents
                 if isinstance(item,Circle) and item.r==2.5]
    planned=[((item.x1,item.y1),(item.x2,item.y2)) for item in drawing.contents
             if isinstance(item,Line) and item.strokeColor==pdf.GRAY and item.y1!=201]
    return points,actual,plan_points,planned


def connections(points,segments):
    """Compare connected observations independently of SVG/PDF axis orientation."""
    return [(points.index(start),points.index(end)) for start,end in segments]


class PdfTests(unittest.TestCase):
    def test_daily_filter_before_summary_and_details(self):
        rows=[record(planned_rolls=10,input_rolls=5),record(shift='Night',planned_rolls=30,input_rolls=30),record(machine_id='OTHER')]
        with patch.object(pdf,'build',side_effect=lambda story,*args:texts(story)):
            full=pdf.render_daily_pdf(rows,'2026-01-01',machine='TEST1')
            self.assertIn('87.5%',full)
            self.assertNotIn('OTHER',full)
            night=pdf.render_daily_pdf(rows,'2026-01-01','Night','TEST1')
            self.assertIn('100.0%',night)
            self.assertIn('夜班',night)
            self.assertNotIn('白班',night)

    def test_zero_missing_and_real_pdf(self):
        zero=record(planned_rolls=0,input_rolls=0,actual_output_m2=0,qualified_output_m2=0,reported_yield_pct=None)
        for rows in ([],[zero]):
            with patch.object(pdf,'build',side_effect=lambda story,*args:texts(story)):
                output=pdf.render_daily_pdf(rows,'2026-01-01')
                self.assertIn('—',output)
                self.assertNotIn('nan',output.lower())
            data=pdf.render_daily_pdf(rows,'2026-01-01')
            self.assertTrue(data.startswith(b'%PDF-'))
            self.assertTrue(data.rstrip().endswith(b'%%EOF'))

    def test_trend_gap_and_plan_dashes(self):
        dates=[f'2026-01-0{i}' for i in range(1,8)]
        rows=[dict(production_date=dates[i],input_rolls=5,planned_rolls=10,shift_count=1) for i in (0,2,3)]
        drawing=pdf.trend_drawing(rows,dates,'input_rolls','卷',11,True,None,523)
        # One legend segment plus two segments connecting the three recorded dates.
        actual=[x for x in drawing.contents if isinstance(x,Line) and x.strokeColor==pdf.BLUE]
        planned=[x for x in drawing.contents if isinstance(x,Line) and x.strokeColor==pdf.GRAY]
        self.assertEqual(len(actual),3)
        self.assertEqual(len(planned),3)
        self.assertTrue(all(x.strokeDashArray for x in planned))

    def test_all_shift_gap_geometry_matches_html_and_preserves_recorded_zero(self):
        rows=trend_points()
        before=deepcopy(rows)
        for days in (7,30):
            for metric in METRICS:
                for shift in (None,'Day','Night'):
                    with self.subTest(days=days,metric=metric,shift=shift):
                        with patch.object(pdf,'build',side_effect=lambda story,*args:story):
                            story=pdf.render_trend_pdf(rows,'2026-01-07',days,metric,shift,'TEST1')
                        drawing=next(item for item in story if isinstance(item,Drawing))
                        points,actual,plan_points,planned=drawing_series(drawing)
                        self.assertEqual(len(points),3)
                        self.assertEqual(points[1][1],36)
                        expected=[(0,1),(1,2)]
                        self.assertEqual(connections(points,actual),expected)
                        _,html_points,html_actual,html_plan_points,html_planned=svg_series(
                            render_trends(rows,'2026-01-07',days,metric,shift,'TEST1'))
                        self.assertEqual(connections(points,actual),connections(html_points,html_actual))
                        self.assertNotIn('2026-01-02',texts(story))
                        self.assertNotIn('2026-01-05',texts(story))
                        for day in ('2026-01-01','2026-01-03','2026-01-04'):
                            self.assertIn(day,texts(story))
                        if metric=='投入卷数（实际 / 计划）':
                            self.assertEqual(len(plan_points),3)
                            self.assertEqual(connections(plan_points,planned),expected)
                            self.assertEqual(connections(plan_points,planned),connections(html_plan_points,html_planned))
                            self.assertTrue(all(item.strokeDashArray for item in drawing.contents
                                                if isinstance(item,Line) and item.strokeColor==pdf.GRAY))
                        else:
                            self.assertEqual(planned,[])
        self.assertEqual(rows,before)

    def test_changeover_graphics_persist_and_only_details_are_optional(self):
        rows=trend_points()
        before=deepcopy(rows)
        for days in (7,30):
            outputs=[]
            for options in ({},{'show_changeovers':False},{'show_changeovers':True}):
                with patch.object(pdf,'build',side_effect=lambda story,*args:story):
                    outputs.append(pdf.render_trend_pdf(rows,'2026-01-07',days,shift='Night',**options))
            for story in outputs[:2]:
                self.assertNotIn(CONFIRMED_EVENT,texts(story))
            self.assertIn(CONFIRMED_EVENT,texts(outputs[2]))
            charts=[next(item for item in story if isinstance(item,Drawing)) for story in outputs]
            geometry=[[item.getProperties() for item in chart.contents] for chart in charts]
            self.assertEqual(geometry[0],geometry[1])
            self.assertEqual(geometry[0],geometry[2])
            for chart in charts:
                markers=[item for item in chart.contents if isinstance(item,Line) and item.strokeColor==pdf.PURPLE]
                rings=[item for item in chart.contents if isinstance(item,Circle) and item.strokeColor==pdf.PURPLE]
                self.assertEqual(len(markers),1)
                self.assertTrue(markers[0].strokeDashArray)
                self.assertEqual([(item.r,item.fillColor) for item in rings],[(6,None)])
                self.assertEqual([item.text for item in chart.contents if isinstance(item,String)
                                  and item.fillColor==pdf.PURPLE],['换产'])
            no_events=[dict(row,changeover=None) for row in rows]
            no_events += [dict(rows[0],production_date='2026-01-08',changeover=CONFIRMED_EVENT),
                          dict(rows[1],machine_id='TEST2')]
            for visible in (False,True):
                with patch.object(pdf,'build',side_effect=lambda story,*args:story):
                    selected=pdf.render_trend_pdf(no_events,'2026-01-07',days,shift='Night',
                                                  machine='TEST1',show_changeovers=visible)
                self.assertNotIn(CONFIRMED_EVENT,texts(selected))
                self.assertNotIn('TEST2',texts(selected))
                self.assertNotIn('2026-01-08',texts(selected))
                chart=next(item for item in selected if isinstance(item,Drawing))
                self.assertFalse(any(isinstance(item,(Line,Circle)) and item.strokeColor==pdf.PURPLE
                                     for item in chart.contents))
            for metric in METRICS:
                with self.subTest(days=days,metric=metric):
                    with patch.object(pdf,'build',side_effect=lambda story,*args:story):
                        story=pdf.render_trend_pdf([rows[1]],'2026-01-07',days,metric,'Night')
                    chart=next(item for item in story if isinstance(item,Drawing))
                    points,actual,plan_points,planned=drawing_series(chart)
                    self.assertEqual(len(points),1)
                    self.assertEqual(points[0][1],36)
                    self.assertEqual(actual,[])
                    self.assertEqual(planned,[])
                    self.assertEqual(len(plan_points),int(metric=='投入卷数（实际 / 计划）'))
                    self.assertIn('只有一个日期',texts(story))
        self.assertEqual(rows,before)

    def test_long_history_and_product_paginate(self):
        rows=[record(machine_id=f'TEST{i}',product='长产品描述'*30) for i in range(40)]
        daily=pdf.render_daily_pdf(rows,'2026-01-01')
        self.assertGreater(len(daily),1000)
        end=date(2026,1,30)
        points=[dict(machine_id='TEST1',production_date=(end-timedelta(days=i)).isoformat(),
                     input_rolls=i,planned_rolls=10,qualified_output_m2=100,shift_count=1,
                     changeover='已确认换产（白班）：A → B' if i==1 else None) for i in range(30)]
        self.assertTrue(pdf.render_trend_pdf(points,end.isoformat(),30,'投入卷数（实际 / 计划）').startswith(b'%PDF-'))
        with patch.object(pdf,'build',side_effect=lambda story,*args:texts(story)):
            selected=pdf.render_trend_pdf(points,end.isoformat(),7,machine='OTHER')
            self.assertIn('暂无生产记录',selected)
            self.assertNotIn('TEST1',selected)


if __name__=='__main__': unittest.main()
