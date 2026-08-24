from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


SPICE_TOKEN = re.compile(
    r'(?i)(?:"[^"\r\n]*[\\/](?P<quoted>spice(?:64|cfg)?\.exe)"|'
    r'(?P<plain>(?:[^\s"<>|]+[\\/])*(?P<plain_name>spice(?:64|cfg)?\.exe)))'
)


@dataclass(slots=True, frozen=True)
class BatConversion:
    path: Path
    original_text: str
    converted_text: str
    encoding: str
    replacements: int


class BatConverter:
    def __init__(self, portable_root: Path):
        self.portable_root = portable_root.resolve()
        self.runtime_directory = self.portable_root / "spice2x"

    def preview(self, bat_path: Path) -> BatConversion:
        raw = bat_path.read_bytes()
        text, encoding = decode_batch(raw)
        replacements = 0
        output: list[str] = []

        for line in text.splitlines(keepends=True):
            stripped = line.lstrip()
            command = stripped[1:].lstrip() if stripped.startswith("@") else stripped
            lowered = command.lower()
            if lowered == "rem" or lowered.startswith(("rem ", "rem\t", "::", "echo ", "echo\t")):
                output.append(line)
                continue

            def replace(match: re.Match) -> str:
                nonlocal replacements
                name = match.group("quoted") or match.group("plain_name")
                if not name:
                    return match.group(0)
                target = self.runtime_directory / name.lower()
                relative = os.path.relpath(target, bat_path.parent.resolve()).replace("/", "\\")
                replacements += 1
                return f'"%~dp0{relative}"'

            output.append(SPICE_TOKEN.sub(replace, line))

        return BatConversion(
            path=bat_path,
            original_text=text,
            converted_text="".join(output),
            encoding=encoding,
            replacements=replacements,
        )

    def apply(self, conversion: BatConversion) -> Path:
        if conversion.replacements == 0:
            raise ValueError("변환할 spice 실행 경로가 없습니다.")
        backup = next_backup_path(conversion.path)
        shutil.copy2(conversion.path, backup)

        newline = "\r\n" if "\r\n" in conversion.original_text else "\n"
        normalized = conversion.converted_text.replace("\r\n", "\n").replace("\n", newline)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{conversion.path.name}.", suffix=".tmp", dir=conversion.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding=conversion.encoding, newline="") as stream:
                stream.write(normalized)
            os.replace(temporary_name, conversion.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
        return backup


def decode_batch(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig"), "utf-8-sig"
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    for encoding in ("utf-8", "cp949", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def next_backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bak")
    number = 2
    while candidate.exists():
        candidate = path.with_name(path.name + f".bak.{number}")
        number += 1
    return candidate
