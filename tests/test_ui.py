from __future__ import annotations

import unittest
from types import SimpleNamespace

from bsm.ui import COLORS, ManagerApp


class FakeTree:
    def __init__(self, selected: tuple[str, ...] = ()) -> None:
        self.selected = selected
        self.seen = ""

    def selection(self) -> tuple[str, ...]:
        return self.selected

    def selection_set(self, game_id: str) -> None:
        self.selected = (game_id,)

    def selection_remove(self, *_game_ids: str) -> None:
        self.selected = ()

    def see(self, game_id: str) -> None:
        self.seen = game_id


class FakeCard:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **options: object) -> None:
        self.configure_calls.append(options)


class ManagerAppSelectionTests(unittest.TestCase):
    def test_select_game_keeps_card_geometry_stable(self) -> None:
        old_card = FakeCard()
        new_card = FakeCard()
        untouched_card = FakeCard()
        app = SimpleNamespace(
            games={"old": object(), "new": object(), "untouched": object()},
            selected_game_key="old",
            tree=FakeTree(("old",)),
            grid_cards={
                "old": old_card,
                "new": new_card,
                "untouched": untouched_card,
            },
        )

        ManagerApp._select_game(app, "new")

        self.assertEqual(app.selected_game_key, "new")
        self.assertEqual(app.tree.selected, ("new",))
        self.assertEqual(app.tree.seen, "new")
        self.assertEqual(
            old_card.configure_calls,
            [{"highlightbackground": COLORS["border"], "highlightcolor": COLORS["border"]}],
        )
        self.assertEqual(
            new_card.configure_calls,
            [{"highlightbackground": COLORS["accent"], "highlightcolor": COLORS["accent"]}],
        )
        self.assertEqual(untouched_card.configure_calls, [])
        self.assertNotIn("highlightthickness", new_card.configure_calls[0])


if __name__ == "__main__":
    unittest.main()
