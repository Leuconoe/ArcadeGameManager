import tempfile
import unittest
from pathlib import Path

from bsm.launcher import DirectLauncher, GameLauncher, SpiceLauncher
from bsm.models import GameDefinition
from bsm.paths import PortablePaths


class SpiceLauncherTests(unittest.TestCase):
    def test_builds_central_runtime_plan(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "spice2x"
            modules = root / "games" / "iidx" / "contents" / "modules"
            runtime.mkdir(parents=True)
            modules.mkdir(parents=True)
            (runtime / "spice64.exe").write_bytes(b"")
            (runtime / "spicecfg.exe").write_bytes(b"")
            (runtime / "spicetools.xml").write_text("<config />", encoding="utf-8")
            game = GameDefinition(
                id="iidx-32",
                title="beatmania IIDX",
                version="32",
                game_type="iidx",
                game_root="games/iidx/contents",
                module_directory="modules",
                architecture="x64",
                arguments=["-w"],
            )

            plan = SpiceLauncher(PortablePaths(root)).plan(game)

            self.assertEqual(Path(plan.executable), runtime / "spice64.exe")
            self.assertEqual(Path(plan.working_directory), modules.parent)
            self.assertEqual(plan.arguments[0], "-modules")
            self.assertEqual(Path(plan.arguments[1]), modules)
            self.assertEqual(plan.arguments[2], "-cfgpath")
            self.assertEqual(Path(plan.arguments[3]), runtime / "spicetools.xml")
            self.assertEqual(plan.arguments[4], "-w")

    def test_configurator_uses_same_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "spice2x"
            game_root = root / "games" / "sdvx"
            runtime.mkdir(parents=True)
            game_root.mkdir(parents=True)
            (runtime / "spicecfg.exe").write_bytes(b"")
            (runtime / "spicetools.xml").write_text("<config />", encoding="utf-8")
            game = GameDefinition("sdvx", "SDVX", "", "sdvx", "games/sdvx", ".", "x64")

            plan = SpiceLauncher(PortablePaths(root)).plan(game, configure=True)

            self.assertEqual(Path(plan.executable), runtime / "spicecfg.exe")
            self.assertEqual(plan.arguments[0], "-modules")
            self.assertEqual(Path(plan.arguments[1]), game_root)


class ExtensibleLauncherTests(unittest.TestCase):
    def test_direct_launcher_uses_paths_relative_to_game_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "games" / "dmt2" / "dmt2-tool" / "DMT2 Tool.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            game = GameDefinition(
                id="dmt2-tool",
                title="DJMAX Technika 2 Arcade",
                version="",
                game_type="other",
                game_root="games/dmt2",
                launcher_type="direct",
                executable="dmt2-tool/DMT2 Tool.exe",
                working_directory="dmt2-tool",
                arguments=["--windowed"],
            )

            plan = DirectLauncher(PortablePaths(root)).plan(game)

            self.assertEqual(Path(plan.executable), executable)
            self.assertEqual(Path(plan.working_directory), executable.parent)
            self.assertEqual(plan.arguments, ("--windowed",))

    def test_launcher_registry_preserves_legacy_spice2x_default(self):
        game = GameDefinition.from_dict(
            {
                "id": "legacy",
                "title": "Legacy",
                "gameType": "iidx",
                "gameRoot": "games/legacy",
            }
        )

        self.assertEqual(game.launcher_type, "spice2x")
        self.assertIn("spice2x", GameLauncher(PortablePaths(Path.cwd())).launchers)

    def test_validation_reports_missing_direct_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "games" / "missing").mkdir(parents=True)
            game = GameDefinition(
                id="missing",
                title="Missing Game",
                version="",
                game_type="other",
                game_root="games/missing",
                launcher_type="direct",
                executable="game.exe",
            )

            error = GameLauncher(PortablePaths(root)).validation_error(game)

            self.assertIn("게임 실행 파일", error)


if __name__ == "__main__":
    unittest.main()
