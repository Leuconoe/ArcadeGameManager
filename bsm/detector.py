from __future__ import annotations

import os
import re
import struct
from pathlib import Path

from .catalog import GAME_SIGNATURES, GameSignature, SIGNATURE_BY_ID
from .models import DetectionCandidate
from .paths import PortablePaths


class GameDetector:
    MAX_DEPTH = 4

    def __init__(self, paths: PortablePaths):
        self.paths = paths
        self.known_dlls = {
            name.lower()
            for signature in GAME_SIGNATURES
            for name in (*signature.dlls, *signature.required_dlls, *signature.excluded_dlls)
        }

    def detect(self, selected_folder: Path) -> list[DetectionCandidate]:
        selected = selected_folder.resolve()
        module_folders = self._find_candidate_module_folders(selected)
        candidates: list[DetectionCandidate] = []

        for module_folder, files in module_folders:
            game_root = module_folder.parent if module_folder.name.lower() == "modules" else module_folder
            for signature in GAME_SIGNATURES:
                matched_dll = self._matches(signature, files, game_root)
                if not matched_dll:
                    continue
                title, version = self.infer_metadata(selected, signature)
                architecture = read_pe_architecture(module_folder / matched_dll)
                candidates.append(
                    DetectionCandidate(
                        game_type=signature.id,
                        suggested_title=title,
                        suggested_version=version,
                        game_root=self.paths.relative(game_root),
                        module_directory=self.paths.relative(module_folder, base=game_root),
                        architecture=architecture,
                        detected_dll=matched_dll,
                        confidence=self._confidence(signature),
                    )
                )

        unique: dict[tuple[str, str], DetectionCandidate] = {}
        for candidate in candidates:
            key = (candidate.game_type, candidate.game_root.casefold())
            current = unique.get(key)
            if current is None or candidate.confidence > current.confidence:
                unique[key] = candidate
        return sorted(unique.values(), key=lambda item: (-item.confidence, item.game_type, item.game_root))

    def defaults_for(self, game_type: str, selected_folder: Path) -> DetectionCandidate:
        signature = SIGNATURE_BY_ID[game_type]
        detected = [item for item in self.detect(selected_folder) if item.game_type == game_type]
        if detected:
            return detected[0]

        selected = selected_folder.resolve()
        title, version = self.infer_metadata(selected, signature)
        return DetectionCandidate(
            game_type=signature.id,
            suggested_title=title,
            suggested_version=version,
            game_root=self.paths.relative(selected),
            module_directory="modules" if (selected / "modules").is_dir() else ".",
            architecture="x64",
            detected_dll="",
            confidence=0,
        )

    def _find_candidate_module_folders(self, selected: Path) -> list[tuple[Path, set[str]]]:
        found: list[tuple[Path, set[str]]] = []
        for current, directories, file_names in os.walk(selected):
            current_path = Path(current)
            depth = len(current_path.relative_to(selected).parts)
            if depth >= self.MAX_DEPTH:
                directories[:] = []
            directories[:] = [name for name in directories if name.lower() not in {"data", "dev", "prop", "contents_data", "backup"}]
            names = {name.lower() for name in file_names}
            if names & self.known_dlls:
                found.append((current_path, names))
        return found

    @staticmethod
    def _matches(signature: GameSignature, files: set[str], game_root: Path) -> str:
        primary = next((name for name in signature.dlls if name.lower() in files), "")
        if not primary:
            return ""
        if any(name.lower() not in files for name in signature.required_dlls):
            return ""
        if any(name.lower() in files for name in signature.excluded_dlls):
            return ""
        if any(not (game_root / Path(value)).exists() for value in signature.required_root_paths):
            return ""
        return primary

    @staticmethod
    def _confidence(signature: GameSignature) -> int:
        return min(100, 80 + len(signature.required_dlls) * 10 + len(signature.required_root_paths) * 15)

    @staticmethod
    def infer_metadata(selected: Path, signature: GameSignature) -> tuple[str, str]:
        folder = selected.name
        if folder.lower() in {"contents", "modules", "game"} and selected.parent.name:
            folder = selected.parent.name
        pretty = re.sub(r"[._-]+", " ", folder).strip()

        aliases = sorted(signature.aliases, key=len, reverse=True)
        for alias in aliases:
            pattern = re.compile(re.escape(alias).replace(r"\ ", r"[\s._-]*"), re.IGNORECASE)
            match = pattern.search(pretty)
            if not match:
                continue
            remainder = (pretty[: match.start()] + " " + pretty[match.end() :]).strip(" -_[]()")
            remainder = re.sub(r"\s+", " ", remainder)
            return signature.title, remainder

        return pretty or signature.title, ""


def read_pe_architecture(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            if stream.read(2) != b"MZ":
                return "x64"
            stream.seek(0x3C)
            pe_offset = struct.unpack("<I", stream.read(4))[0]
            stream.seek(pe_offset)
            if stream.read(4) != b"PE\0\0":
                return "x64"
            machine = struct.unpack("<H", stream.read(2))[0]
            if machine == 0x014C:
                return "x86"
            if machine == 0x8664:
                return "x64"
    except (OSError, struct.error):
        pass
    return "x64"
