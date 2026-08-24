from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from .models import GameDefinition
from .paths import PortablePaths


class GameStore:
    def __init__(self, paths: PortablePaths):
        self.paths = paths
        self.games_directory = paths.root / "data" / "games"

    def load_all(self) -> list[GameDefinition]:
        if not self.games_directory.exists():
            return []
        games: list[GameDefinition] = []
        for file_path in sorted(self.games_directory.glob("*.json")):
            try:
                with file_path.open("r", encoding="utf-8") as stream:
                    games.append(GameDefinition.from_dict(json.load(stream)))
            except (OSError, ValueError, TypeError) as error:
                raise ValueError(f"게임 설정을 읽을 수 없습니다: {file_path.name}: {error}") from error
        return games

    def save(self, game: GameDefinition) -> None:
        self._validate(game)
        self.games_directory.mkdir(parents=True, exist_ok=True)
        target = self.games_directory / f"{game.id}.json"
        self._write_json_atomic(target, game.to_dict())

    def delete(self, game_id: str) -> None:
        target = self.games_directory / f"{game_id}.json"
        if target.exists():
            target.unlink()

    def make_unique_id(self, title: str, version: str, current_id: str = "") -> str:
        base = re.sub(r"[^a-z0-9]+", "-", f"{title}-{version}".lower()).strip("-") or "game"
        existing = {item.id for item in self.load_all() if item.id != current_id}
        candidate = base
        number = 2
        while candidate in existing:
            candidate = f"{base}-{number}"
            number += 1
        return candidate

    def _validate(self, game: GameDefinition) -> None:
        if not game.id or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", game.id):
            raise ValueError("게임 ID는 영문 소문자, 숫자, 하이픈만 사용할 수 있습니다.")
        if not game.title.strip():
            raise ValueError("게임명을 입력하세요.")
        self.paths.ensure_relative(game.game_root)
        self.paths.ensure_relative(game.module_directory)
        self.paths.ensure_relative(game.working_directory)
        if game.launcher_type not in {"spice2x", "direct"}:
            raise ValueError("지원하지 않는 실행 방식입니다.")
        if game.launcher_type == "direct":
            if not game.executable.strip():
                raise ValueError("일반 실행 파일을 선택하세요.")
            self.paths.ensure_relative(game.executable)
        if game.thumbnail:
            self.paths.ensure_relative(game.thumbnail)
        if game.architecture not in {"x86", "x64"}:
            raise ValueError("아키텍처는 x86 또는 x64여야 합니다.")

    @staticmethod
    def _write_json_atomic(target: Path, value: dict) -> None:
        handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary_name, target)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
