import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bsm.paths import PortablePathError, PortablePaths


class PortablePathsTests(unittest.TestCase):
    def test_relative_path_round_trip_after_root_move(self):
        with tempfile.TemporaryDirectory() as temporary:
            first_root = Path(temporary) / "first"
            second_root = Path(temporary) / "second"
            first_game = first_root / "games" / "iidx" / "contents"
            second_game = second_root / "games" / "iidx" / "contents"
            first_game.mkdir(parents=True)
            second_game.mkdir(parents=True)

            relative = PortablePaths(first_root).relative(first_game)

            self.assertEqual(relative, "games/iidx/contents")
            self.assertEqual(PortablePaths(second_root).resolve(relative), second_game.resolve())

    def test_absolute_paths_are_rejected(self):
        with self.assertRaises(PortablePathError):
            PortablePaths.ensure_relative("C:/Games/IIDX")

    def test_discovers_marker_from_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".bsm-root").write_text("", encoding="utf-8")
            child = root / "src" / "deep"
            child.mkdir(parents=True)
            self.assertEqual(PortablePaths.discover(child).root, root.resolve())

    def test_frozen_executable_uses_its_folder_without_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "ArcadeGameManager.exe"
            executable.write_bytes(b"")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
                discovered = PortablePaths.discover()

            self.assertEqual(discovered.root, root.resolve())

    def test_source_mode_still_requires_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(PortablePathError):
                PortablePaths.discover(Path(temporary))


if __name__ == "__main__":
    unittest.main()
