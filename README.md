# 모비체크 · MobiChecklist v0.1.0

마비노기 모바일 창 모드 위에 띄우는 **수동 자원 소모·숙제 체크리스트**입니다. 게임 데이터 접근이나 자동 조작은 하지 않습니다.

## Windows 실행

Python 3.10 이상:

```powershell
py -m pip install -r requirements.txt
py main.py
```

## 사용

1. 상단에서 금주의 **매우 어려움 심층 위치**를 선택합니다. 직접 입력 후 **적용**도 가능합니다.
2. 야외 위치라면 **접근 마을**을 지정합니다. 기존 방문 마을이면 심층 카드를 통합합니다.
3. 번호·화살표를 따라 이동하고 체크합니다. 룬다는 고정 횟수가 아니라 **다음 날 은동전 상한을 대비해 필요한 만큼 소모**하는 항목입니다.
4. 심층 매우 어려움에서 공물 2개를 소모하고 요일별 아르바이트·콘텐츠와 이벤트를 확인합니다.

모든 마을 간 포탈 이동이 가능하다는 사용자 제공 정보를 기준으로 안내합니다. 실제 최단 경로·이동 비용은 계산하지 않습니다. 야외 지역의 접근 마을은 직접 선택하며 위치 미설정은 경고로 표시합니다.

`≡`로 간략 보기, `펼치기`로 상세 보기를 전환합니다. 간략 보기에도 체크·심층 위치·짧은 이동 안내를 유지합니다. 헤더의 빈 부분을 드래그해 이동하고 `◐`로 버튼 위 슬라이더를 엽니다. `×`로 종료합니다.

상세 보기의 **자원 안내**에서는 직접 입력한 은동전 보유량으로 소모량과 더블루팅·일반 횟수를 계산합니다. 은동전은 하루 48개 갱신·상한 100개, 공물은 하루 2개 갱신·상한 10개를 전제로 합니다. 게임 보유량을 자동 추적하거나 자동 체크하지 않습니다.

**주간 기록**에서 날짜를 선택해 수정합니다. **백업**으로 JSON을 내보내고 **불러오기**로 지원하는 기록을 복원합니다. 체크 행의 빈 부분도 클릭할 수 있고 완료 시 ✓를 표시합니다.

## 저장

`%LOCALAPPDATA%\MabiChecklist\state.json`. 이전 알 수 없는 파일은 그대로 보존하고 `state.recovered.json`을 사용합니다. 지원하는 이전 테스트 형식만 변환하며 모든 과거 버전 호환을 보장하지 않습니다. 직전 저장과 최초 원본은 백업합니다.

로컬 시각 오전 6시가 날짜 경계입니다. 한국 게임 날짜에 맞추려면 Windows 시간대를 한국으로 설정하세요. 저장 실패 시 체크 변경을 되돌리고 오류를 표시합니다.

## EXE (Windows에서 빌드)

```powershell
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --onefile --windowed --name MobiChecklist main.py
```

결과: `dist/MobiChecklist.exe`. 실제 Windows 오버레이·DPI·다중 모니터·EXE 빌드는 아직 검증하지 않았습니다. 독점 전체화면에서는 표시되지 않을 수 있습니다.

## 개발 검증

Windows:

```powershell
py -m unittest discover -s tests -v
```

Linux 클라우드:

```sh
QT_QPA_PLATFORM=offscreen /workspace/.venvs/mobichecklist/bin/python -m unittest discover -s tests -v
```

현재 **27개 테스트 통과**. [새 설계](docs/DESIGN.md)에서 이동·자원 계산 정책을 확인하세요.
