"""Manual Windows overlay; presentation changes never change checklist data."""
import copy
import sys
from datetime import timedelta
from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QComboBox, QScrollArea, QFrame, QDialog, QSlider,
)
from checklist import Store, TASKS, REGIONS, cards, game_day, week_key
from version import APP_TITLE, __version__

STYLE = '''
QWidget { background: #20242d; color: #eff2f7; font-family: "Segoe UI", "Malgun Gothic"; font-size: 13px; }
QWidget#header { background: #171b23; border-radius: 8px; }
QPushButton { background: #303747; border: 1px solid #414b60; border-radius: 5px; padding: 6px; }
QPushButton:hover { background: #424e66; }
QPushButton:disabled { color: #7e8796; }
QLabel#muted { color: #a7b2c7; }
QLabel#title { font-size: 15px; font-weight: bold; }
QFrame#card { background: #282e3a; border: 1px solid #414b60; border-radius: 8px; }
QFrame#card[active="true"] { border: 2px solid #edc46b; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QLabel#number { background: #424e66; border-radius: 12px; font-weight: bold; }
QCheckBox { spacing: 8px; padding: 5px 0; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #8e9bb2; border-radius: 4px; background: #171b23; }
QCheckBox::indicator:checked { background: #edc46b; border: 3px solid #9a7936; }
QComboBox { background: #303747; border: 1px solid #414b60; border-radius: 5px; padding: 6px; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 10px; background: #20242d; }
QScrollBar::handle:vertical { background: #56647e; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
'''


def label(text='', muted=False):
    result = QLabel(text)
    result.setWordWrap(True)
    if muted:
        result.setObjectName('muted')
    return result


class Header(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('header')
        self.origin = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, event):
        if self.origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self.origin)

    def mouseReleaseEvent(self, event):
        self.origin = None
        self.window().clamp_position()
        self.window().save_position()


class TaskCard(QFrame):
    changed = Signal(str, object)

    def __init__(self, number, card, writable):
        super().__init__()
        self.setObjectName('card')
        self.card = card
        self.controls = {}
        self.values = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        title = QHBoxLayout()
        number_label = QLabel(str(number))
        number_label.setObjectName('number')
        number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        number_label.setFixedSize(26, 26)
        title.addWidget(number_label)
        title.addWidget(label(card['region']), 1)
        self.next_label = QLabel('다음')
        self.next_label.setStyleSheet('color: #edc46b; font-weight: bold;')
        title.addWidget(self.next_label)
        layout.addLayout(title)
        self.notice = label(card['notice'], True)
        layout.addWidget(self.notice)
        for task in card['tasks']:
            if task == 'abyss':
                row = QHBoxLayout()
                row.addWidget(QLabel('어비스'))
                row.addStretch()
                minus, plus = QPushButton('−'), QPushButton('+')
                count = QLabel('0/3')
                count.setAlignment(Qt.AlignmentFlag.AlignCenter)
                count.setMinimumWidth(36)
                for button in (minus, plus):
                    button.setFixedWidth(32)
                    button.setEnabled(writable)
                minus.clicked.connect(lambda: self.changed.emit('abyss', max(0, self.values.get('abyss', 0) - 1)))
                plus.clicked.connect(lambda: self.changed.emit('abyss', min(3, self.values.get('abyss', 0) + 1)))
                row.addWidget(minus)
                row.addWidget(count)
                row.addWidget(plus)
                layout.addLayout(row)
                self.controls[task] = (count, minus, plus)
            else:
                box = QCheckBox(TASKS[task][0])
                box.setEnabled(writable)
                box.toggled.connect(lambda value, task_id=task: self.changed.emit(task_id, value))
                layout.addWidget(box)
                self.controls[task] = box
        self.writable = writable

    def sync(self, store, day, active, compact):
        self.next_label.setVisible(active)
        self.setProperty('active', active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.notice.setVisible(bool(self.card['notice']) and not compact)
        for task, control in self.controls.items():
            value = store.value(day, task)
            self.values[task] = value
            if task == 'abyss':
                count, minus, plus = control
                count.setText(f'{value}/3')
                minus.setEnabled(self.writable and value > 0)
                plus.setEnabled(self.writable and value < 3)
            else:
                control.blockSignals(True)
                control.setChecked(value)
                control.blockSignals(False)


class Checklist(QWidget):
    def __init__(self, store=None):
        super().__init__()
        self.store = store or Store()
        self.today = game_day()
        self.day = self.today
        self.compact = self.store.data['settings'].get('compact', False)
        self.card_widgets = []
        self.guides = []
        self.resize_pending = False
        self.setWindowTitle(f'{APP_TITLE} · MobiChecklist')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(380)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)
        self.header = Header(self)
        header_layout = QHBoxLayout(self.header)
        self.title = QLabel(APP_TITLE)
        self.title.setObjectName('title')
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        header_layout.addWidget(self.title, 1)
        self.mode_button = QPushButton('≡')
        self.mode_button.clicked.connect(self.toggle_compact)
        header_layout.addWidget(self.mode_button)
        opacity = QPushButton('◐')
        opacity.setToolTip('투명도')
        opacity.clicked.connect(self.opacity_dialog)
        header_layout.addWidget(opacity)
        close = QPushButton('×')
        close.setToolTip('종료')
        close.clicked.connect(self.close)
        header_layout.addWidget(close)
        for button in (self.mode_button, opacity, close):
            button.setFixedWidth(32)
        self.layout.addWidget(self.header)
        self.date_label = label()
        self.layout.addWidget(self.date_label)
        self.settings = QWidget()
        settings_layout = QVBoxLayout(self.settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(label('금주의 매우 어려움 심층던전 위치'))
        self.region = QComboBox()
        self.region.setEditable(True)
        self.region.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.region.addItems(['미설정'] + REGIONS)
        self.region.setToolTip('목록은 예시 지역입니다. 실제 심층 위치를 직접 입력할 수 있습니다.')
        self.region.activated.connect(self.change_region)
        self.region.lineEdit().editingFinished.connect(self.change_region)
        self.region.setEnabled(self.store.writable)
        settings_layout.addWidget(self.region)
        self.layout.addWidget(self.settings)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.layout.addWidget(self.scroll, 1)
        self.footer = QPushButton('주간 기록')
        self.footer.clicked.connect(self.history_dialog)
        self.layout.addWidget(self.footer)
        self.current = QPushButton('과거 기록 · 오늘로 돌아가기')
        self.current.clicked.connect(self.return_today)
        self.layout.addWidget(self.current)
        self.error_label = label(self.store.error)
        self.error_label.setStyleSheet('color: #ffb3a8;')
        self.error_label.setVisible(bool(self.store.error))
        self.layout.addWidget(self.error_label)
        self.setWindowOpacity(self.store.data['settings'].get('opacity', 0.95))
        position = self.store.data['settings'].get('position')
        if position:
            self.move(*position)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_date)
        self.timer.start(10000)
        self.rebuild_cards()
        self.screenChanged_connection = False

    def commit(self, mutate):
        if not self.store.writable:
            return False
        data = copy.deepcopy(self.store.data)
        mutate(data)
        try:
            self.store.commit(data)
            self.error_label.clear()
            self.error_label.hide()
            return True
        except (OSError, ValueError) as exc:
            self.error_label.setText(f'저장 실패 · 변경이 저장되지 않았습니다.\n{exc}')
            self.error_label.show()
            self.schedule_resize()
            return False

    def rebuild_cards(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(8)
        self.card_widgets = []
        self.guides = []
        for number, card in enumerate(cards(self.day, self.store.deep(self.day)), 1):
            if 'raid' in card['tasks']:
                guide = label('레이드 퀵메뉴 → 대기방 입장 → 나가기 → 콜헨', True)
                layout.addWidget(guide)
                self.guides.append(guide)
            if 'abyss' in card['tasks']:
                guide = label('어비스 퀵메뉴: 실제 클리어 필요 → 이후 룬다', True)
                layout.addWidget(guide)
                self.guides.append(guide)
            widget = TaskCard(number, card, self.store.writable)
            widget.changed.connect(self.mark)
            layout.addWidget(widget)
            self.card_widgets.append(widget)
        layout.addStretch(1)
        previous = self.scroll.takeWidget()
        if previous:
            previous.deleteLater()
        self.scroll.setWidget(content)
        self.region.blockSignals(True)
        self.region.setCurrentText(self.store.deep(self.day) or '미설정')
        self.region.blockSignals(False)
        self.sync()

    def sync(self):
        done, total = self.store.progress(self.day)
        day_text = f'{self.day:%m/%d} {"월화수목금토일"[self.day.weekday()]}'
        past = self.day != self.today
        self.title.setText(f'모비체크 · {day_text}' if self.compact else APP_TITLE)
        self.title.setToolTip(f'MobiChecklist v{__version__} · {self.day:%Y-%m-%d}')
        self.date_label.setText(f'{self.day:%Y-%m-%d} {"월화수목금토일"[self.day.weekday()]}요일 · {done}/{total} 완료')
        self.date_label.setVisible(not self.compact)
        self.settings.setVisible(not self.compact)
        self.footer.setVisible(not self.compact)
        self.current.setVisible(past)
        self.mode_button.setToolTip('상세 보기로 펼치기' if self.compact else '체크 카드만 보기로 접기')
        first = True
        for widget in self.card_widgets:
            incomplete = any(self.store.value(self.day, task) != (3 if task == 'abyss' else True) for task in widget.card['tasks'])
            active = first and incomplete
            if active:
                first = False
            widget.sync(self.store, self.day, active, self.compact)
        for guide in self.guides:
            guide.setVisible(not self.compact)
        self.schedule_resize()

    def schedule_resize(self):
        if not self.resize_pending:
            self.resize_pending = True
            QTimer.singleShot(0, self.resize_content)

    def resize_content(self):
        self.resize_pending = False
        content = self.scroll.widget()
        if not content:
            return
        content.layout().invalidate()
        content.layout().activate()
        body_layout = content.layout()
        margins = body_layout.contentsMargins()
        width = max(1, self.scroll.viewport().width() - margins.left() - margins.right())
        visible_items = [body_layout.itemAt(i).widget() for i in range(body_layout.count())]
        visible_items = [item for item in visible_items if item and not item.isHidden()]
        needed = margins.top() + margins.bottom()
        needed += sum(item.heightForWidth(width) if item.hasHeightForWidth() else item.sizeHint().height() for item in visible_items)
        needed += body_layout.spacing() * max(0, len(visible_items) - 1)
        content.setMinimumHeight(needed)
        overhead = self.layout.contentsMargins().top() + self.layout.contentsMargins().bottom()
        visible = [self.header, self.date_label, self.settings, self.footer, self.current, self.error_label]
        visible = [widget for widget in visible if not widget.isHidden()]
        overhead += sum(widget.sizeHint().height() for widget in visible)
        overhead += self.layout.spacing() * len(visible)
        maximum = max(180, self.screen().availableGeometry().height() - 24)
        height = min(needed + overhead + 2, maximum)
        self.setFixedHeight(height)
        self.clamp_position()

    def clamp_position(self):
        area = self.screen().availableGeometry()
        x = min(max(self.x(), area.left()), max(area.left(), area.right() - self.width() + 1))
        y = min(max(self.y(), area.top()), max(area.top(), area.bottom() - self.height() + 1))
        self.move(x, y)

    def save_position(self):
        self.commit(lambda data: data['settings'].update(position=[self.x(), self.y()]))

    def mark(self, task, value):
        self.commit(lambda data: data['records'].setdefault(self.day.isoformat(), {}).update({task: value}))
        self.sync()

    def change_region(self, *args):
        region = self.region.currentText().strip()
        if region == '미설정':
            region = ''
        if region == self.store.deep(self.day):
            return
        self.commit(lambda data: data['deep_weeks'].update({week_key(self.day): region}))
        self.rebuild_cards()

    def toggle_compact(self):
        top = self.scroll.verticalScrollBar().value()
        anchor = next((widget for widget in self.card_widgets if widget.y() + widget.height() > top), None)
        anchor_id = anchor.card['id'] if anchor else None
        self.compact = not self.compact
        self.commit(lambda data: data['settings'].update(compact=self.compact))
        self.sync()
        def restore_anchor():
            widget = next((widget for widget in self.card_widgets if widget.card['id'] == anchor_id), None)
            if widget:
                self.scroll.verticalScrollBar().setValue(widget.y())
        QTimer.singleShot(0, restore_anchor)

    def opacity_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('투명도')
        layout = QVBoxLayout(dialog)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(35, 100)
        slider.setValue(round(self.windowOpacity() * 100))
        value_label = QLabel(f'{slider.value()}%')
        def change(value):
            self.setWindowOpacity(value / 100)
            value_label.setText(f'{value}%')
        slider.valueChanged.connect(change)
        layout.addWidget(value_label)
        layout.addWidget(slider)
        dialog.exec()
        self.commit(lambda data: data['settings'].update(opacity=slider.value() / 100))

    def history_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('주간 기록')
        layout = QVBoxLayout(dialog)
        monday = self.day - timedelta(days=self.day.weekday())
        title = label()
        layout.addWidget(title)
        rows = QVBoxLayout()
        layout.addLayout(rows)
        def select(day):
            self.day = day
            dialog.accept()
            self.rebuild_cards()
        def render():
            title.setText(f'{monday:%Y-%m-%d} 주간 · 날짜를 눌러 수정')
            while rows.count():
                rows.takeAt(0).widget().deleteLater()
            for offset in range(7):
                day = monday + timedelta(days=offset)
                done, total = self.store.progress(day)
                button = QPushButton(f'{day:%m/%d} {"월화수목금토일"[offset]} · {done}/{total}')
                button.clicked.connect(lambda checked=False, chosen=day: select(chosen))
                rows.addWidget(button)
        def move(delta):
            nonlocal monday
            monday += timedelta(days=delta)
            render()
        navigation = QHBoxLayout()
        for text, delta in [('이전 주', -7), ('다음 주', 7)]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, amount=delta: move(amount))
            navigation.addWidget(button)
        layout.addLayout(navigation)
        render()
        dialog.exec()

    def return_today(self):
        self.today = game_day()
        self.day = self.today
        self.rebuild_cards()

    def check_date(self):
        new = game_day()
        if new != self.today:
            if self.day == self.today:
                self.day = new
            self.today = new
            self.rebuild_cards()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.screenChanged_connection:
            self.windowHandle().screenChanged.connect(lambda screen: self.schedule_resize())
            self.screenChanged_connection = True
        self.schedule_resize()

    def event(self, event):
        if event.type() == QEvent.Type.ScreenChangeInternal and hasattr(self, 'resize_pending'):
            self.schedule_resize()
        return super().event(event)

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
        QApplication.instance().quit()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Checklist()
    window.show()
    sys.exit(app.exec())
