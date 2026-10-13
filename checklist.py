"""Pure schedule model and atomic, versioned record storage."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import copy

REGIONS = ['티르코네일', '던바튼', '콜헨', '이멘마하']
TASKS = {
    'runda': ('룬다', 1), 'settlement': ('주간 정산', 1),
    'gold': ('골드', 1), 'gems': ('보석', 1), 'raid': ('레이드', 1),
    'catalyst': ('촉매', 1), 'abyss': ('어비스', 3),
    'weekend_reward': ('주말 보상', 1), 'optional_dungeon': ('선택 던전', 1),
    'weekend_review': ('주말 미완료 확인', 1),
    'deep': ('심층 매우 어려움 · 공물 2개', 1), 'event': ('이벤트 확인', 1),
}
SCHEDULE = [
    [('이멘마하', 'runda'), ('던바튼', 'settlement'), ('티르코네일', 'gold')],
    [('던바튼', 'gems'), ('이멘마하', 'runda')],
    [('콜헨', 'raid'), ('콜헨', 'catalyst'), ('이멘마하', 'runda')],
    [('이멘마하', 'runda'), ('티르코네일', 'gold')],
    [('던바튼', 'gems'), ('이멘마하', 'runda')],
    [('콜헨', 'raid'), ('콜헨', 'catalyst'), ('이멘마하', 'abyss'), ('이멘마하', 'runda'), ('이멘마하', 'weekend_reward')],
    [('이멘마하', 'runda'), ('사용자 확인', 'optional_dungeon'), ('사용자 확인', 'weekend_review')],
]


def game_day(now=None):
    return ((now or datetime.now()) - timedelta(hours=6)).date()


def week_key(day):
    return (day - timedelta(days=day.weekday())).isoformat()


def cards(day, deep_region=''):
    result = []
    for region, task in SCHEDULE[day.weekday()]:
        if result and result[-1]['region'] == region:
            result[-1]['tasks'].append(task)
        else:
            result.append({'id': region, 'region': region, 'tasks': [task], 'notice': ''})
    matching = next((card for card in result if card['region'] == deep_region), None)
    if matching:
        matching['tasks'].append('deep')
    elif deep_region:
        result.append({'id': 'deep', 'region': deep_region, 'tasks': ['deep'],
                       'notice': '경유 순서 미확정 · 기본 동선 뒤에 표시'})
    else:
        result.append({'id': 'deep', 'region': '⚠ 심층 위치 미설정', 'tasks': ['deep'],
                       'notice': '상세 보기 상단에서 금주의 위치를 설정하세요.'})
    result.append({'id': 'event', 'region': '이벤트 · 위치 확인', 'tasks': ['event'],
                   'notice': '이벤트 위치는 직접 확인하세요.'})
    return result


class Store:
    def __init__(self, path=None):
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share')))
        self.path = Path(path) if path else base / 'MabiChecklist/state.json'
        self.original_path = self.path
        self.data = {'schema_version': 2, 'records': {}, 'settings': {}, 'deep_weeks': {}}
        self.error = ''
        self.writable = True
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding='utf-8'))
                raw = self.normalize(raw)
                self.validate(raw)
                self.data = raw
            except (OSError, ValueError, TypeError) as exc:
                # Unknown legacy data must not lock ordinary checklist use.
                # Keep it untouched and use a separate, stable recovery file.
                self.path = self.original_path.with_name(self.original_path.stem + '.recovered.json')
                self.error = '이전 기록 형식을 읽지 못해 별도 새 기록을 사용합니다. 체크와 설정은 가능합니다. 기존 파일은 그대로 보존합니다.'
                if self.path.exists():
                    try:
                        recovered = self.normalize(json.loads(self.path.read_text(encoding='utf-8')))
                        self.validate(recovered)
                        self.data = recovered
                    except (OSError, ValueError, TypeError) as recovery_error:
                        self.writable = False
                        self.error = f'복구 기록도 읽을 수 없습니다. 불러오기 또는 백업 후 새 시작이 필요합니다.\n{recovery_error}\n{self.path}'

    @staticmethod
    def normalize(raw):
        if not isinstance(raw, dict):
            raise ValueError('기록은 JSON 객체여야 합니다.')
        if raw.get('schema_version') == 2:
            return raw
        # Supported earlier checklist format. Unknown layouts stay protected.
        if raw.get('schema_version') not in (None, 1) or not all(isinstance(raw.get(k), dict) for k in ('records', 'settings', 'deep_weeks')):
            raise ValueError('지원하지 않는 저장 형식입니다. 기록 불러오기 또는 백업 후 새 시작을 사용하세요.')
        result = copy.deepcopy(raw)
        aliases = {name: task for task, (name, _) in TASKS.items()}
        aliases['심층 매우 어려움 (공물 2개)'] = 'deep'
        result['records'] = {}
        for day, record in raw['records'].items():
            if not isinstance(record, dict):
                raise ValueError('날짜별 기록 형식이 올바르지 않습니다.')
            result['records'][day] = {aliases.get(task, task): value for task, value in record.items()}
        result['schema_version'] = 2
        return result

    def load_file(self, path):
        raw = self.normalize(json.loads(Path(path).read_text(encoding='utf-8')))
        self.validate(raw)
        # A validated explicit import can replace an unreadable current file,
        # but save() backs that file up first.
        previous_writable = self.writable
        self.writable = True
        try:
            self.commit(raw)
        except (OSError, ValueError):
            self.writable = previous_writable
            raise
        self.error = ''

    def reset_with_backup(self):
        previous_writable = self.writable
        self.writable = True
        try:
            self.commit({'schema_version': 2, 'records': {}, 'settings': {}, 'deep_weeks': {}})
        except (OSError, ValueError):
            self.writable = previous_writable
            raise
        self.error = ''

    @staticmethod
    def validate(raw):
        if not isinstance(raw, dict) or raw.get('schema_version') != 2:
            raise ValueError('지원하지 않는 저장 형식입니다.')
        for key in ('records', 'settings', 'deep_weeks'):
            if not isinstance(raw.get(key), dict):
                raise ValueError(f'{key} 형식이 올바르지 않습니다.')
        for record in raw['records'].values():
            if not isinstance(record, dict):
                raise ValueError('날짜별 기록 형식이 올바르지 않습니다.')
            for task, value in record.items():
                if task in TASKS:
                    if TASKS[task][1] == 3:
                        if not isinstance(value, (bool, int)) or not 0 <= value <= 3:
                            raise ValueError('어비스 기록 범위가 올바르지 않습니다.')
                    elif not isinstance(value, bool):
                        raise ValueError('체크 기록은 참/거짓이어야 합니다.')
        if any(not isinstance(value, str) for value in raw['deep_weeks'].values()):
            raise ValueError('심층 위치는 문자열이어야 합니다.')
        settings = raw['settings']
        opacity = settings.get('opacity', 0.95)
        if isinstance(opacity, bool) or not isinstance(opacity, (int, float)) or not 0.35 <= opacity <= 1:
            raise ValueError('투명도 범위가 올바르지 않습니다.')
        if not isinstance(settings.get('compact', False), bool):
            raise ValueError('보기 모드 형식이 올바르지 않습니다.')
        position = settings.get('position')
        if position is not None and (not isinstance(position, list) or len(position) != 2 or any(type(v) is not int for v in position)):
            raise ValueError('창 위치 형식이 올바르지 않습니다.')

    def value(self, day, task):
        value = self.data['records'].get(day.isoformat(), {}).get(task, 0)
        if task == 'abyss':
            return 3 if value is True else max(0, min(3, int(value or 0)))
        return bool(value)

    def deep(self, day):
        return self.data['deep_weeks'].get(week_key(day), '')

    def save(self):
        if not self.writable:
            raise OSError(self.error)
        self.validate(self.data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            if not self.path.with_suffix('.json.original.bak').exists():
                shutil.copy2(self.path, self.path.with_suffix('.json.original.bak'))
            shutil.copy2(self.path, self.path.with_suffix('.json.bak'))
        temporary = self.path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def commit(self, data):
        previous = self.data
        self.data = data
        try:
            self.save()
        except (OSError, ValueError):
            self.data = previous
            raise

    def progress(self, day):
        tasks = [task for card in cards(day, self.deep(day)) for task in card['tasks']]
        total = sum(TASKS[task][1] for task in tasks)
        done = sum(self.value(day, task) if task == 'abyss' else int(self.value(day, task)) for task in tasks)
        return done, total
