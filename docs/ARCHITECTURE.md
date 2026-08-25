# 아키텍처 초안

## 결론

Windows용 `Python + tkinter GUI + 공용 실행 코어` 구조를 사용합니다. 게임 실행은 GUI가 담당하며, 게임별 실행 정보는 JSON manifest로 관리합니다.

1차 버전에서 중요한 것은 UI보다 중앙 런타임 실행의 안정성입니다.

## 배포 후 디렉터리

```text
ArcadeGameManager/
├─ .arcade-game-manager-root         # portable 루트 표식
├─ main.py
├─ run.bat                           # GUI 실행
├─ requirements.txt
├─ bsm/                              # 실행 코어와 tkinter GUI
├─ tests/
├─ games/                            # 실제 게임 또는 게임 폴더로 이어지는 구조
│  ├─ iidx-32/
│  │  └─ contents/
│  └─ sdvx-6/
│     └─ contents/
├─ spice2x/                          # 모든 게임이 공유하는 단일 런타임
│  ├─ spice.exe
│  ├─ spice64.exe
│  ├─ spicecfg.exe
│  ├─ spicetools.xml                # 현재의 공용 설정 파일
│  └─ spicetools_patch_manager.json # 선택적인 공용 패치 설정
├─ data/
│  ├─ settings.json
│  ├─ games/
│  │  ├─ iidx-32.json
│  │  └─ sdvx-6.json
│  ├─ profiles/
│  │  └─ shared/
│  │     └─ spicetools.xml
│  ├─ thumbnails/
│  │  ├─ iidx-32.webp
│  │  └─ sdvx-6.webp
│  └─ logs/
└─ docs/
```

게임 폴더에는 spice2x 실행 파일이 전혀 남지 않습니다. 가장 확실한 portable 구성은 위처럼 게임도 `ArcadeGameManager` 아래에 두는 것입니다. 기존 배치를 유지해야 한다면 `../iidx-32/contents`처럼 바깥의 형제 폴더를 가리킬 수도 있지만, 이 경우 `ArcadeGameManager` 폴더만 따로 옮기는 것이 아니라 공통 부모 폴더를 함께 옮겨야 합니다.

현재 저장소에 배치된 루트의 `spice2x/` 폴더를 그대로 단일 런타임으로 사용합니다. 1차 버전에서는 버전 선택 기능을 넣지 않고, 업데이트 전에 세 실행 파일을 `backup/`에 복사한 뒤 교체하여 롤백만 지원하면 충분합니다.

## 중앙 런타임 실행 규칙

spice2x 소스는 시작할 때 실행 파일의 부모 폴더를 기본 `MODULE_PATH`로 사용합니다. `moduleDirectory`를 지정하면 `-modules`에 절대경로를 전달하고, 비워 두면 인자를 생략해 spice2x 기본 탐색을 사용합니다.

모든 실행은 다음 규칙을 따릅니다.

```text
Executable       = <runtime>\spice.exe 또는 spice64.exe
WorkingDirectory = <gameRoot>
Arguments        = [-modules <moduleDirectory>]
                   [-cfgpath <configPath>]
                   [-patchcfgpath <patchManagerConfigPath>]
                   [-ea]
                   [-url <serviceUrl>]
                   [-card0 <cardNumber>]
                   <게임 공통 인자>
                   <선택한 실행 프로필 인자>
```

- `WorkingDirectory`는 게임 루트로 고정합니다. `prop`, `dev`, `game` 등 상대경로를 사용하는 게임을 위해 필요합니다.
- `moduleDirectory`는 게임에 따라 게임 루트 또는 `<gameRoot>\modules`일 수 있으므로 manifest에서 지정합니다.
- 설정 파일에는 절대경로를 저장하지 않습니다. `moduleDirectory`, `cfgpath` 및 다른 경로는 실행 직전에만 메모리에서 현재 위치에 맞는 절대경로로 해석합니다. 생성된 절대경로는 설정에 다시 기록하지 않습니다.
- 문자열 하나로 명령행을 합치지 말고 Python `subprocess.Popen`에 인자 목록을 전달합니다. 공백과 따옴표가 들어간 경로가 안전해집니다.
- Configurator도 선택된 `spicecfg.exe`에 지정된 `-modules`, `-cfgpath`, `-patchcfgpath`, 네트워크 전역 인자를 전달합니다. 비어 있는 선택 인자는 전달하지 않습니다.

## 상대경로 규칙

portable 기준점(`portableRoot`)은 프로세스의 현재 작업 폴더가 아니라 `.arcade-game-manager-root`가 있는 폴더입니다. 배포판에서는 `main.py`와 같은 폴더입니다. 하위 폴더에서 실행되더라도 상위 폴더를 따라가며 루트 표식을 찾으므로 바로가기나 BAT가 시작된 위치의 영향을 받지 않습니다. 기존 `.bsm-root`도 호환을 위해 인식합니다.

저장 규칙은 다음과 같이 고정합니다.

| 필드 | 저장 기준 | 예시 |
|---|---|---|
| `spice2x.*Executable` | `portableRoot` | `spice2x/spice64.exe` 또는 빈 값 |
| `spice2x.configPath` | `portableRoot` | `spice2x/spicetools.xml` 또는 빈 값 |
| `spice2x.patchManagerConfigPath` | `portableRoot` | `spice2x/spicetools_patch_manager.json` 또는 빈 값 |
| `spice2x.serviceUrl` | 경로 아님 | `example.com:8083` 또는 빈 값 |
| `spice2x.card0` | 경로 아님 | 16자리 16진수 카드 번호 또는 빈 값 |
| `gameRoot` | `portableRoot` | `games/iidx-32/contents` |
| `thumbnail` | `portableRoot` | `data/thumbnails/iidx-32.webp` |
| `moduleDirectory` | 해당 `gameRoot` | `modules` 또는 `.` |
| 게임 인자 안의 상대 파일 | 해당 `gameRoot` | `prop/ea3-config.xml` |

경로 구분자는 JSON에서 `/`로 통일하고, 실행할 때 Windows 경로로 정규화합니다. 드라이브 문자, UNC 경로, `file:` URI, `%APPDATA%` 같은 환경 변수는 manifest 저장 시 거부합니다.

```text
portableRoot = FindParentContaining(AppContext.BaseDirectory, ".arcade-game-manager-root")
gameRoot     = FullPath(portableRoot + manifest.gameRoot)
modulePath   = FullPath(gameRoot + manifest.moduleDirectory)
runtimePath  = FullPath(portableRoot + settings.spice2x.*Executable)
configPath   = FullPath(portableRoot + settings.spice2x.configPath)
patchConfig  = FullPath(portableRoot + settings.spice2x.patchManagerConfigPath)
thumbnail    = FullPath(portableRoot + manifest.thumbnail)
```

`FullPath` 결과는 프로세스를 시작하고 파일을 읽는 동안에만 사용합니다. 이렇게 하면 `C:\game\ArcadeGameManager`를 `E:\Arcade\ArcadeGameManager`로 옮겨도 JSON 수정 없이 새 위치에서 다시 계산됩니다.

경로 검증기는 최소한 아래를 확인해야 합니다.

- 저장값이 비어 있지 않고 `Path.IsPathRooted`가 `false`인지
- 정규화 후 파일/폴더가 실제로 존재하는지
- `moduleDirectory`가 의도한 `gameRoot` 내부인지
- 활성 런타임에 선택한 x86/x64 실행 파일이 있는지
- 설정을 저장할 때 절대경로로 역직렬화되지 않았는지

## 게임 추가와 DLL 감지

게임 추가는 두 가지 흐름을 지원합니다.

게임이 아닌 실행 항목은 `itemKind`를 `server` 또는 `tool`로 저장하고 `도구 · 서버` 탭에서 분리해 표시합니다. 이 항목은 `direct` launcher만 사용하며 EXE, BAT, CMD를 지원합니다. `../_tools/asphyxia-core-win-x64`처럼 portable root 바깥의 형제 폴더도 상대경로로 저장할 수 있습니다. 관리자가 시작한 프로세스 핸들은 현재 세션 동안 유지해 실행 상태 표시에 사용합니다.

라이브러리 헤더의 단일 정렬 메뉴는 이름 오름차순·내림차순과 최신 오름차순·내림차순을 제공합니다. 최신순은 `data/games/*.json`의 마지막 수정 시각을 기준으로 하며 게임과 도구·서버 탭, 리스트와 썸네일 보기에 동일하게 적용됩니다. 선택한 `sortMode`는 보기 방식과 함께 `data/ui.json`에 저장합니다.

직접 실행 항목의 EXE 아이콘은 Windows에 256px 크기를 요청해 주 아이콘 그룹에서 가장 적합한 고해상도 리소스를 선택합니다. 추출한 투명 원본은 EXE의 절대경로·크기·수정 시각으로 키를 만든 `data/cache/icons/*.png`에 저장하며, 리스트와 썸네일 렌더링은 같은 캐시를 재사용합니다. EXE가 교체되면 키가 달라져 자동으로 다시 추출됩니다.

### 게임 계열을 먼저 지정

1. 사용자가 IIDX, SDVX, DDR 같은 게임 계열을 선택합니다.
2. 내장 카탈로그에서 기본 게임명과 모듈 폴더 후보를 채웁니다.
3. 게임 폴더를 지정하면 해당 계열의 DLL을 찾아 모듈 폴더와 x86/x64를 보정합니다.
4. DLL을 찾지 못해도 기본값을 표시하고 사용자가 수정하여 저장할 수 있습니다.

### 폴더에서 게임 제안

1. 사용자가 게임 폴더만 선택하고 `DLL 탐색`을 누릅니다.
2. 선택 폴더 아래를 제한된 깊이까지 읽기 전용으로 탐색합니다.
3. spice2x의 알려진 모듈 DLL 이름과 보조 파일 조건을 비교합니다.
4. 일치 후보를 신뢰도순으로 표시합니다.
5. DLL의 PE 헤더를 읽어 `x86` 또는 `x64`를 결정합니다. DLL을 로드하거나 실행하지 않습니다.

`bm2dx.dll`, `soundvoltex.dll`처럼 계열을 확정할 수 있는 DLL은 높은 신뢰도로 제안합니다. `launch.dll`, `popn.dll`, `system.dll`, `kamunity.dll`처럼 여러 게임에서 공유되는 이름은 `ess.dll`, `data/mfc.ini`, `game/*.exe` 같은 보조 시그니처로 구분합니다. 감지 규칙은 [bsm/catalog.py](../bsm/catalog.py)에 UI와 분리해 두었습니다.

정확한 작품명과 버전은 같은 DLL 이름을 공유할 수 있으므로 폴더명에서 초기값만 추정합니다.

```text
IIDX_32_Pinky_Crush
  gameType = iidx
  title    = beatmania IIDX
  version  = 32 Pinky Crush
```

등록 창의 `게임명`과 `버전`은 항상 편집할 수 있습니다. 저장 후에는 폴더명을 다시 분석해 사용자가 편집한 값을 자동으로 덮어쓰지 않습니다.

관련 근거:

- [spice2x launcher.cpp](https://github.com/spice2x/spice2x.github.io/blob/main/src/spice2x/launcher/launcher.cpp): 기본 `MODULE_PATH`와 `-modules` 처리
- [spice2x Config files](https://github.com/spice2x/spice2x.github.io/wiki/spice2x-features#config-files): `-cfgpath`를 게임 실행 파일과 Configurator 양쪽에 항상 전달해야 함

## 설정 모델

### 전역 설정

`settings.json`에는 선택적으로 spice2x 관련 파일 경로와 전역 네트워크 값을 둡니다. 실행 파일 경로가 비어 있으면 표준 위치와 PATH에서 찾습니다. 설정 파일 경로가 비어 있으면 각각 `-cfgpath`, `-patchcfgpath`를 생략해 spice2x 기본값을 사용합니다. `localEa`, `serviceUrl`, `card0`도 비어 있거나 꺼져 있으면 해당 인자를 생략합니다.

```json
{
  "schemaVersion": 4,
  "spice2x": {
    "x86Executable": "spice2x/spice.exe",
    "x64Executable": "spice2x/spice64.exe",
    "configurator": "spice2x/spicecfg.exe",
    "configPath": "spice2x/spicetools.xml",
    "patchManagerConfigPath": "spice2x/spicetools_patch_manager.json",
    "localEa": false,
    "serviceUrl": "example.com:8083",
    "card0": "E0040100FFFFFFFF"
  }
}
```

모든 값은 portable root 기준 상대경로이며 빈 값도 유효합니다.

### 게임 manifest

게임별 파일은 실행에 필요한 차이만 가집니다.

```json
{
  "schemaVersion": 1,
  "id": "iidx-example",
  "title": "beatmania IIDX",
  "version": "32 Pinky Crush",
  "gameType": "iidx",
  "gameRoot": "games/iidx-example/contents",
  "architecture": "x64",
  "moduleDirectory": "modules",
  "thumbnail": "data/thumbnails/iidx-example.webp",
  "configProfile": "shared",
  "arguments": ["-w"],
  "detectedDll": "bm2dx.dll"
}
```

`arguments`는 게임에 필요한 사용자 인자입니다. GUI에서는 한 줄에 인자 하나씩 입력합니다. `-modules`, `-cfgpath`, `-patchcfgpath`, `-ea`, `-url`, `-card0`은 전역 설정에 따라 실행 코어가 자동으로 추가합니다.

환경 변수나 사전 실행 작업이 필요한 게임이 확인되면 다음과 같이 구조화된 필드로 확장합니다. 임의의 shell 문자열을 그대로 실행하는 방식은 경로 quoting과 보안 문제가 있어 피하는 것이 좋습니다.

```json
{
  "environment": {
    "EXAMPLE_DEVICE": "1"
  },
  "preLaunch": [
    {
      "file": "tools/helper.exe",
      "arguments": ["--start"]
    }
  ]
}
```

## 코드 구조

```text
bsm/
├─ models.py          # GameDefinition, DetectionCandidate, LaunchPlan
├─ paths.py           # portable 루트 표식 기준 상대경로 처리
├─ catalog.py         # 게임 DLL 시그니처 카탈로그
├─ detector.py        # 폴더 탐색, 게임/아키텍처/메타데이터 제안
├─ store.py           # data/games/*.json 원자적 저장
├─ launcher.py        # 중앙 spice2x 실행 계획과 프로세스 실행
├─ thumbnail.py       # 이미지 로딩
└─ ui.py              # tkinter GUI
tests/                # 표준 unittest 코어 테스트
```

`GameLauncher`가 실행 방식에 따라 `SpiceLauncher` 또는 `DirectLauncher`로 전달하고 실제 프로세스를 시작하기 전에 `LaunchPlan`을 만듭니다. 테스트에서는 게임을 실행하지 않고 실행 파일, 작업 폴더, `-modules`, `-cfgpath`, 사용자 인자를 검증합니다.

`PortablePaths`만 상대경로를 실제 경로로 변환합니다. JSON 저장 계층은 절대경로를 거부합니다.

## 최소 GUI

첫 화면은 복잡한 관리자 화면보다 다음 정도면 충분합니다.

```text
┌────────────────────────────────────────────────────────┐
│ Arcade Game Manager                   [런타임 확인 ⚙] │
├────────────────────────────────────────────────────────┤
│ [썸네일] IIDX 32          [기본 실행 ▼] [설정] [실행] │
│ [썸네일] SDVX 6           [기본 실행 ▼] [설정] [실행] │
│ [썸네일] pop'n ...        [기본 실행 ▼] [설정] [실행] │
├────────────────────────────────────────────────────────┤
│ 상태 / 마지막 오류 / 로그 열기                         │
└────────────────────────────────────────────────────────┘
```

게임 편집 화면에는 제목, 버전, 게임 계열, 게임 루트, x86/x64, 모듈 폴더, 썸네일과 추가 인자를 둡니다. spice2x의 수백 개 옵션을 GUI에서 다시 구현하지 않고 Configurator를 중앙 런타임으로 실행합니다.

## 기존 설치 마이그레이션

실행 파일 제거는 다음 순서가 안전합니다.

1. 기존 BAT에서 작업 폴더와 인자를 읽고, 현재 `portableRoot`에 대한 상대경로로 변환하여 게임 manifest를 생성합니다.
2. 중앙 런타임으로 만든 최종 명령을 미리보기하고 경로 존재 여부를 검사합니다.
3. 기존 게임 폴더의 spice2x 파일을 건드리지 않은 상태로 중앙 런타임 실행을 시험합니다.
4. 정상 실행이 확인된 게임만 기존 실행 파일을 별도 백업 폴더로 이동합니다.
5. 모든 게임 검증 후 백업을 삭제합니다.

자동 마이그레이션 기능은 처음부터 삭제하지 말고 `검사 -> dry-run -> 백업 이동 -> 확인 후 삭제` 단계로 나눠야 합니다. 서로 다른 버전의 spice2x를 쓰던 게임은 통일된 최신 런타임에서 동작이 달라질 수 있으므로 게임별 검증 결과도 manifest나 상태 DB에 기록하는 것이 좋습니다.

## 구현 순서

1. 상대경로 모델, DLL 감지, JSON 저장, `LaunchPlan` 생성 및 검증 — 구현됨
2. 중앙 `spice.exe/spice64.exe/spicecfg.exe` 실행 — 구현됨
3. 게임 추가/편집/삭제/실행 GUI — 구현됨
4. 실제 보유 게임별 DLL 카탈로그 검증 및 규칙 보완
5. 실행 로그 보기와 기존 게임 폴더의 중복 spice 실행 파일 정리 도구
6. spice2x 업데이트 전 백업과 롤백
