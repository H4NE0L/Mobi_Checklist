"""Run with QT_QPA_PLATFORM=offscreen on headless Linux."""
import copy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QCheckBox
from checklist import Store
from main import Checklist
from version import APP_TITLE, __version__

class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.window = Checklist(Store(Path(self.directory.name) / 'state.json'))
        self.window.show()
        self.flush()

    def flush(self):
        for _ in range(3):
            self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.flush()
        self.directory.cleanup()

    def test_release_version_display(self):
        self.assertEqual(__version__, '0.1.0')
        self.assertIn(APP_TITLE, self.window.windowTitle())
        self.assertEqual(self.window.title.text(), APP_TITLE)
        self.window.toggle_compact()
        self.flush()
        self.assertIn('v0.1.0', self.window.title.toolTip())

    def test_twenty_switches_each_weekday(self):
        window = self.window
        for weekday in range(7):
            window.day = date(2026, 10, 12 + weekday)
            window.rebuild_cards()
            self.flush()
            widgets = list(window.card_widgets)
            before = copy.deepcopy(window.store.data['records'])
            full_height = window.height()
            for _ in range(20):
                window.toggle_compact()
                self.flush()
                self.assertEqual(window.card_widgets, widgets)
                self.assertEqual(window.store.data['records'], before)
                for box in window.scroll.widget().findChildren(QCheckBox):
                    self.assertTrue(box.isVisible())
                self.assertEqual(window.settings.isVisible(), not window.compact)
                if window.compact:
                    self.assertLess(window.height(), full_height)
            self.assertLessEqual(window.height(), window.screen().availableGeometry().height())
            self.assertEqual(window.height(), full_height)

    def test_location_above_cards_and_shared_region(self):
        window = self.window
        window.day = date(2026, 10, 14)
        window.rebuild_cards()
        window.region.setCurrentText('이멘마하')
        window.change_region()
        self.flush()
        self.assertLess(window.settings.geometry().bottom(), window.scroll.geometry().top())
        matching = [card for card in window.card_widgets if card.card['region'] == '이멘마하']
        self.assertEqual(len(matching), 1)
        self.assertIn('deep', matching[0].controls)
        self.assertEqual(Store(window.store.path).deep(window.day), '이멘마하')

    def test_check_updates_without_recreating_cards(self):
        window = self.window
        window.day = date(2026, 10, 17)
        window.rebuild_cards()
        widgets = list(window.card_widgets)
        window.mark('raid', True)
        window.mark('catalyst', True)
        self.assertFalse(widgets[0].next_label.isVisible())
        self.assertTrue(widgets[1].next_label.isVisible())
        for _ in range(4):
            control = widgets[1].controls['abyss']
            control[2].click()
        self.assertEqual(window.store.value(window.day, 'abyss'), 3)
        self.assertFalse(control[2].isEnabled())
        self.assertEqual(window.card_widgets, widgets)
        self.assertEqual(Store(window.store.path).value(window.day, 'raid'), True)

    def test_write_error_reverts_checkbox(self):
        window = self.window
        box = window.card_widgets[0].controls['runda'] if 'runda' in window.card_widgets[0].controls else next(c for c in window.card_widgets[0].controls.values() if isinstance(c, QCheckBox))
        with patch.object(window.store, 'save', side_effect=OSError('disk full')):
            box.click()
        self.assertFalse(box.isChecked())
        self.assertTrue(window.error_label.isVisible())

    def test_date_rollover_preserves_historical_selection(self):
        window = self.window
        window.today = date(2026, 10, 14)
        window.day = date(2026, 10, 12)
        with patch('main.game_day', return_value=date(2026, 10, 15)):
            window.check_date()
        self.assertEqual(window.day, date(2026, 10, 12))
        window.day = window.today
        with patch('main.game_day', return_value=date(2026, 10, 16)):
            window.check_date()
        self.assertEqual(window.day, date(2026, 10, 16))
        window.close()
        self.assertFalse(window.timer.isActive())
