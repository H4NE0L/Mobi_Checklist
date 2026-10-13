# 모비체크 · MobiChecklist v0.1.0

마비노기 모바일 창 모드에서 사용하는 수동 Windows 숙제 체크리스트입니다. 게임 데이터를 읽거나 입력을 자동화하지 않습니다.

새 설계로 구현한 첫 테스트 버전입니다. 이전 구현의 버전 번호를 이어받지 않습니다.

## 실행

Windows / Python 3.10 이상:

```powershell
py -m pip install -r requirements.txt
py main.py
```

헤더의 빈 공간을 드래그해 이동합니다. `≡`를 누르면 상세 보기와 간략 보기 사이를 전환합니다. `◐`는 투명도, `×`는 종료입니다.

- 상세 보기: 카드 위에 **금주의 매우 어려움 심층던전 위치**를 설정합니다. 목록에 없는 위치도 직접 입력한 뒤 Enter로 적용할 수 있습니다. 이동 안내, 진행률, 주간 기록 버튼도 표시합니다.
- 간략 보기: 방문 번호·지역명·체크 항목만 남습니다. 체크 항목은 접히지 않습니다. 첫 미완료 카드를 `다음`으로 표시합니다.
- 내용에 맞춰 창 높이를 줄이고, 화면 높이를 넘을 때는 카드 영역만 스크롤합니다.
- 주간 기록에서 날짜를 선택해 수정할 수 있습니다. 과거 날짜에서는 두 보기 모두 오늘 복귀 버튼을 표시합니다.
- 토요일 어비스는 0~3 카운터로 기록합니다.

요일별 숙제 및 상세 동작은 [설계 문서](docs/DESIGN.md)에 있습니다.

## 심층 위치와 동선

같은 방문 지역의 심층 숙제는 카드에 통합합니다. 실제 지도 지역 순서가 확인되지 않은 추가 지역은 기본 동선 뒤에 표시하고 `경유 순서 미확정`을 안내합니다. 최단 경로 계산이 아닙니다. 지역 목록은 예시이며 직접 입력할 수 있습니다. 미설정 경고는 간략 보기에서도 유지됩니다.

## 기록

`%LOCALAPPDATA%\MabiChecklist\state.json`에 자동 저장하고 직전 파일을 `state.json.bak`으로 보관합니다. 로컬 시각 오전 6시를 게임 날짜 경계로 사용합니다. 한국 게임 날짜에 맞추려면 Windows 시간대를 한국으로 설정하세요.

이번 앱은 새 버전의 저장 형식을 사용합니다. 알려지지 않은 기존 형식이나 깨진 파일은 덮어쓰지 않고 저장을 중지합니다. 실제 과거 버전 데이터 호환은 검증하지 않았습니다. 저장 실패 시 체크 변경을 되돌리고 오류를 표시합니다.

## EXE 빌드

Windows에서 실행하세요:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name MobiChecklist main.py
```

결과: `dist/MobiChecklist.exe`. 실제 Windows 게임 위 표시, DPI·다중 모니터, EXE 빌드는 별도 검증이 필요합니다. 독점 전체화면에서는 표시되지 않을 수 있습니다.

## 개발 검증

```powershell
py -m unittest discover -s tests -v
```

Linux 클라우드:

```sh
QT_QPA_PLATFORM=offscreen /workspace/.venvs/mobichecklist/bin/python -m unittest discover -s tests -v
```

테스트는 임시 경로에 저장하며 실제 체크 기록을 변경하지 않습니다. 현재 로직 및 Qt 테스트 10개가 통과했습니다. 헤드리스 Qt 검증은 Windows 게임 위 동작 검증을 대신하지 않습니다.
