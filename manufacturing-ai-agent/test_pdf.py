"""PDF export selection, weighted metrics, gaps, and pagination regressions."""
import unittest
from datetime import date,timedelta
from unittest.mock import patch
from reportlab.graphics.shapes import Line
from reportlab.platypus import Paragraph,Table
import production_pdf as pdf
from test_production import record


def texts(story):
    result=[]
    for item in story:
        if isinstance(item,Paragraph): result.append(item.getPlainText())
        elif isinstance(item,Table):
            result.extend(cell.getPlainText() for row in item._cellvalues for cell in row if isinstance(cell,Paragraph))
    return '\n'.join(result)


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
        # One legend segment and exactly one adjacent-date segment; no line across Jan 2.
        actual=[x for x in drawing.contents if isinstance(x,Line) and x.strokeColor==pdf.BLUE]
        planned=[x for x in drawing.contents if isinstance(x,Line) and x.strokeColor==pdf.GRAY]
        self.assertEqual(len(actual),2)
        self.assertEqual(len(planned),2)
        self.assertTrue(all(x.strokeDashArray for x in planned))

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
