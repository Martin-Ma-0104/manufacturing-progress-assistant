"""Synthetic anomaly/import/query/chart/UI regressions. No paid model calls."""
import copy
import csv
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import abnormality as ab
from cloud_data import decode_payload, import_payload, export_payload
from production import import_records
from production_dashboard import summarize
from ai_production_data import (read_snapshot, normalize_scope, query_analysis, legacy_presentation,
                                catalog, export_preview, METRIC_LABELS, METRICS)
from ai_production_client import ask_production, AgentError
from ai_production_charts import bar_spec, csv_bytes, safe_cell
from test_ai_production_data import record
from test_ai_production_client import FakeClient, call_response, choose_first_fact


def event(event_id='E1', **changes):
    result=dict(event_id=event_id,production_date='2026-01-01',shift='Day',machine_id='FX1',
                category='Equipment',subcategory='PRIVATE-subcategory',started_at='2026-01-01T08:00',
                ended_at='2026-01-01T09:00',reported_minutes=60,status='Closed',
                source_name='PRIVATE-source.png',notes='PRIVATE-source-note')
    result.update(changes)
    return result


def query(**changes):
    result=dict(start_date='2026-01-01',end_date='2026-01-03',shift='All',machines=[],
                domain='abnormalities',group_by='machine',metrics=['reported_minutes','event_count'],
                categories=[],status='All',chart='bar')
    result.update(changes)
    return result


class AbnormalityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'test.db'
        self.events=[event(),event('E2',started_at='2026-01-01T08:30',ended_at='2026-01-01T09:30',
                                  category='QC',reported_minutes=50,status='Open'),
                     event('E3',shift=None,started_at=None,ended_at=None,reported_minutes=None,status='Unknown'),
                     event('E4',machine_id='FX2',reported_minutes=0,started_at=None,ended_at=None),
                     event('E5',machine_id='FX3',reported_minutes=None,started_at=None,ended_at=None),
                     event('E6',production_date='2026-01-02',shift='Night',machine_id='FX2',
                           started_at='2026-01-02T23:30',ended_at='2026-01-03T00:30',reported_minutes=60)]
        self.production=[record(machine='FX1'),record(machine='FX2',planned_rolls=30,input_rolls=30)]
        with sqlite3.connect(self.db) as c:
            import_payload(dict(records=self.production,changeover_events=[],abnormality_events=self.events),c)
        self.scope=normalize_scope('2026-01-01','2026-01-03')

    def snapshot(self):
        return read_snapshot(self.scope,self.db)

    def test_strict_validation_explicit_cross_midnight_and_missing(self):
        for e in self.events:
            ab.validate(e)
        for changes in (dict(reported_minutes=-1),dict(reported_minutes=float('nan')),
                        dict(reported_minutes=True),dict(shift='Day?'),dict(status='Running'),
                        dict(started_at='08:00'),dict(ended_at='2026-01-01T07:00'),
                        dict(production_date='20260101'),dict(machine_id=''),dict(sql='DROP')):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                ab.validate(event(**changes))
        self.assertEqual(ab.interval_minutes(self.events[-1]),60)
        self.assertIsNone(ab.interval_minutes(self.events[2]))

    def test_missing_zero_overlap_and_reported_interval_mismatch(self):
        s=ab.summarize(self.events)
        self.assertEqual(s['reported_minutes'],170)
        self.assertEqual(s['valid_minutes_count'],4)
        self.assertEqual(s['missing_minutes_count'],2)
        self.assertEqual(s['overlap_event_count'],2)
        self.assertEqual(s['mismatch_count'],1)
        self.assertEqual(s['unknown_shift_count'],1)
        self.assertEqual(ab.overlap_ids(self.events),{'E1','E2'})
        self.assertIsNone(ab.summarize([])['reported_minutes'])
        self.assertIsNone(ab.summarize([self.events[2]])['reported_minutes'])
        self.assertEqual(ab.summarize([self.events[3]])['reported_minutes'],0)

    def test_overlap_across_dates_and_categories_not_different_machines_or_adjacent(self):
        events=[event('a',started_at='2026-01-01T23:00',ended_at='2026-01-02T02:00'),
                event('b',production_date='2026-01-02',category='QC',started_at='2026-01-02T00:00',ended_at='2026-01-02T01:00'),
                event('c',started_at='2026-01-02T02:00',ended_at='2026-01-02T03:00'),
                event('d',machine_id='OTHER')]
        self.assertEqual(ab.overlap_ids(events),{'a','b'})

    def test_independent_events_without_production_and_catalog(self):
        db=Path(self.tmp.name)/'events-only.db'
        with sqlite3.connect(db) as c:
            self.assertEqual(import_payload({'abnormality_events':[event(machine_id='NO-PRODUCTION')]},c),(0,0,1))
        self.assertEqual(catalog(db),{'dates':['2026-01-01'],'machines':['NO-PRODUCTION']})
        s=read_snapshot(self.scope,db)
        self.assertEqual(s['rows'],[])
        env,p=query_analysis(s,query())
        self.assertEqual(p['chart']['rows'],[{'label':'NO-PRODUCTION','value':60}])
        self.assertIn('不代表实际净停机',env['coverage']['text'])

    def test_old_bundle_restore_preserves_existing_abnormalities(self):
        with sqlite3.connect(self.db) as c:
            self.assertEqual(import_payload({'records':self.production,'changeover_events':[]},c),(0,0))
            bundle=export_payload(c)
        self.assertEqual(len(bundle['abnormality_events']),6)
        with sqlite3.connect(':memory:') as c:
            self.assertEqual(import_payload(decode_payload(json.dumps(bundle)),c),(2,0,6))
            self.assertEqual(export_payload(c),bundle)
            self.assertEqual(import_payload(bundle,c),(0,0,0))

    def test_conflicting_id_rolls_back_whole_combined_batch(self):
        with sqlite3.connect(self.db) as c:
            before=export_payload(c)
            payload=dict(records=[record(machine='NEW')],changeover_events=[],
                         abnormality_events=[event('NEW'),event(status='Open')])
            with self.assertRaises(ValueError):
                import_payload(payload,c)
            self.assertEqual(export_payload(c),before)
        # Status changes need reviewed corrections, never silent overwrite.
        with sqlite3.connect(self.db) as c,self.assertRaises(ValueError):
            import_payload({'abnormality_events':[event(status='Open')]},c)

    def test_snapshot_privacy_and_abnormality_only_version_change(self):
        s=self.snapshot()
        self.assertEqual(s['summary'],summarize(self.production))
        self.assertNotIn('PRIVATE-source',json.dumps(s))
        self.assertNotIn('source_name',json.dumps(s))
        self.assertNotIn('notes',json.dumps(s))
        before=self.db.read_bytes()
        read_snapshot(self.scope,self.db)
        self.assertEqual(before,self.db.read_bytes())
        with sqlite3.connect(self.db) as c:
            import_payload({'abnormality_events':[event('ADDED',reported_minutes=15)]},c)
        changed=self.snapshot()
        self.assertNotEqual(s['version'],changed['version'])
        self.assertEqual(s['summary'],changed['summary'])

    def test_group_table_and_bar_share_values_missing_group_has_no_zero_bar(self):
        env,p=query_analysis(self.snapshot(),query())
        self.assertEqual(p['chart']['rows'],[{'label':'FX1','value':110},{'label':'FX2','value':60}])
        self.assertEqual(p['chart']['omitted_groups'],1)
        self.assertEqual(p['chart']['partial_groups'],[{'label':'FX1','missing_count':1}])
        rows={r['设备']:r for r in p['rows']}
        self.assertIsNone(rows['FX3'][METRIC_LABELS['reported_minutes']])
        self.assertEqual(rows['FX1'][METRIC_LABELS['missing_minutes_count']],1)
        for r in p['chart']['rows']:
            self.assertEqual(rows[r['label']][METRIC_LABELS['reported_minutes']],r['value'])
        self.assertNotIn('PRIVATE',json.dumps(env))

    def test_shift_unknown_status_and_category_filters_narrow_without_inference(self):
        s=self.snapshot()
        for args,count,minutes in [(dict(shift='Day'),4,110),(dict(shift='Night'),1,60),
                                   (dict(status='Open'),1,50),(dict(categories=['QC']),1,50)]:
            q=query(group_by='overview',chart='none',**args)
            env,p=query_analysis(s,q)
            self.assertEqual(p['rows'][0][METRIC_LABELS['event_count']],count)
            self.assertEqual(p['rows'][0][METRIC_LABELS['reported_minutes']],minutes)
        _,p=query_analysis(s,query(group_by='shift'))
        self.assertEqual(len(p['rows']),3)
        self.assertTrue(any(r['班次']=='班次未确认' for r in p['rows']))

    def test_detail_times_stay_local_and_no_private_notes(self):
        env,p=query_analysis(self.snapshot(),query(group_by='details',chart='none'))
        self.assertEqual(len(p['rows']),6)
        self.assertTrue(p['rows'][0]['时间重叠'])
        self.assertIn('PRIVATE-subcategory',json.dumps(p))
        self.assertNotIn('PRIVATE',json.dumps(env))
        self.assertNotIn('started_at',json.dumps(export_preview(self.snapshot())))
        self.assertNotIn('PRIVATE',json.dumps(export_preview(self.snapshot())))

    def test_no_records_and_zero_values_are_distinct(self):
        env,p=query_analysis(self.snapshot(),query(start_date='2026-01-03',group_by='overview',chart='none'))
        self.assertEqual(p['rows'],[])
        self.assertIn('不代表没有异常',env['coverage']['text'])
        _,p=query_analysis(self.snapshot(),query(end_date='2026-01-01',machines=['FX2']))
        self.assertEqual(p['chart']['rows'],[{'label':'FX2','value':0}])

    def test_production_shift_and_wide_tables_reuse_weighted_ratios(self):
        _,p=query_analysis(self.snapshot(),query(domain='production',group_by='shift',metrics=list(METRICS),chart='none'))
        self.assertEqual(len(p['rows']),1)
        self.assertEqual(p['rows'][0]['投入计划达成率'],'87.5%')
        self.assertEqual(len(p['rows'][0]),10)
        with sqlite3.connect(self.db) as c:
            import_records([record(machine=f'FX{i}') for i in range(4,16)],c)
        legacy=dict(view='comparison',start_date='2026-01-01',end_date='2026-01-03',shift='All',machines=[],metrics=['input_rolls'])
        table=legacy_presentation(self.snapshot(),legacy)
        self.assertEqual(table['total_rows'],14)
        self.assertFalse(table['truncated'])

    def test_scope_injection_and_illegal_combinations_rejected(self):
        s=read_snapshot(normalize_scope('2026-01-01','2026-01-03','Day',['FX1']),self.db)
        for changes in (dict(start_date='2025-12-01'),dict(shift='All'),dict(machines=['FX2']),
                        dict(categories=['Made up']),dict(group_by='sql'),dict(sql='DELETE'),
                        dict(metrics=['net_downtime']),dict(domain='production',chart='bar'),
                        dict(group_by='details',chart='bar')):
            args=query(shift='Day',**{k:v for k,v in changes.items() if k!='shift'})
            args.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                query_analysis(s,args)

    def test_model_receives_aggregates_never_local_table_times_ids_or_subcategories(self):
        fake=FakeClient([call_response(name='query_analysis',arguments=query(group_by='details',chart='none')),choose_first_fact])
        result=ask_production('列出异常并总结',self.snapshot(),api_key='synthetic',consent=True,client_factory=fake.factory)
        self.assertEqual(len(fake.requests),2)
        packets=json.dumps(fake.requests,ensure_ascii=False)
        self.assertNotIn('PRIVATE',packets)
        self.assertNotIn('2026-01-01T08:00',packets)
        self.assertNotIn('presentation',json.loads(fake.requests[1]['input'][-1]['output']))
        self.assertEqual(len(result['presentation']['rows']),6)
        self.assertLessEqual(len(result['facts']),8)

    def test_table_not_truncated_by_model_fact_selection(self):
        fake=FakeClient([call_response(name='query_analysis',arguments=query()),choose_first_fact])
        result=ask_production('画图',self.snapshot(),api_key='synthetic',consent=True,client_factory=fake.factory)
        self.assertEqual(len(result['facts']),2)
        self.assertEqual(len(result['presentation']['rows']),3)
        self.assertEqual(result['presentation']['chart']['rows'][0]['value'],110)

    def test_csv_headers_values_bom_and_formula_labels(self):
        _,p=query_analysis(self.snapshot(),query())
        decoded=csv_bytes(p).decode('utf-8-sig')
        rows=list(csv.DictReader(io.StringIO(decoded)))
        self.assertEqual(float(rows[0][METRIC_LABELS['reported_minutes']]),110)
        self.assertEqual(rows[2][METRIC_LABELS['reported_minutes']],'')
        p['rows'][0]['设备']='  =HYPERLINK("bad")'
        self.assertIn("'  =HYPERLINK",csv_bytes(p).decode('utf-8-sig'))
        self.assertEqual(safe_cell(p['rows'][0]['设备']),"'  =HYPERLINK(\"bad\")")
        self.assertEqual(safe_cell(0),0)

    def test_bar_spec_real_values_labels_zero_axis_and_long_category_orientation(self):
        _,p=query_analysis(self.snapshot(),query())
        spec=bar_spec(p['chart'])
        self.assertEqual(spec['data']['values'],p['chart']['rows'])
        self.assertEqual(spec['layer'][0]['encoding']['x']['axis']['labelAngle'],0)
        self.assertEqual(spec['layer'][0]['encoding']['y']['scale']['domainMin'],0)
        self.assertEqual(spec['layer'][1]['encoding']['text']['field'],'value')
        chart=dict(group='异常类别',rows=[dict(label='A very long category description',value=60)],omitted_groups=0)
        self.assertEqual(bar_spec(chart)['layer'][0]['encoding']['y']['field'],'label')

    def test_details_cap_is_explicit_and_csv_matches_only_shown_rows(self):
        s=self.snapshot()
        s['abnormalities']=[dict(self.events[0],event_id='CAP-'+str(i)) for i in range(1001)]
        env,p=query_analysis(s,query(group_by='details',chart='none'))
        self.assertEqual(p['total_rows'],1001)
        self.assertEqual(len(p['rows']),1000)
        self.assertTrue(p['truncated'])
        self.assertEqual(len(list(csv.DictReader(io.StringIO(csv_bytes(p).decode('utf-8-sig'))))),1000)
        self.assertNotIn('CAP-0',json.dumps(env))

    def test_old_database_without_anomaly_table_is_read_only_empty_not_zero(self):
        db=Path(self.tmp.name)/'old.db'
        with sqlite3.connect(db) as c:
            import_records(self.production,c)
        before=db.read_bytes()
        s=read_snapshot(self.scope,db)
        env,p=query_analysis(s,query())
        self.assertEqual(s['abnormalities'],[])
        self.assertEqual(p['chart']['rows'],[])
        self.assertEqual(p['rows'],[])
        self.assertIn('暂无已录入异常记录',env['coverage']['text'])
        self.assertEqual(before,db.read_bytes())

    def test_declared_all_groups_remain_in_table_when_summary_pool_is_bounded(self):
        s=self.snapshot()
        s['abnormalities']=[dict(self.events[0],event_id='GROUP-'+str(i),machine_id='FX'+str(i)) for i in range(25)]
        s['available_machines']=['FX'+str(i) for i in range(25)]
        env,p=query_analysis(s,query())
        self.assertEqual(p['total_rows'],25)
        self.assertEqual(len(p['chart']['rows']),25)
        self.assertTrue(any('前20组' in f['text'] for f in env['facts']))

    def test_model_missing_aggregate_selection_cannot_hide_summary_or_coverage(self):
        from test_ai_production_client import answer_response
        def choose_last(request):
            data=json.loads(request['input'][-1]['output'])
            return answer_response({'fact_ids':[data['facts'][-1]['id']]})
        fake=FakeClient([call_response(name='query_analysis',arguments=query()),choose_last])
        result=ask_production('画图',self.snapshot(),api_key='synthetic',consent=True,client_factory=fake.factory)
        texts=' '.join(f['text'] for f in result['facts'])
        self.assertIn('异常合计',texts)
        self.assertIn('不代表实际净停机',texts)

    def test_long_chat_history_trims_without_duplicate_table_widget_keys(self):
        from streamlit.testing.v1 import AppTest
        import ai_production_ui as ui
        script=Path(self.tmp.name)/'long_ui.py'
        script.write_text('import ai_production_ui as ui\nui.render_agent('+repr(str(self.db))+',compact=True)')
        at=AppTest.from_file(str(script),default_timeout=15)
        def mocked(question,snapshot,**options):
            q=query(start_date=snapshot['scope']['start_date'],end_date=snapshot['scope']['end_date'])
            env,p=query_analysis(snapshot,q)
            return dict(status='answered',**env,presentation=p,usage={})
        with patch.object(ui,'_api_key',return_value='synthetic'),patch.object(ui,'ask_production',side_effect=mocked) as ask:
            at.run().chat_input[0].set_value('画图').run()
            at.button(key='ai_confirm_send').click().run()
            for _ in range(21):
                at.chat_input[0].set_value('画图').run()
                self.assertEqual(len(at.exception),0)
            self.assertEqual(ask.call_count,1)
            self.assertEqual(len(at.session_state['ai_history']),20)

    def test_ui_table_chart_cache_and_abnormality_change_reset(self):
        from streamlit.testing.v1 import AppTest
        import ai_production_ui as ui
        script=Path(self.tmp.name)/'ui.py'
        script.write_text('import ai_production_ui as ui\nui.render_agent('+repr(str(self.db))+',compact=True)')
        at=AppTest.from_file(str(script),default_timeout=10)
        def mocked(question,snapshot,**options):
            q=query(start_date=snapshot['scope']['start_date'],end_date=snapshot['scope']['end_date'])
            env,p=query_analysis(snapshot,q)
            return dict(status='answered',**env,presentation=p,usage={})
        with patch.object(ui,'_api_key',return_value='synthetic'),patch.object(ui,'ask_production',side_effect=mocked) as ask:
            at.run()
            at.chat_input[0].set_value('本周异常柱状图').run()
            self.assertEqual(ask.call_count,0)
            at.button(key='ai_confirm_send').click().run()
            self.assertEqual(len(at.exception),0)
            self.assertEqual(len(at.dataframe),1)
            self.assertEqual(len(at.get('vega_lite_chart')),1)
            at.chat_input[0].set_value('本周异常柱状图').run()
            self.assertEqual(ask.call_count,1)
            self.assertEqual(len(at.dataframe),2)
            self.assertEqual(len(at.exception),0)
            with sqlite3.connect(self.db) as c:
                import_payload({'abnormality_events':[event('new',reported_minutes=20)]},c)
            at.run()
            self.assertFalse(at.session_state['ai_consent_saved'])
            self.assertEqual(len(at.chat_message),0)
            self.assertEqual(ask.call_count,1)


if __name__=='__main__':
    unittest.main()
