from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class GameDefinition:
    id: str
    title: str
    version: str
    game_type: str
    game_root: str
    module_directory: str = "modules"
    architecture: str = "x64"
    thumbnail: str = ""
    arguments: list[str] = field(default_factory=list)
    detected_dll: str = ""
    launcher_type: str = "spice2x"
    executable: str = ""
    working_directory: str = "."

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GameDefinition":
        return cls(
            id=str(value.get("id", "")),
            title=str(value.get("title", "")),
            version=str(value.get("version", "")),
            game_type=str(value.get("gameType", "unknown")),
            game_root=str(value.get("gameRoot", "")),
            module_directory=str(value.get("moduleDirectory", ".")),
            architecture=str(value.get("architecture", "x64")),
            thumbnail=str(value.get("thumbnail", "")),
            arguments=[str(item) for item in value.get("arguments", [])],
            detected_dll=str(value.get("detectedDll", "")),
            launcher_type=str(value.get("launcherType", "spice2x")),
            executable=str(value.get("executable", "")),
            working_directory=str(value.get("workingDirectory", ".")),
        )

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return {
            "schemaVersion": 2,
            "id": raw["id"],
            "title": raw["title"],
            "version": raw["version"],
            "gameType": raw["game_type"],
            "gameRoot": raw["game_root"],
            "moduleDirectory": raw["module_directory"],
            "architecture": raw["architecture"],
            "thumbnail": raw["thumbnail"],
            "arguments": raw["arguments"],
            "detectedDll": raw["detected_dll"],
            "launcherType": raw["launcher_type"],
            "executable": raw["executable"],
            "workingDirectory": raw["working_directory"],
        }


@dataclass(slots=True, frozen=True)
class DetectionCandidate:
    game_type: str
    suggested_title: str
    suggested_version: str
    game_root: str
    module_directory: str
    architecture: str
    detected_dll: str
    confidence: int


@dataclass(slots=True, frozen=True)
class LaunchPlan:
    executable: str
    working_directory: str
    arguments: tuple[str, ...]

    @property
    def command(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)
