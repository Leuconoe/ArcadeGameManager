import struct
import tempfile
import unittest
from pathlib import Path

from bsm.detector import GameDetector
from bsm.paths import PortablePaths


def write_pe(path: Path, machine: int) -> None:
    data = bytearray(256)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, machine)
    path.write_bytes(data)


class GameDetectorTests(unittest.TestCase):
    def test_detects_iidx_and_infers_folder_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "games" / "IIDX_32_Pinky_Crush"
            modules = selected / "contents" / "modules"
            modules.mkdir(parents=True)
            write_pe(modules / "bm2dx.dll", 0x8664)

            candidates = GameDetector(PortablePaths(root)).detect(selected)

            self.assertEqual(len(candidates), 1)
            candidate = candidates[0]
            self.assertEqual(candidate.game_type, "iidx")
            self.assertEqual(candidate.suggested_title, "beatmania IIDX")
            self.assertEqual(candidate.suggested_version, "32 Pinky Crush")
            self.assertEqual(candidate.game_root, "games/IIDX_32_Pinky_Crush/contents")
            self.assertEqual(candidate.module_directory, "modules")
            self.assertEqual(candidate.architecture, "x64")

    def test_reads_x86_from_pe_header(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "games" / "SDVX6"
            selected.mkdir(parents=True)
            write_pe(selected / "soundvoltex.dll", 0x014C)

            candidate = GameDetector(PortablePaths(root)).detect(selected)[0]

            self.assertEqual(candidate.game_type, "sdvx")
            self.assertEqual(candidate.architecture, "x86")


if __name__ == "__main__":
    unittest.main()
