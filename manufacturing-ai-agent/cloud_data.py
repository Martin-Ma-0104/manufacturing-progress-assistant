"""Private Cloud Demo JSON import/export; local files remain the source of truth."""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

from database import DB_PATH, get_connection
from production import FIELDS, import_records, validate

EVENT_SCHEMA = '''CREATE TABLE IF NOT EXISTS changeover_events (
    production_date TEXT NOT NULL, shift TEXT NOT NULL CHECK(shift IN ('Day','Night')),
    machine_id TEXT NOT NULL, from_product TEXT NOT NULL, to_product TEXT NOT NULL,
    confirmation_note TEXT NOT NULL, PRIMARY KEY(production_date,shift,machine_id))'''
EVENT_FIELDS=('production_date','shift','machine_id','from_product','to_product','confirmation_note')


def decode_payload(raw):
    payload=json.loads(raw)
    if isinstance(payload,list):
        payload={'records':payload,'changeover_events':[]}
    if not isinstance(payload,dict) or set(payload)!={'records','changeover_events'}:
        raise ValueError('Expected a record list or a bundle with records and changeover_events.')
    if not isinstance(payload['records'],list) or not payload['records']:
        raise ValueError('records must be a nonempty list.')
    if not isinstance(payload['changeover_events'],list):
        raise ValueError('changeover_events must be a list.')
    for record in payload['records']:
        if not isinstance(record,dict):
            raise ValueError('Each production record must be an object.')
        validate(record)
    for event in payload['changeover_events']:
        if not isinstance(event,dict) or set(event)!=set(EVENT_FIELDS):
            raise ValueError('Invalid changeover event fields.')
        if date.fromisoformat(event['production_date']).isoformat()!=event['production_date']:
            raise ValueError('Invalid changeover date.')
        if event['shift'] not in ('Day','Night'):
            raise ValueError('Invalid changeover shift.')
        if any(not isinstance(event[f],str) or not event[f].strip() for f in EVENT_FIELDS):
            raise ValueError('Changeover fields must be nonempty text.')
    return payload


def import_payload(payload, connection):
    # The outer transaction includes both records and confirmed changeover events.
    with connection:
        connection.execute(EVENT_SCHEMA)
        added=import_records(payload['records'],connection,manage_transaction=False)
        events_added=0
        for event in payload['changeover_events']:
            values=tuple(event[f] for f in EVENT_FIELDS)
            existing=connection.execute('SELECT '+','.join(EVENT_FIELDS)+' FROM changeover_events WHERE production_date=? AND shift=? AND machine_id=?',values[:3]).fetchone()
            if existing is not None:
                if tuple(existing)!=values:
                    raise ValueError('Conflicting confirmed changeover; batch rolled back.')
                continue
            if connection.execute('SELECT 1 FROM slitting_records WHERE production_date=? AND shift=? AND machine_id=?',values[:3]).fetchone() is None:
                raise ValueError('Changeover has no matching production record; batch rolled back.')
            connection.execute('INSERT INTO changeover_events VALUES (?,?,?,?,?,?)',values)
            events_added+=1
    return added,events_added


def export_payload(connection):
    records=[dict(zip(FIELDS,row)) for row in connection.execute('SELECT '+','.join(FIELDS)+' FROM slitting_records ORDER BY production_date,shift,machine_id,product')]
    has_events=connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='changeover_events'").fetchone()
    events=[dict(zip(EVENT_FIELDS,row)) for row in connection.execute('SELECT '+','.join(EVENT_FIELDS)+' FROM changeover_events ORDER BY production_date,shift,machine_id')] if has_events else []
    return {'records':records,'changeover_events':events}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export',type=Path,required=True)
    args=parser.parse_args()
    if not DB_PATH.is_file():
        parser.exit(1,'No local database to export.\n')
    try:
        with sqlite3.connect(f'file:{DB_PATH}?mode=ro',uri=True) as connection:
            bundle=export_payload(connection)
        args.export.parent.mkdir(parents=True,exist_ok=True)
        args.export.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'Exported {len(bundle["records"])} records and {len(bundle["changeover_events"])} confirmed events.')
    except (OSError,ValueError,sqlite3.Error) as error:
        parser.exit(1,f'Export failed: {error}\n')


if __name__=='__main__':
    main()
