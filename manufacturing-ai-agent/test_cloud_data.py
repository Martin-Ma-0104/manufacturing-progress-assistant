import json
import sqlite3
import unittest
from cloud_data import decode_payload,import_payload,export_payload
from test_production import record

class CloudDataTests(unittest.TestCase):
    def test_list_import_duplicate_and_full_restore(self):
        payload=decode_payload(json.dumps([record()]))
        with sqlite3.connect(':memory:') as db:
            self.assertEqual(import_payload(payload,db),(1,0))
            self.assertEqual(import_payload(payload,db),(0,0))
            bundle=export_payload(db)
        with sqlite3.connect(':memory:') as db:
            import_payload(decode_payload(json.dumps(bundle)),db)
            self.assertEqual(export_payload(db),bundle)

    def test_event_conflict_rolls_back_production(self):
        event=dict(production_date='2026-01-01',shift='Day',machine_id='TEST1',from_product='A',to_product='B',confirmation_note='Confirmed synthetic event')
        payload={'records':[record()],'changeover_events':[event]}
        with sqlite3.connect(':memory:') as db:
            self.assertEqual(import_payload(payload,db),(1,1))
            conflict={'records':[record(machine_id='TEST2')],'changeover_events':[dict(event,to_product='C')]}
            with self.assertRaises(ValueError): import_payload(conflict,db)
            self.assertEqual(export_payload(db),payload)

    def test_invalid_or_unmatched_event(self):
        with self.assertRaises(ValueError): decode_payload('{"records":[]}')
        with self.assertRaises(ValueError): decode_payload('[null]')
        event=dict(production_date='2026-01-01',shift='Day',machine_id='OTHER',from_product='A',to_product='B',confirmation_note='synthetic')
        with sqlite3.connect(':memory:') as db:
            with self.assertRaises(ValueError): import_payload({'records':[record()],'changeover_events':[event]},db)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM slitting_records').fetchone()[0],0)

if __name__=='__main__': unittest.main()
