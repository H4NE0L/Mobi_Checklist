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
                self.assertTrue(store.writable)
                self.assertNotEqual(store.path, path)
                store.save()
                self.assertEqual(path.read_text(), raw)
                self.assertTrue(store.path.exists())

    def test_failed_write_rolls_back_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'state.json')
            data = copy.deepcopy(store.data)
            data['settings']['compact'] = True
            with patch.object(Path, 'write_text', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    store.commit(data)
            self.assertNotIn('compact', store.data['settings'])

class RecoveryTests(unittest.TestCase):
    def test_legacy_named_records_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            legacy = {'schema_version': 1, 'records': {'2026-10-17': {'어비스': True, '룬다': True, '심층 매우 어려움 (공물 2개)': True}}, 'settings': {}, 'deep_weeks': {'2026-10-12': '이멘마하'}}
            original = json.dumps(legacy, ensure_ascii=False)
            path.write_text(original)
            store = Store(path)
            self.assertTrue(store.writable)
            self.assertEqual(store.value(date(2026, 10, 17), 'abyss'), 3)
            self.assertTrue(store.value(date(2026, 10, 17), 'deep'))
            store.save()
            store.save()
            self.assertEqual(path.with_suffix('.json.original.bak').read_text(), original)

    def test_recover_unknown_file_without_losing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{"unknown": true}')
            store = Store(path)
            store.reset_with_backup()
            self.assertTrue(store.writable)
            self.assertEqual(path.read_text(), '{"unknown": true}')
            self.assertNotEqual(store.path, path)
            self.assertTrue(Store(path).writable)

    def test_explicit_import_and_invalid_import_keeps_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'state.json')
            source = Path(directory) / 'import.json'
            data = copy.deepcopy(store.data)
            data['records']['2026-10-14'] = {'raid': True}
            source.write_text(json.dumps(data))
            store.load_file(source)
            self.assertTrue(Store(store.path).value(date(2026, 10, 14), 'raid'))
            source.write_text('{}')
            with self.assertRaises(ValueError):
                store.load_file(source)
            self.assertTrue(Store(store.path).value(date(2026, 10, 14), 'raid'))

    def test_unknown_original_uses_same_recovery_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{"old_unknown_format": true}')
            store = Store(path)
            data = copy.deepcopy(store.data)
            data['records']['2026-10-14'] = {'raid': True}
            data['deep_weeks']['2026-10-12'] = '던바튼'
            store.commit(data)
            reopened = Store(path)
            self.assertTrue(reopened.value(date(2026, 10, 14), 'raid'))
            self.assertEqual(reopened.deep(date(2026, 10, 14)), '던바튼')
            self.assertEqual(path.read_text(), '{"old_unknown_format": true}')

    def test_corrupt_recovery_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{}')
            recovery = Path(directory) / 'state.recovered.json'
            recovery.write_text('broken recovery')
            store = Store(path)
            self.assertFalse(store.writable)
            with self.assertRaises(OSError):
                store.save()
            self.assertEqual(recovery.read_text(), 'broken recovery')

class NewRoutineTests(unittest.TestCase):
    def test_manual_silver_spend_keeps_next_day_below_cap(self):
        from checklist import silver_plan
        for balance in range(101):
            plan = silver_plan(balance)
            self.assertLess(plan['next_balance'], 100)
            self.assertLessEqual(plan['spend'], balance)
            self.assertEqual(plan['spend'], plan['double_runs'] * 20 + plan['single_runs'] * 10)
        self.assertEqual(silver_plan(90)['spend'], 40)
        self.assertEqual(silver_plan(100)['spend'], 50)
        self.assertEqual(silver_plan(0)['spend'], 0)

    def test_outdoor_deep_merges_at_explicit_arrival(self):
        result = cards(date(2026, 10, 14), '센마이 평원', '이멘마하')
        matching = [card for card in result if 'deep' in card['tasks']]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]['region'], '이멘마하')
        self.assertEqual(matching[0]['deep_location'], '센마이 평원')
        self.assertIn('콜헨 마을 포탈 → 이멘마하', matching[0]['detail'])

    def test_new_town_stop_before_unknown_sunday_content(self):
        result = cards(date(2026, 10, 18), '반호르')
        self.assertEqual([card['region'] for card in result[:3]], ['이멘마하', '반호르', '사용자 확인'])
        self.assertEqual(result[1]['brief'], '포탈 → 반호르')

    def test_weekly_arrival_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'state.json')
            data = copy.deepcopy(store.data)
            data['deep_weeks']['2026-10-12'] = '창백한 산'
            data['settings']['deep_arrivals'] = {'2026-10-12': '이멘마하'}
            store.commit(data)
            reopened = Store(store.path)
            self.assertEqual(reopened.arrival(date(2026, 10, 18)), '이멘마하')
            self.assertEqual(reopened.arrival(date(2026, 10, 19)), '')
