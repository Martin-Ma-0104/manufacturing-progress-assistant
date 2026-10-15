"""Order progress arithmetic and selection regressions using synthetic data."""
import unittest
from order_progress_demo import DEMO_ORDERS, progress_summary


class OrderProgressTests(unittest.TestCase):
    def test_order_totals_and_daily_accumulation(self):
        order = DEMO_ORDERS[0]
        result = progress_summary(order['target'], order['rows'])
        self.assertEqual((result['completed'], result['remaining'], result['ratio']), (650, 350, .65))
        self.assertEqual([p['累计合格成品卷数'] for p in result['points']], [150, 350, 650])
        self.assertEqual(result['points'][1]['当日合格成品卷数'], 200)
        self.assertEqual(progress_summary(500, DEMO_ORDERS[1]['rows'])['completed'], 500)

    def test_empty_completed_excess_and_zero_target(self):
        self.assertEqual(progress_summary(800, ())['remaining'], 800)
        self.assertEqual(progress_summary(800, ())['ratio'], 0)
        rows = DEMO_ORDERS[0]['rows']
        self.assertEqual(progress_summary(650, rows)['ratio'], 1)
        excess = progress_summary(500, rows)
        self.assertEqual((excess['remaining'], excess['excess'], excess['ratio']), (0, 150, 1.3))
        self.assertIsNone(progress_summary(0, rows)['ratio'])
        self.assertIsNone(progress_summary(0, rows)['excess'])
        self.assertEqual(progress_summary(0, rows)['completed'], 650)
        for invalid in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                progress_summary(invalid, rows)


if __name__ == '__main__':
    unittest.main()
