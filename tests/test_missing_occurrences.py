import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'tools'))
from missing_occurrences import generate, occurrences, WEEKDAYS


class TestMissingOccurrences(unittest.TestCase):
    def test_full_series(self):
        first = dt.date(2026, 9, 29)
        until = dt.date(2027, 9, 29)
        all_dates = list(occurrences(first, until, WEEKDAYS['TU']))
        self.assertEqual(len(all_dates), 13)
        text, fixes = generate(first, until, WEEKDAYS['TU'], dt.time(13), 60,
                               'Europe/Madrid', 'Check Outlook recurring meeting')
        self.assertEqual([str(d) for d, _ in fixes], [
            '2026-10-27', '2026-11-24', '2027-01-26', '2027-02-23',
            '2027-04-27', '2027-05-25', '2027-07-27', '2027-09-28'])
        self.assertIn('DTSTART:20261027T120000Z', text)
        self.assertEqual(text.count('BEGIN:VEVENT'), 8)
        self.assertNotIn('20261229', text)
        self.assertIn('DTSTART:20270427T110000Z', text)
        self.assertIn('\r\n', text)

    def test_exclusion(self):
        _, fixes = generate(dt.date(2026, 9, 29), dt.date(2026, 11, 30),
                             WEEKDAYS['TU'], dt.time(13), 60, 'Europe/Madrid',
                             'Check Outlook', [dt.date(2026, 10, 27)])
        self.assertEqual([str(d) for d, _ in fixes], ['2026-11-24'])


if __name__ == '__main__':
    unittest.main()
