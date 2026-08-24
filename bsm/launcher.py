from __future__ import annotations

import subprocess
from pathlib import Path

from .models import GameDefinition, LaunchPlan
from .paths import PortablePaths


class SpiceLauncher:
    def __init__(self, paths: PortablePaths):
        self.paths = paths
        self.runtime_directory = paths.root / "spice2x"
        self.config_path = self.runtime_directory / "spicetools.xml"

    def plan(self, game: GameDefinition, *, configure: bool = False) -> LaunchPlan:
        game_root = self.paths.resolve(game.game_root)
        module_directory = self.paths.resolve(game.module_directory, base=game_root)
        executable_name = "spicecfg.exe" if configure else ("spice.exe" if game.architecture == "x86" else "spice64.exe")
        executable = self.runtime_directory / executable_name

        missing = [
            (executable, "spice2x 실행 파일"),
            (game_root, "게임 폴더"),
            (module_directory, "모듈 폴더"),
            (self.config_path, "공용 설정 파일"),
        ]
        for path, description in missing:
            if not path.exists():
                raise FileNotFoundError(f"{description}을(를) 찾을 수 없습니다: {path}")

        arguments = [
            "-modules",
            str(module_directory),
            "-cfgpath",
            str(self.config_path),
        ]
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

    def __init__(self, paths: PortablePaths):
        self.launchers = {
            "spice2x": SpiceLauncher(paths),
            "direct": DirectLauncher(paths),
        }

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
