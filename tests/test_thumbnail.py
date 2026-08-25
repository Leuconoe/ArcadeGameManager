import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from bsm.thumbnail import executable_icon_cache_path, load_executable_icon_image


class ExecutableIconCacheTests(unittest.TestCase):
    def test_extracted_icon_is_cached_and_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "game.exe"
            cache = root / "data" / "cache" / "icons"
            executable.write_bytes(b"fake executable")
            extracted = Image.new("RGBA", (256, 256), (255, 93, 61, 255))

            with patch("bsm.thumbnail.sys.platform", "win32"), patch(
                "bsm.thumbnail._extract_windows_executable_icon", return_value=extracted
            ) as extractor:
                first = load_executable_icon_image(executable, cache)
                second = load_executable_icon_image(executable, cache)

            self.assertEqual(extractor.call_count, 1)
            self.assertEqual(first.size, (256, 256))
            self.assertEqual(second.getpixel((0, 0)), (255, 93, 61, 255))
            self.assertTrue(executable_icon_cache_path(executable, cache).is_file())

    def test_cache_key_changes_when_executable_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "game.exe"
            cache = root / "data" / "cache" / "icons"
            executable.write_bytes(b"first")
            first_path = executable_icon_cache_path(executable, cache)

            executable.write_bytes(b"second version")
            second_path = executable_icon_cache_path(executable, cache)

            self.assertNotEqual(first_path, second_path)


if __name__ == "__main__":
    unittest.main()
