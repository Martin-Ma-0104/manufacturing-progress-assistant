"""Evidence alignment, gaps, boundaries and mocked diagnostic tool integration."""
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from ai_production_data import normalize_scope,read_snapshot,query_diagnostics,export_preview
from ai_production_client import ask_production,AgentError
from ai_production_charts import bar_spec,csv_bytes
from cloud_data import import_payload
from production_diagnostics import analyze,presentation
from production_dashboard import summarize
from test_ai_production_data import record
from test_abnormality import event
from test_ai_production_client import FakeClient,call_response,choose_first_fact


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'source.db'
        self.rows=[record(machine='FX1',planned_rolls=10,input_rolls=3),
                   record(machine='FX1',product='OTHER-SPEC',planned_rolls=10,input_rolls=12),
                   record(machine='FX2',planned_rolls=0,input_rolls=0,actual_output_m2=0,qualified_output_m2=0)]
        self.events=[event(),event('SECOND',category='QC'),
                     event('ZERO',machine_id='FX3',reported_minutes=0),
                     event('UNKNOWN',machine_id='FX4',shift=None,reported_minutes=None,started_at=None,ended_at=None)]
        with sqlite3.connect(self.db) as c:
            import_payload(dict(records=self.rows,changeover_events=[],abnormality_events=self.events),c)
        self.scope=normalize_scope('2026-01-01','2026-01-03')
        self.snapshot=read_snapshot(self.scope,self.db)
        self.before=self.db.read_bytes()
        self.q=dict(start_date='2026-01-01',end_date='2026-01-03',shift='All',machines=[],group_by='machine',chart='deviation')

    def tearDown(self):
        self.assertEqual(self.db.read_bytes(),self.before)

    def test_independent_aggregation_no_event_join_and_no_netting_shortfalls(self):
        s=analyze(self.snapshot)['summary']
        for k,v in summarize(self.rows).items():self.assertEqual(s[k],v)
        self.assertEqual((s['input_delta'],s['input_shortfall'],s['input_excess']),(-5,7,2))
        self.assertEqual(s['abnormalities']['reported_minutes'],120)
        self.assertEqual(s['abnormalities']['overlap_event_count'],2)
        row=next(r for r in analyze(self.snapshot)['rows'] if r['设备']=='FX1')
        self.assertEqual(row['实际投入（母卷）'],15)
        self.assertIn('OTHER-SPEC',row['产品／规格'])
        self.assertEqual(row['异常记录数（条）'],2)

    def test_missing_production_and_missing_anomalies_are_not_zero(self):
        rows={r['设备']:r for r in analyze(self.snapshot,'machine')['rows']}
        self.assertIsNone(rows['FX3']['实际投入（母卷）'])
        self.assertEqual(rows['FX3']['异常记录时长合计（分钟）'],0)
        self.assertIsNone(rows['FX4']['异常记录时长合计（分钟）'])
        self.assertIsNone(rows['FX2']['异常记录时长合计（分钟）'])
        self.assertEqual(rows['FX2']['实际投入（母卷）'],0)
        self.assertEqual(rows['FX2']['面积合格率'],'—')
        self.assertEqual(rows['FX2']['异常记录数（条）'],0)

    def test_category_shares_partial_zero_and_empty_denominators(self):
        rows=analyze(self.snapshot,'category')['rows']
        self.assertEqual({r['异常类别']:r['已知事件分钟占比'] for r in rows},{'Equipment':'50.0%','QC':'50.0%'})
        empty=dict(self.snapshot,rows=[],abnormalities=[self.events[2]])
        self.assertEqual(analyze(empty,'category')['rows'][0]['已知事件分钟占比'],'不可用')
        self.assertIsNone(analyze(dict(empty,abnormalities=[]))['summary']['input_shortfall'])

    def test_tool_filters_scope_and_never_exposes_raw_events_or_sources(self):
        envelope,p=query_diagnostics(self.snapshot,self.q)
        for token in ['PRIVATE','event_id','started_at','ended_at','OTHER-SPEC','source_name','notes']:
            self.assertNotIn(token,json.dumps(envelope))
        self.assertIn('OTHER-SPEC',json.dumps(p))
        for change in [dict(sql='SELECT'),dict(start_date='2025-12-31'),dict(machines=['UNKNOWN']),
                       dict(group_by='capacity'),dict(chart='deviation',group_by='date')]:
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                query_diagnostics(self.snapshot,{**self.q,**change})
        narrow=read_snapshot(normalize_scope('2026-01-01','2026-01-01','Day',['FX1']),self.db)
        for change in [dict(shift='All'),dict(machines=['FX2'])]:
            with self.assertRaises(ValueError):query_diagnostics(narrow,{**self.q,'end_date':'2026-01-01',**change})
        _,day=query_diagnostics(self.snapshot,{**self.q,'shift':'Day','chart':'none','group_by':'details'})
        self.assertNotIn('班次未确认',str(day['rows']))

    def test_table_csv_and_chart_agree_and_signed_deviation_remains_signed(self):
        _,p=query_diagnostics(self.snapshot,self.q)
        self.assertEqual(p['chart']['rows'],[{'label':'FX1','value':-5},{'label':'FX2','value':0}])
        self.assertEqual(bar_spec(p['chart'])['data']['values'],p['chart']['rows'])
        self.assertNotIn('domainMin',str(bar_spec(p['chart'])))
        csv_rows=list(csv.DictReader(io.StringIO(csv_bytes(p).decode('utf-8-sig'))))
        self.assertEqual(csv_rows[0]['投入偏差（实际−计划，母卷）'],'-5')
        self.assertEqual(csv_rows[2]['实际投入（母卷）'],'')

    def test_mocked_two_calls_return_only_program_facts_and_respect_budget(self):
        fake=FakeClient([call_response('query_diagnostics',self.q),choose_first_fact])
        answer=ask_production('汇总差距及同期异常',self.snapshot,api_key='synthetic',consent=True,client_factory=fake.factory)
        self.assertEqual(len(fake.requests),2)
        self.assertTrue(all(len(json.dumps(r,ensure_ascii=False).encode())<=32768 for r in fake.requests))
        self.assertEqual(answer['presentation']['chart']['rows'][0]['value'],-5)
        text=' '.join(f['text'] for f in answer['facts'])
        self.assertIn('未达计划逐记录合计7',text)
        self.assertIn('超额投入逐记录合计2',text)
        self.assertNotIn('PRIVATE',json.dumps(fake.requests))
        self.assertNotIn('PRIVATE',json.dumps(export_preview(self.snapshot)))

    def test_unconsented_and_unsupported_forecast_no_fabrication(self):
        fake=FakeClient([])
        with self.assertRaises(AgentError):ask_production('未来产能',self.snapshot,api_key='synthetic',consent=False,client_factory=fake.factory)
        self.assertEqual(fake.requests,[])
        fake=FakeClient([call_response('request_clarification',{'reason':'unsupported'})])
        result=ask_production('预计真实订单何时完成',self.snapshot,api_key='synthetic',consent=True,client_factory=fake.factory)
        self.assertEqual(result['status'],'clarification')
        self.assertEqual(len(fake.requests),1)

    def test_page_without_model_and_filters_framework_and_csv_are_available(self):
        script=Path(self.tmp.name)/'page.py'
        script.write_text('from production_diagnostics_ui import render_diagnostics\nrender_diagnostics('+repr(str(self.db))+')\n')
        with patch('ai_production_client.ask_production') as ask:
            app=AppTest.from_file(str(script),default_timeout=15).run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(app.metric[0].value,'7 母卷')
            self.assertEqual(app.metric[1].value,'2 母卷')
            self.assertEqual(len(app.tabs),2)
            app.selectbox(key='diagnostic_shift').set_value('夜班').run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(app.metric[0].value,'—')
            ask.assert_not_called()

    def test_long_result_truncation_explicit_and_chart_not_silently_truncated(self):
        rows=[dict(self.rows[0],machine_id=f'TEST{i}') for i in range(1001)]
        snap=dict(self.snapshot,rows=rows,abnormalities=[])
        p=presentation(snap,'machine')
        self.assertEqual((len(p['rows']),p['total_rows'],p['truncated']),(1000,1001,True))
        with self.assertRaises(ValueError):presentation(snap,'machine','deviation')

    def test_floating_assistant_explicitly_adopts_analysis_scope_and_resets_consent(self):
        script=Path(self.tmp.name)/'integrated.py'
        script.write_text('from ai_floating_panel import render_floating_assistant\n'
                          'from production_diagnostics_ui import render_diagnostics\n'
                          'render_floating_assistant("生产分析",'+repr(str(self.db))+')\n'
                          'render_diagnostics('+repr(str(self.db))+')\n')
        with patch('ai_production_ui._api_key',return_value='synthetic'),patch('ai_production_ui.ask_production') as ask:
            app=AppTest.from_file(str(script),default_timeout=15).run()
            app.button(key='ai_launcher').click().run()
            app.button(key='ai_settings').click().run()
            app.selectbox(key='ai_shift').set_value('夜班').run()
            app.checkbox(key='ai_allow_send').set_value(True).run()
            app.selectbox(key='diagnostic_shift').set_value('白班').run()
            self.assertEqual(app.selectbox(key='ai_shift').value,'夜班')
            app.button(key='ai_adopt_scope').click().run()
            self.assertEqual(len(app.exception),0)
            self.assertEqual(app.selectbox(key='ai_shift').value,'白班')
            self.assertFalse(app.checkbox(key='ai_allow_send').value)
            ask.assert_not_called()
