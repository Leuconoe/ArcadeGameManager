from __future__ import annotations

import os
import sys
from pathlib import Path


class PortablePathError(ValueError):
    pass


class PortablePaths:
    def __init__(self, root: Path):
        self.root = root.resolve()

    @classmethod
    def discover(cls, start: Path | None = None) -> "PortablePaths":
        frozen_executable = Path(sys.executable) if getattr(sys, "frozen", False) else None
        current = (start or frozen_executable or Path(__file__).resolve()).resolve()
        if current.is_file():
            current = current.parent

        markers = (".arcade-game-manager-root", ".bsm-root")
        for candidate in (current, *current.parents):
            if any((candidate / marker).is_file() for marker in markers):
                return cls(candidate)
        raise PortablePathError("Arcade Game Manager portable 루트 표시 파일을 찾지 못했습니다.")

    def resolve(self, relative: str, *, base: Path | None = None) -> Path:
        self.ensure_relative(relative)
        anchor = (base or self.root).resolve()
        return (anchor / Path(relative.replace("/", os.sep))).resolve()

    def relative(self, path: Path, *, base: Path | None = None) -> str:
        anchor = (base or self.root).resolve()
        absolute = path.resolve()
        return os.path.relpath(absolute, anchor).replace(os.sep, "/")

    @staticmethod
    def ensure_relative(value: str) -> None:
        if not value or not value.strip():
            raise PortablePathError("경로가 비어 있습니다.")
        path = Path(value.replace("/", os.sep))
        if path.is_absolute() or path.drive or value.startswith(("\\\\", "//")):
            raise PortablePathError(f"절대경로는 저장할 수 없습니다: {value}")
        if value.lower().startswith("file:") or "%" in value:
            raise PortablePathError(f"환경 변수나 URI 경로는 저장할 수 없습니다: {value}")
