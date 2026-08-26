import tempfile
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from bsm.launcher import DirectLauncher, GameLauncher, SpiceLauncher, _launch_plan
from bsm.models import GameDefinition, LaunchPlan
from bsm.paths import PortablePaths
from bsm.settings import RuntimeSettings


class SpiceLauncherTests(unittest.TestCase):
    def test_configurator_does_not_run_profile_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "spice2x"
            game_root = root / "games" / "sdvx"
            runtime.mkdir(parents=True)
            game_root.mkdir(parents=True)
            (runtime / "spicecfg.exe").write_bytes(b"")
            (game_root / "prepare.exe").write_bytes(b"")
            (game_root / "cleanup.exe").write_bytes(b"")
            game = GameDefinition(
                "sdvx", "SDVX", "", "sdvx", "games/sdvx", "", "x64",
                pre_launch_executable="prepare.exe",
                post_exit_executable="cleanup.exe",
            )
            expected_process = object()

            with patch("bsm.launcher._launch_plan", return_value=expected_process) as launch_plan:
                process = GameLauncher(PortablePaths(root)).launch(game, configure=True)

            self.assertIs(process, expected_process)
            launch_plan.assert_called_once()
            self.assertEqual(Path(launch_plan.call_args.args[0].executable), runtime / "spicecfg.exe")

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
            (runtime / "spicetools_patch_manager.json").write_text("{}", encoding="utf-8")
            game = GameDefinition(
                id="iidx-32",
                title="beatmania IIDX",
                version="32",
                game_type="iidx",
                game_root="games/iidx/contents",
                module_directory="modules",
                architecture="x64",
                arguments=["-w"],
                run_as_admin=True,
            )

            plan = SpiceLauncher(
                PortablePaths(root),
                RuntimeSettings(
                    spice_config_path="spice2x/spicetools.xml",
                    spice_patch_manager_config_path="spice2x/spicetools_patch_manager.json",
                    spice_local_ea=True,
                    spice_service_url="example.com:8083",
                    spice_card0="E0040100ABCDEF12",
                ),
            ).plan(game)

            self.assertEqual(Path(plan.executable), runtime / "spice64.exe")
            self.assertEqual(Path(plan.working_directory), modules.parent)
            self.assertEqual(plan.arguments[0], "-modules")
            self.assertEqual(Path(plan.arguments[1]), modules)
            self.assertEqual(plan.arguments[2], "-cfgpath")
            self.assertEqual(Path(plan.arguments[3]), runtime / "spicetools.xml")
            self.assertEqual(plan.arguments[4], "-patchcfgpath")
            self.assertEqual(Path(plan.arguments[5]), runtime / "spicetools_patch_manager.json")
            self.assertEqual(plan.arguments[6:], (
                "-ea",
                "-url", "example.com:8083",
                "-card0", "E0040100ABCDEF12",
                "-w",
            ))
            self.assertTrue(plan.run_as_admin)

    def test_configurator_uses_same_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "spice2x"
            game_root = root / "games" / "sdvx"
            runtime.mkdir(parents=True)
            game_root.mkdir(parents=True)
            (runtime / "spicecfg.exe").write_bytes(b"")
            (runtime / "spicetools.xml").write_text("<config />", encoding="utf-8")
            (runtime / "spicetools_patch_manager.json").write_text("{}", encoding="utf-8")
            game = GameDefinition("sdvx", "SDVX", "", "sdvx", "games/sdvx", ".", "x64")

            plan = SpiceLauncher(
                PortablePaths(root),
                RuntimeSettings(
                    spice_config_path="spice2x/spicetools.xml",
                    spice_patch_manager_config_path="spice2x/spicetools_patch_manager.json",
                    spice_local_ea=True,
                    spice_service_url="example.com:8083",
                    spice_card0="E0040100ABCDEF12",
                ),
            ).plan(game, configure=True)

            self.assertEqual(Path(plan.executable), runtime / "spicecfg.exe")
            self.assertEqual(plan.arguments[0], "-modules")
            self.assertEqual(Path(plan.arguments[1]), game_root)
            self.assertEqual(plan.arguments[2], "-cfgpath")
            self.assertEqual(Path(plan.arguments[3]), runtime / "spicetools.xml")
            self.assertEqual(plan.arguments[4], "-patchcfgpath")
            self.assertEqual(Path(plan.arguments[5]), runtime / "spicetools_patch_manager.json")
            self.assertEqual(plan.arguments[6:], (
                "-ea",
                "-url", "example.com:8083",
                "-card0", "E0040100ABCDEF12",
            ))

    def test_omits_optional_paths_when_left_blank(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "spice2x"
            game_root = root / "games" / "popn"
            runtime.mkdir(parents=True)
            game_root.mkdir(parents=True)
            (runtime / "spice64.exe").write_bytes(b"")
            game = GameDefinition("popn", "pop'n music", "", "popn", "games/popn", "", "x64")

            plan = SpiceLauncher(PortablePaths(root), RuntimeSettings()).plan(game)

            self.assertEqual(plan.arguments, ())

    def test_uses_custom_executable_and_config_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_root = root / "games" / "custom"
            executable = root / "runtime" / "custom-spice.exe"
            config = root / "profiles" / "cabinet.xml"
            game_root.mkdir(parents=True)
            executable.parent.mkdir(parents=True)
            config.parent.mkdir(parents=True)
            executable.write_bytes(b"")
            config.write_text("<config />", encoding="utf-8")
            game = GameDefinition("custom", "Custom", "", "other", "games/custom", "", "x64")
            settings = RuntimeSettings(
                spice_x64_executable="runtime/custom-spice.exe",
                spice_config_path="profiles/cabinet.xml",
            )

            plan = SpiceLauncher(PortablePaths(root), settings).plan(game)

            self.assertEqual(Path(plan.executable), executable)
            self.assertEqual(plan.arguments[0], "-cfgpath")
            self.assertEqual(Path(plan.arguments[1]), config)


class ExtensibleLauncherTests(unittest.TestCase):
    def test_runs_pre_app_then_post_app_after_profile_exits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_root = root / "games" / "lifecycle"
            game_root.mkdir(parents=True)
            for name in ("game.exe", "prepare.bat", "cleanup.exe"):
                (game_root / name).write_bytes(b"")
            game = GameDefinition(
                id="lifecycle",
                title="Lifecycle Game",
                version="",
                game_type="other",
                game_root="games/lifecycle",
                launcher_type="direct",
                executable="game.exe",
                pre_launch_executable="prepare.bat",
                post_exit_executable="cleanup.exe",
            )
            completed = threading.Event()
            launched_plans = []

            class FinishedProcess:
                def wait(self):
                    return 0

            def fake_launch(plan):
                launched_plans.append(plan)
                if len(launched_plans) == 2:
                    return FinishedProcess()
                if len(launched_plans) == 3:
                    completed.set()
                return object()

            with patch("bsm.launcher._launch_plan", side_effect=fake_launch):
                process = GameLauncher(PortablePaths(root)).launch(game)
                self.assertTrue(completed.wait(1))

            self.assertIsInstance(process, FinishedProcess)
            self.assertEqual(launched_plans[0].executable, os.environ.get("COMSPEC", "cmd.exe"))
            self.assertEqual(Path(launched_plans[0].arguments[2]), game_root / "prepare.bat")
            self.assertEqual(Path(launched_plans[1].executable), game_root / "game.exe")
            self.assertEqual(Path(launched_plans[2].executable), game_root / "cleanup.exe")
            self.assertEqual(Path(launched_plans[2].working_directory), game_root)

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
                run_as_admin=True,
            )

            plan = DirectLauncher(PortablePaths(root)).plan(game)

            self.assertEqual(Path(plan.executable), executable)
            self.assertEqual(Path(plan.working_directory), executable.parent)
            self.assertEqual(plan.arguments, ("--windowed",))
            self.assertTrue(plan.run_as_admin)

    def test_admin_plan_uses_elevated_launcher(self):
        plan = LaunchPlan("game.exe", ".", ("--windowed",), run_as_admin=True)
        expected_process = object()

        with patch("bsm.launcher._launch_elevated", return_value=expected_process) as launch_elevated:
            actual_process = _launch_plan(plan)

        self.assertIs(actual_process, expected_process)
        launch_elevated.assert_called_once_with(plan)

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

    def test_validation_reports_missing_profile_helper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_root = root / "games" / "missing-helper"
            game_root.mkdir(parents=True)
            (game_root / "game.exe").write_bytes(b"")
            game = GameDefinition(
                id="missing-helper",
                title="Missing Helper",
                version="",
                game_type="other",
                game_root="games/missing-helper",
                launcher_type="direct",
                executable="game.exe",
                pre_launch_executable="missing.exe",
            )

            error = GameLauncher(PortablePaths(root)).validation_error(game)

            self.assertIn("프로필 보조 앱", error)

    def test_batch_support_tool_is_wrapped_with_cmd(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tool_root = root / "_tools" / "server"
            tool_root.mkdir(parents=True)
            script = tool_root / "start-server.bat"
            script.write_text("@echo off\n", encoding="utf-8")
            item = GameDefinition(
                id="server",
                title="Virtual Server",
                version="",
                game_type="support-server",
                game_root=PortablePaths(root).relative(tool_root),
                module_directory="",
                launcher_type="direct",
                executable="start-server.bat",
                item_kind="server",
            )

            plan = DirectLauncher(PortablePaths(root)).plan(item)

            self.assertEqual(plan.executable, os.environ.get("COMSPEC", "cmd.exe"))
            self.assertEqual(plan.arguments[:2], ("/d", "/c"))
            self.assertEqual(Path(plan.arguments[2]), script.resolve())

    def test_batch_profile_preserves_admin_flag(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_root = root / "games" / "batch"
            game_root.mkdir(parents=True)
            script = game_root / "launch.bat"
            script.write_text("@echo off\n", encoding="utf-8")
            game = GameDefinition(
                id="batch",
                title="Batch Game",
                version="",
                game_type="other",
                game_root="games/batch",
                launcher_type="direct",
                executable="launch.bat",
                run_as_admin=True,
            )

            plan = DirectLauncher(PortablePaths(root)).plan(game)

            self.assertTrue(plan.run_as_admin)


if __name__ == "__main__":
    unittest.main()
