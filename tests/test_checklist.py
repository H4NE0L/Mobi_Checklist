import copy
import json
from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from checklist import Store, cards, game_day, week_key, SCHEDULE


class ModelTests(unittest.TestCase):
    def test_six_am_and_week_boundary(self):
        self.assertEqual(game_day(datetime(2026, 10, 12, 5, 59)), date(2026, 10, 11))
        self.assertEqual(game_day(datetime(2026, 10, 12, 6)), date(2026, 10, 12))
        self.assertEqual(week_key(date(2026, 10, 18)), '2026-10-12')

    def test_all_days_preserve_base_order(self):
        for weekday in range(7):
            for region in ['', '던바튼', '이멘마하', '미확인 지역']:
                result = cards(date(2026, 10, 12 + weekday), region)
                tasks = [task for card in result for task in card['tasks']]
                self.assertEqual([task for task in tasks if task not in ('deep', 'event')], [task for _, task in SCHEDULE[weekday]])
                self.assertEqual(tasks.count('deep'), 1)
                self.assertEqual(tasks.count('event'), 1)
                if region:
                    self.assertEqual(sum(card['region'] == region for card in result), 1)
                else:
                    self.assertIn('⚠', result[-2]['region'])

    def test_persist_past_record_and_abyss(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            store = Store(path)
            day = date(2026, 10, 17)
            data = copy.deepcopy(store.data)
            data['records'][day.isoformat()] = {'abyss': True}
            store.commit(data)
            self.assertEqual(Store(path).value(day, 'abyss'), 3)
            data['records'][day.isoformat()]['abyss'] = 2
            store.commit(data)
            self.assertEqual(Store(path).progress(day), (2, 9))
            self.assertTrue(path.with_suffix('.json.bak').exists())

    def test_unknown_or_invalid_file_protected(self):
        for raw in ['broken json', '{}', '{"schema_version":2,"records":{},"settings":{"opacity":"bad"},"deep_weeks":{}}']:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'state.json'
                path.write_text(raw)
                store = Store(path)
                self.assertFalse(store.writable)
                with self.assertRaises(OSError):
                    store.save()
                self.assertEqual(path.read_text(), raw)

    def test_failed_write_rolls_back_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'state.json')
            data = copy.deepcopy(store.data)
            data['settings']['compact'] = True
            with patch.object(Path, 'write_text', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    store.commit(data)
            self.assertNotIn('compact', store.data['settings'])
