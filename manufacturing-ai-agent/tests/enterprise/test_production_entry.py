import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import ProductionEntry
from backend.production_entry import save_entry
from production import SCHEMA

HEADERS = {'X-Local-Client': 'manufacturing-web', 'Origin': 'http://127.0.0.1:3000'}


def record(**changes):
    return dict(production_date='2026-10-20', shift='Day', machine_id='FX1', product='TEST-ONLY',
                planned_rolls=10, input_rolls=8, qualified_rolls=40,
                actual_output_m2=100.5, qualified_output_m2=90.0, reported_yield_pct=None,
                source_report_date='2026-10-20', source_shift_label='Day',
                source_name='PRIVATE TEST SOURCE', notes='PRIVATE TEST NOTE',
                confirmed_real=True, source='reviewed', **changes)


@pytest.fixture
def writable(tmp_path, monkeypatch):
    path=tmp_path/'entry-test.db'
    monkeypatch.setenv('PRODUCTION_DB', str(path))
    with sqlite3.connect(path) as c:
        c.execute(SCHEMA)
        c.execute('CREATE TABLE untouched(value TEXT)')
        c.execute("INSERT INTO untouched VALUES ('preserve')")
    with TestClient(app) as client:
        yield client, path
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT value FROM untouched').fetchall() == [('preserve',)]
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


def post(client, payload):
    return client.post('/api/production/records', headers=HEADERS, json=payload)


def test_save_read_statistics_and_source_retention(writable):
    client, db = writable
    payload=record()
    result=post(client,payload)
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'saved'
    response=client.get('/api/dashboard/summary',params={'start':'2026-10-20','end':'2026-10-20','machine':'FX1','shift':'Day'})
    assert response.status_code == 200
    data=response.json()
    assert data['source']=='reviewed' and data['summary']['planned_rolls']==10
    assert data['summary']['input_rolls']==8 and data['summary']['attainment']=='80.0%'
    assert data['summary']['qualified_output_m2']==90.0
    assert 'PRIVATE' not in response.text
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT source_name,notes FROM slitting_records').fetchone()==('PRIVATE TEST SOURCE','PRIVATE TEST NOTE')


def test_duplicate_conflict_and_retry_are_safe(writable):
    client,db=writable
    assert post(client,record()).json()['added']==1
    assert post(client,record()).json()['status']=='unchanged'
    assert post(client,dict(record(),input_rolls=9)).status_code==409
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*),max(input_rolls) FROM slitting_records').fetchone()==(1,8)


@pytest.mark.parametrize('change',[
    {'planned_rolls':-1},{'input_rolls':1.5},{'qualified_rolls':True},
    {'qualified_output_m2':101},{'actual_output_m2':'100'}, {'reported_yield_pct':101},
    {'production_date':'2026-02-30'},{'source_report_date':0},{'source_report_date':'20261020'},
    {'shift':'All'},{'source_name':'   '},{'product':' '}, {'machine_id':'DEMO-M1'},
    {'confirmed_real':False},{'confirmed_real':1},{'source':'demo'}, {'sql':'DROP TABLE'},
])
def test_invalid_record_does_not_write(writable,change):
    client,db=writable
    assert post(client,dict(record(),**change)).status_code==422
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT count(*) FROM slitting_records').fetchone()[0]==0


def test_required_fields_and_origin(writable):
    client,db=writable
    for field in ['planned_rolls','source_name','confirmed_real']:
        payload=record();del payload[field]
        assert post(client,payload).status_code==422
    assert client.post('/api/production/records',json=record()).status_code==403
    assert client.post('/api/production/records',headers={**HEADERS,'Origin':'https://evil.example'},json=record()).status_code==403


def test_concurrent_identical_submissions(writable):
    _,db=writable
    value=ProductionEntry(**record())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:save_entry(value),range(2)))
    assert sorted(r['added'] for r in results)==[0,1]


def test_no_implicit_database_creation(writable,monkeypatch,tmp_path):
    client,_=writable
    missing=tmp_path/'missing.db';monkeypatch.setenv('PRODUCTION_DB',str(missing))
    assert post(client,record()).status_code==503
    assert not missing.exists()


def test_web_rejects_demo_in_all_routes(writable):
    client,_=writable
    for path in ['/api/production/options','/api/dashboard/summary','/api/production','/api/production/machines','/api/production/machines/FX1','/api/production/downtime','/api/reports/selection.html','/api/reports/selection.pdf']:
        assert client.get(path,params={'source':'demo'}).status_code==422,path
    with patch('backend.main.answer') as answer:
        assert client.post('/api/agent/chat',headers=HEADERS,json={'message':'production','scope':{'source':'demo'}}).status_code==422
        answer.assert_not_called()
    assert client.get('/api/inventory').json()['items']==[]
