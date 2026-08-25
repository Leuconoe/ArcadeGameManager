import unittest

from bsm.models import GameDefinition
from bsm.sorting import sort_library_items


def item(item_id: str, title: str, version: str = "") -> GameDefinition:
    return GameDefinition(item_id, title, version, "other", f"games/{item_id}")


class LibrarySortingTests(unittest.TestCase):
    def setUp(self):
        self.items = [item("zeta", "Zeta"), item("alpha-2", "alpha", "2"), item("alpha-1", "Alpha", "1")]
        self.modified = {"zeta": 20, "alpha-2": 30, "alpha-1": 10}

    def test_name_sort_supports_both_directions(self):
        ascending = sort_library_items(self.items, "name_asc", self.modified.__getitem__)
        descending = sort_library_items(self.items, "name_desc", self.modified.__getitem__)

        self.assertEqual([value.id for value in ascending], ["alpha-1", "alpha-2", "zeta"])
        self.assertEqual([value.id for value in descending], ["zeta", "alpha-2", "alpha-1"])

    def test_recent_sort_uses_manifest_modified_time(self):
        newest_first = sort_library_items(self.items, "recent_desc", self.modified.__getitem__)
        oldest_first = sort_library_items(self.items, "recent_asc", self.modified.__getitem__)

        self.assertEqual([value.id for value in newest_first], ["alpha-2", "zeta", "alpha-1"])
        self.assertEqual([value.id for value in oldest_first], ["alpha-1", "zeta", "alpha-2"])


if __name__ == "__main__":
    unittest.main()
