from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import GameDefinition


SORT_MODES = {"name_asc", "name_desc", "recent_asc", "recent_desc"}


def sort_library_items(
    items: Iterable[GameDefinition],
    mode: str,
    modified_time: Callable[[str], int],
) -> list[GameDefinition]:
    selected_mode = mode if mode in SORT_MODES else "name_asc"
    values = list(items)
    if selected_mode.startswith("name_"):
        return sorted(
            values,
            key=lambda item: (item.title.casefold(), item.version.casefold(), item.id),
            reverse=selected_mode.endswith("desc"),
        )
    return sorted(
        values,
        key=lambda item: (modified_time(item.id), item.title.casefold(), item.id),
        reverse=selected_mode.endswith("desc"),
    )
