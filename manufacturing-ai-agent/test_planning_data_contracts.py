"""Future modules stay explicitly unready; templates contain no fake observations."""
import json
import unittest
from planning_data_contracts import blueprint,readiness,template_bytes


class PlanningContractTests(unittest.TestCase):
    def test_all_modules_blocked_and_dependencies_explicit(self):
        statuses=readiness()
        self.assertEqual(len(statuses),3)
        self.assertTrue(all(not r['calculation_enabled'] for r in statuses))
        self.assertIn('production_allocations',statuses[1]['missing_entities'])
        self.assertIn('product_bom',statuses[2]['missing_entities'])

    def test_preparation_only_empty_records_and_explicit_units(self):
        template=json.loads(template_bytes())
        self.assertIn('not accepted',template['purpose'])
        for entity in template['entities'].values():
            self.assertEqual(entity['records'],[])
            self.assertTrue(all(f['type_and_unit'] for f in entity['fields']))
        self.assertIn('cannot exceed',str(template['entities']['production_allocations']))
        self.assertIn('Missing units',str(template['rules']))

    def test_caller_changes_do_not_mark_real_modules_ready(self):
        a=blueprint();a['modules'].clear();a['entities']['order_lines']['records'].append({'fake':True})
        b=blueprint()
        self.assertEqual(len(b['modules']),3)
        self.assertEqual(b['entities']['order_lines']['records'],[])
