import tempfile
import unittest
from pathlib import Path

from bsm.bat_converter import BatConverter


class BatConverterTests(unittest.TestCase):
    def test_only_replaces_spice_executable_and_preserves_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "BemaniSpiceManager"
            bat_directory = root / "games" / "iidx"
            bat_directory.mkdir(parents=True)
            (root / "spice2x").mkdir()
            bat = bat_directory / "launch.bat"
            bat.write_text(
                '@echo off\r\n@REM old spice64.exe must stay in this comment\r\necho spice.exe stays too\r\n"C:\\old spice\\spice64.exe" -w -url http://localhost\r\necho done\r\n',
                encoding="utf-8",
                newline="",
            )

            converter = BatConverter(root)
            preview = converter.preview(bat)

            self.assertEqual(preview.replacements, 1)
            self.assertIn('@REM old spice64.exe must stay in this comment', preview.converted_text)
            self.assertIn('echo spice.exe stays too', preview.converted_text)
            self.assertIn('"%~dp0..\\..\\spice2x\\spice64.exe" -w -url http://localhost', preview.converted_text)
            self.assertIn("echo done", preview.converted_text)

    def test_apply_creates_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "spice2x").mkdir()
            bat = root / "launch.bat"
            original = "spice.exe -w\n"
            bat.write_text(original, encoding="utf-8")
            converter = BatConverter(root)

            backup = converter.apply(converter.preview(bat))

            self.assertEqual(backup.read_text(encoding="utf-8"), original)
            self.assertIn('"%~dp0spice2x\\spice.exe" -w', bat.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
