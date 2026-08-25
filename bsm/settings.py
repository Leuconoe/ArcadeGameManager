from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass

from .paths import PortablePaths


@dataclass(slots=True)
class RuntimeSettings:
    spice_x86_executable: str = ""
    spice_x64_executable: str = ""
    spice_configurator: str = ""
    spice_config_path: str = ""
    spice_patch_manager_config_path: str = ""
    spice_local_ea: bool = False
    spice_service_url: str = ""
    spice_card0: str = ""

    @classmethod
    def from_dict(cls, value: dict) -> "RuntimeSettings":
        spice = value.get("spice2x")
        if isinstance(spice, dict):
            return cls(
                spice_x86_executable=str(spice.get("x86Executable", "")),
                spice_x64_executable=str(spice.get("x64Executable", "")),
                spice_configurator=str(spice.get("configurator", "")),
                spice_config_path=str(spice.get("configPath", "")),
                spice_patch_manager_config_path=str(spice.get("patchManagerConfigPath", "")),
                spice_local_ea=bool(spice.get("localEa", False)),
                spice_service_url=str(spice.get("serviceUrl", "")),
                spice_card0=str(spice.get("card0", "")),
            )

        # Read the original example schema for existing installations.
        runtime = value.get("runtime", {})
        directory = str(runtime.get("directory", "")).strip().strip("/\\")

        def runtime_file(key: str) -> str:
            name = str(runtime.get(key, "")).strip()
            return f"{directory}/{name}" if directory and name else name

        profile_name = str(value.get("defaultConfigProfile", ""))
        profiles = value.get("configProfiles", {})
        profile = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}
        return cls(
            spice_x86_executable=runtime_file("x86Executable"),
            spice_x64_executable=runtime_file("x64Executable"),
            spice_configurator=runtime_file("configurator"),
            spice_config_path=str(profile.get("path", "")) if isinstance(profile, dict) else "",
        )

    def to_dict(self) -> dict:
        return {
            "schemaVersion": 4,
            "spice2x": {
                "x86Executable": self.spice_x86_executable,
                "x64Executable": self.spice_x64_executable,
                "configurator": self.spice_configurator,
                "configPath": self.spice_config_path,
                "patchManagerConfigPath": self.spice_patch_manager_config_path,
                "localEa": self.spice_local_ea,
                "serviceUrl": self.spice_service_url,
                "card0": self.spice_card0,
            },
        }


class RuntimeSettingsStore:
    def __init__(self, paths: PortablePaths):
        self.paths = paths
        self.path = paths.root / "data" / "settings.json"

    def load(self) -> RuntimeSettings:
        if not self.path.is_file():
            return RuntimeSettings()
        try:
            return RuntimeSettings.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError) as error:
            raise ValueError(f"런타임 설정을 읽을 수 없습니다: {error}") from error

    def save(self, settings: RuntimeSettings) -> None:
        for value in (
            settings.spice_x86_executable,
            settings.spice_x64_executable,
            settings.spice_configurator,
            settings.spice_config_path,
            settings.spice_patch_manager_config_path,
        ):
            if value:
                self.paths.ensure_relative(value)

        settings.spice_service_url = settings.spice_service_url.strip()
        settings.spice_card0 = settings.spice_card0.strip().upper()
        if settings.spice_card0 and not re.fullmatch(r"[0-9A-F]{16}", settings.spice_card0):
            raise ValueError("플레이어 1 카드 번호는 16자리 16진수여야 합니다.")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix=".settings.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(settings.to_dict(), stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
