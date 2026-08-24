# Arcade Game Manager

아케이드 게임을 portable 라이브러리로 관리하고 실행하는 Python GUI입니다. spice2x 게임은 하나의 공용 런타임으로 통합하고, 그 밖의 게임은 폴더 내부 실행 파일을 직접 등록할 수 있습니다.

## 1차 목표

- 각 게임 폴더에서 `spice.exe`, `spice64.exe`, `spicecfg.exe` 제거
- 중앙의 spice2x 런타임만 사용
- 모든 경로를 실행 파일 기준 상대경로로 저장하여 폴더 전체 이동 지원
- 게임별 작업 폴더, 모듈 경로, 추가 인자를 manifest로 관리
- 공용 `spicetools.xml`을 모든 실행과 Configurator에 동일하게 전달
- 게임 목록과 썸네일을 GUI에서 표시
- 기존 BAT가 필요하면 GUI와 같은 실행 코어를 호출하는 얇은 바로가기만 생성
- 기존 BAT의 다른 내용은 유지하고 spice 실행 파일 경로만 중앙 런타임 상대경로로 변환
- 게임 폴더의 DLL을 탐색해 게임 계열과 x86/x64를 제안
- 폴더명에서 게임명과 버전의 초기값을 추정하고 GUI에서 편집
- 일반 아케이드 게임의 EXE와 작업 폴더를 게임 폴더 기준 상대경로로 저장
- 동일한 폴더를 여러 실행 프로필로 중복 등록하여 모듈·인자별로 독립 실행
- EXE 아이콘을 자동 썸네일로 사용하고 투명 아트워크에는 확대·블러 배경 합성
- 썸네일 모드와 리스트 모드를 전환하고 선택한 모드를 저장

## 실행

Python 3.12 기준으로 작성되었습니다.

```powershell
python -m pip install -r requirements.txt
.\run.bat
```

GUI의 게임 등록 정보는 `data/games/*.json`에 상대경로로 저장됩니다.

`게임 추가`에서 실행 방식을 선택합니다.

- `spice2x 공용 런타임`: DLL 탐색, 게임 계열 제안, 공용 `spicetools.xml` 사용
- `일반 실행 파일`: 게임 폴더 내부의 EXE와 작업 폴더를 직접 지정

같은 폴더에서 다른 모듈이나 인자를 사용해야 하는 경우 항목을 선택하고 `복제`한 뒤 필요한 값만 변경합니다.

구체적인 구조와 실행 규칙은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

예시 설정:

- [examples/settings.json](examples/settings.json)
- [examples/games/iidx-example.json](examples/games/iidx-example.json)

## 테스트

```powershell
python -m unittest discover -s tests -v
```

## Windows EXE 빌드

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name ArcadeGameManager main.py
```

생성된 `dist/ArcadeGameManager.exe`를 `.arcade-game-manager-root`와 같은 폴더에 놓으면 해당 위치를 portable 루트로 사용합니다.

> 이 저장소에는 게임 데이터나 spice2x 바이너리를 포함하지 않습니다. 실제 배포 폴더에서는 런타임과 정당하게 보유한 게임 데이터를 상대경로로 배치합니다.
