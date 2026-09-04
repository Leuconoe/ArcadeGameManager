from __future__ import annotations

import ctypes
import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from ctypes import wintypes

from .arguments import normalize_arguments
from .models import GameDefinition, LaunchPlan
from .paths import PortablePaths
from .settings import RuntimeSettings


class ElevatedProcess:
    """Minimal Popen-compatible wrapper around an elevated process handle."""

    def __init__(self, handle):
        self._handle = handle
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.GetProcessId.argtypes = [wintypes.HANDLE]
        self._kernel32.GetProcessId.restype = wintypes.DWORD
        self._kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self.pid = int(self._kernel32.GetProcessId(handle))

    def poll(self) -> int | None:
        if not self._handle:
            return 0
        exit_code = wintypes.DWORD()
        if not self._kernel32.GetExitCodeProcess(self._handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return None if exit_code.value == 259 else int(exit_code.value)

    def wait(self) -> int:
        if not self._handle:
            return 0
        result = self._kernel32.WaitForSingleObject(self._handle, 0xFFFFFFFF)
        if result == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return self.poll() or 0

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    def __del__(self):
        self.close()


class _ShellExecuteInfo(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    )


def _launch_elevated(plan: LaunchPlan) -> ElevatedProcess:
    if os.name != "nt":
        raise OSError("관리자 권한 실행은 Windows에서만 지원합니다.")

    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell_execute = shell32.ShellExecuteExW
    shell_execute.argtypes = [ctypes.POINTER(_ShellExecuteInfo)]
    shell_execute.restype = wintypes.BOOL
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040  # SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = plan.executable
    info.lpParameters = subprocess.list2cmdline(plan.arguments) if plan.arguments else None
    info.lpDirectory = plan.working_directory
    info.nShow = 1  # SW_SHOWNORMAL
    if not shell_execute(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:
            raise OSError("관리자 권한 실행이 사용자에 의해 취소되었습니다.")
        raise ctypes.WinError(error)
    return ElevatedProcess(info.hProcess)


def _launch_plan(plan: LaunchPlan) -> subprocess.Popen | ElevatedProcess:
    if plan.run_as_admin:
        return _launch_elevated(plan)
    return subprocess.Popen(list(plan.command), cwd=plan.working_directory, close_fds=True)


def _auxiliary_plan(paths: PortablePaths, game: GameDefinition, configured: str) -> LaunchPlan | None:
    if not configured.strip():
        return None
    game_root = paths.resolve(game.game_root)
    executable = paths.resolve(configured.strip(), base=game_root)
    if not executable.is_file():
        raise FileNotFoundError(f"프로필 보조 앱을 찾을 수 없습니다: {executable}")
    working_directory = executable.parent
    if executable.suffix.lower() in {".bat", ".cmd"}:
        return LaunchPlan(
            executable=os.environ.get("COMSPEC", "cmd.exe"),
            working_directory=str(working_directory),
            arguments=("/d", "/c", str(executable)),
        )
    return LaunchPlan(str(executable), str(working_directory), ())


def _launch_after_exit(process: subprocess.Popen | ElevatedProcess, plan: LaunchPlan, profile_title: str) -> None:
    try:
        process.wait()
        _launch_plan(plan)
    except OSError:
        logging.getLogger(__name__).exception("Could not run post-exit app for %s", profile_title)


class SpiceLauncher:
    def __init__(self, paths: PortablePaths, settings: RuntimeSettings | None = None):
        self.paths = paths
        self.settings = settings or RuntimeSettings()

    def update_settings(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def _resolve_executable(self, configured: str, name: str, game_root: Path) -> Path:
        if configured.strip():
            return self.paths.resolve(configured.strip())
        candidates = (
            self.paths.root / "spice2x" / name,
            self.paths.root / name,
            game_root / name,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        discovered = shutil.which(name)
        return Path(discovered).resolve() if discovered else candidates[0].resolve()

    def available(self) -> bool:
        placeholder_root = self.paths.root
        for configured, name in (
            (self.settings.spice_x86_executable, "spice.exe"),
            (self.settings.spice_x64_executable, "spice64.exe"),
        ):
            if self._resolve_executable(configured, name, placeholder_root).is_file():
                return True
        return False

    def plan(self, game: GameDefinition, *, configure: bool = False) -> LaunchPlan:
        game_root = self.paths.resolve(game.game_root)
        executable_name = "spicecfg.exe" if configure else ("spice.exe" if game.architecture == "x86" else "spice64.exe")
        configured_executable = (
            self.settings.spice_configurator
            if configure
            else (
                self.settings.spice_x86_executable
                if game.architecture == "x86"
                else self.settings.spice_x64_executable
            )
        )
        executable = self._resolve_executable(configured_executable, executable_name, game_root)
        module_directory = (
            self.paths.resolve(game.module_directory, base=game_root)
            if game.module_directory.strip()
            else None
        )
        config_path = (
            self.paths.resolve(self.settings.spice_config_path)
            if self.settings.spice_config_path.strip()
            else None
        )
        patch_manager_config_path = (
            self.paths.resolve(self.settings.spice_patch_manager_config_path)
            if self.settings.spice_patch_manager_config_path.strip()
            else None
        )

        missing = [
            (executable, "spice2x 실행 파일"),
            (game_root, "게임 폴더"),
        ]
        if module_directory is not None:
            missing.append((module_directory, "모듈 폴더"))
        if config_path is not None:
            missing.append((config_path, "spice2x 설정 파일"))
        if patch_manager_config_path is not None:
            missing.append((patch_manager_config_path, "spice2x 패치 관리자 설정 파일"))
        for path, description in missing:
            if not path.exists():
                raise FileNotFoundError(f"{description}을(를) 찾을 수 없습니다: {path}")

        arguments: list[str] = []
        if module_directory is not None:
            arguments.extend(("-modules", str(module_directory)))
        if config_path is not None:
            arguments.extend(("-cfgpath", str(config_path)))
        if patch_manager_config_path is not None:
            arguments.extend(("-patchcfgpath", str(patch_manager_config_path)))
        if self.settings.spice_local_ea:
            arguments.append("-ea")
        if self.settings.spice_service_url.strip():
            arguments.extend(("-url", self.settings.spice_service_url.strip()))
        if self.settings.spice_card0.strip():
            arguments.extend(("-card0", self.settings.spice_card0.strip()))
        if not configure:
            arguments.extend(normalize_arguments(game.arguments))

        return LaunchPlan(
            executable=str(executable),
            working_directory=str(game_root),
            arguments=tuple(arguments),
            run_as_admin=game.run_as_admin,
        )

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen | ElevatedProcess:
        return _launch_plan(self.plan(game, configure=configure))


class DirectLauncher:
    """Launch an executable contained in a game's portable folder."""

    def __init__(self, paths: PortablePaths):
        self.paths = paths

    def plan(self, game: GameDefinition, *, configure: bool = False) -> LaunchPlan:
        if configure:
            raise ValueError("일반 실행 파일 방식은 별도의 런타임 설정 화면을 지원하지 않습니다.")
        if not game.executable.strip():
            raise ValueError("일반 실행 파일을 선택하세요.")

        game_root = self.paths.resolve(game.game_root)
        executable = self.paths.resolve(game.executable, base=game_root)
        working_directory = self.paths.resolve(game.working_directory or ".", base=game_root)
        for path, description in (
            (game_root, "게임 폴더"),
            (executable, "게임 실행 파일"),
            (working_directory, "작업 폴더"),
        ):
            if not path.exists():
                raise FileNotFoundError(f"{description}을(를) 찾을 수 없습니다: {path}")
        if not executable.is_file():
            raise ValueError(f"게임 실행 파일이 아닙니다: {executable}")
        if not working_directory.is_dir():
            raise ValueError(f"작업 폴더가 아닙니다: {working_directory}")

        arguments = normalize_arguments(game.arguments)
        if executable.suffix.lower() in {".bat", ".cmd"}:
            return LaunchPlan(
                executable=os.environ.get("COMSPEC", "cmd.exe"),
                working_directory=str(working_directory),
                arguments=("/d", "/c", str(executable), *arguments),
                run_as_admin=game.run_as_admin,
            )
        return LaunchPlan(str(executable), str(working_directory), arguments, game.run_as_admin)

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen | ElevatedProcess:
        return _launch_plan(self.plan(game, configure=configure))


class GameLauncher:
    """Dispatch games to a runtime adapter without coupling the GUI to one runtime."""

    def __init__(self, paths: PortablePaths, settings: RuntimeSettings | None = None):
        self.paths = paths
        self.launchers = {
            "spice2x": SpiceLauncher(paths, settings),
            "direct": DirectLauncher(paths),
        }

    def update_runtime_settings(self, settings: RuntimeSettings) -> None:
        self.launchers["spice2x"].update_settings(settings)

    def spice_available(self) -> bool:
        return self.launchers["spice2x"].available()

    def _for(self, game: GameDefinition):
        try:
            return self.launchers[game.launcher_type]
        except KeyError as error:
            raise ValueError(f"지원하지 않는 실행 방식입니다: {game.launcher_type}") from error

    def plan(self, game: GameDefinition, *, configure: bool = False) -> LaunchPlan:
        return self._for(game).plan(game, configure=configure)

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen | ElevatedProcess:
        main_plan = self.plan(game, configure=configure)
        if configure:
            return _launch_plan(main_plan)

        pre_launch_plan = _auxiliary_plan(self.paths, game, game.pre_launch_executable)
        post_exit_plan = _auxiliary_plan(self.paths, game, game.post_exit_executable)
        if pre_launch_plan is not None:
            _launch_plan(pre_launch_plan)
        process = _launch_plan(main_plan)
        if post_exit_plan is not None:
            threading.Thread(
                target=_launch_after_exit,
                args=(process, post_exit_plan, game.title),
                name=f"post-exit-{game.id}",
                daemon=False,
            ).start()
        return process

    def validation_error(self, game: GameDefinition) -> str:
        try:
            self.plan(game)
            _auxiliary_plan(self.paths, game, game.pre_launch_executable)
            _auxiliary_plan(self.paths, game, game.post_exit_executable)
            return ""
        except (OSError, ValueError) as error:
            return str(error)
