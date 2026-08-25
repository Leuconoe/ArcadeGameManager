import tempfile
import unittest
from pathlib import Path

from bsm.paths import PortablePaths
from bsm.settings import RuntimeSettings, RuntimeSettingsStore


class RuntimeSettingsStoreTests(unittest.TestCase):
    def test_round_trip_preserves_optional_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeSettingsStore(PortablePaths(Path(temporary)))
            expected = RuntimeSettings(
                spice_x86_executable="runtime/spice.exe",
                spice_x64_executable="runtime/spice64.exe",
                spice_configurator="runtime/spicecfg.exe",
                spice_config_path="profiles/shared.xml",
                spice_patch_manager_config_path="profiles/spicetools_patch_manager.json",
            )

            store.save(expected)
            actual = store.load()

            self.assertEqual(actual, expected)

    def test_missing_settings_file_uses_automatic_defaults(self):
        with tempfile.TemporaryDirectory() as temporary:
            settings = RuntimeSettingsStore(PortablePaths(Path(temporary))).load()

            self.assertEqual(settings, RuntimeSettings())

    def test_reads_original_settings_schema(self):
        settings = RuntimeSettings.from_dict(
            {
                "runtime": {
                    "directory": "spice2x",
                    "x86Executable": "spice.exe",
                    "x64Executable": "spice64.exe",
                    "configurator": "spicecfg.exe",
                },
                "defaultConfigProfile": "shared",
                "configProfiles": {"shared": {"path": "spice2x/spicetools.xml"}},
            }
        )

        self.assertEqual(settings.spice_x64_executable, "spice2x/spice64.exe")
        self.assertEqual(settings.spice_config_path, "spice2x/spicetools.xml")


if __name__ == "__main__":
    unittest.main()
