import tempfile
import unittest
from pathlib import Path

from bsm.models import GameDefinition
from bsm.paths import PortablePaths
from bsm.store import GameStore


class GameStoreSupportItemTests(unittest.TestCase):
    def test_game_profile_round_trip_preserves_admin_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "games" / "admin-game").mkdir(parents=True)
            store = GameStore(PortablePaths(root))
            game = GameDefinition(
                id="admin-game",
                title="Admin Game",
                version="",
                game_type="other",
                game_root="games/admin-game",
                run_as_admin=True,
                pre_launch_executable="helpers/prepare.exe",
                post_exit_executable="helpers/cleanup.bat",
            )

            store.save(game)

            loaded = store.load_all()[0]
            self.assertTrue(loaded.run_as_admin)
            self.assertEqual(loaded.pre_launch_executable, "helpers/prepare.exe")
            self.assertEqual(loaded.post_exit_executable, "helpers/cleanup.bat")

    def test_profile_helper_must_be_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = GameStore(PortablePaths(Path(temporary)))
            game = GameDefinition(
                id="absolute-helper",
                title="Absolute Helper",
                version="",
                game_type="other",
                game_root="games/absolute-helper",
                pre_launch_executable="C:/tools/prepare.exe",
            )

            with self.assertRaisesRegex(ValueError, "절대경로"):
                store.save(game)

    def test_support_server_round_trip_keeps_relative_parent_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "ArcadeGameManager"
            server_root = Path(temporary) / "_tools" / "asphyxia"
            root.mkdir()
            server_root.mkdir(parents=True)
            (server_root / "server.exe").write_bytes(b"")
            paths = PortablePaths(root)
            store = GameStore(paths)
            item = GameDefinition(
                id="asphyxia",
                title="Asphyxia Core",
                version="",
                game_type="support-server",
                game_root=paths.relative(server_root),
                module_directory="",
                launcher_type="direct",
                executable="server.exe",
                item_kind="server",
                run_as_admin=True,
            )

            store.save(item)
            loaded = store.load_all()[0]

            self.assertEqual(loaded.item_kind, "server")
            self.assertFalse(Path(loaded.game_root).is_absolute())
            self.assertEqual(paths.resolve(loaded.game_root), server_root.resolve())
            self.assertTrue(loaded.run_as_admin)

    def test_support_item_must_use_direct_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = GameStore(PortablePaths(Path(temporary)))
            item = GameDefinition(
                id="invalid-server",
                title="Invalid",
                version="",
                game_type="support-server",
                game_root="../_tools/server",
                module_directory="",
                launcher_type="spice2x",
                item_kind="server",
            )

            with self.assertRaisesRegex(ValueError, "일반 실행 파일"):
                store.save(item)


if __name__ == "__main__":
    unittest.main()
