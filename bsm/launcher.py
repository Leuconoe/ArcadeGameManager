from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from .models import GameDefinition, LaunchPlan
from .paths import PortablePaths
from .settings import RuntimeSettings


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

        missing = [
            (executable, "spice2x 실행 파일"),
            (game_root, "게임 폴더"),
        ]
        if module_directory is not None:
            missing.append((module_directory, "모듈 폴더"))
        if config_path is not None:
            missing.append((config_path, "spice2x 설정 파일"))
        for path, description in missing:
            if not path.exists():
                raise FileNotFoundError(f"{description}을(를) 찾을 수 없습니다: {path}")

        arguments: list[str] = []
        if module_directory is not None:
            arguments.extend(("-modules", str(module_directory)))
        if config_path is not None:
            arguments.extend(("-cfgpath", str(config_path)))
        if not configure:
            arguments.extend(game.arguments)

        return LaunchPlan(
            executable=str(executable),
            working_directory=str(game_root),
            arguments=tuple(arguments),
        )

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen:
        plan = self.plan(game, configure=configure)
        return subprocess.Popen(
            list(plan.command),
            cwd=plan.working_directory,
            close_fds=True,
        )


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

        return LaunchPlan(
            executable=str(executable),
            working_directory=str(working_directory),
            arguments=tuple(game.arguments),
        )

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen:
        plan = self.plan(game, configure=configure)
        return subprocess.Popen(list(plan.command), cwd=plan.working_directory, close_fds=True)


class GameLauncher:
    """Dispatch games to a runtime adapter without coupling the GUI to one runtime."""

    def __init__(self, paths: PortablePaths, settings: RuntimeSettings | None = None):
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

    def launch(self, game: GameDefinition, *, configure: bool = False) -> subprocess.Popen:
        return self._for(game).launch(game, configure=configure)

    def validation_error(self, game: GameDefinition) -> str:
        try:
            self.plan(game)
            return ""
        except (OSError, ValueError) as error:
            return str(error)
