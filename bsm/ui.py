from __future__ import annotations

import json
import logging
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .catalog import catalog_titles
from .detector import GameDetector
from .launcher import ElevatedProcess, GameLauncher
from .models import DetectionCandidate, GameDefinition
from .paths import PortablePaths
from .store import GameStore
from .settings import RuntimeSettings, RuntimeSettingsStore
from .sorting import SORT_MODES, sort_library_items
from .thumbnail import load_executable_icon, load_thumbnail


COLORS = {
    "background": "#F4F6FA",
    "surface": "#FFFFFF",
    "surface_alt": "#F0F3F8",
    "surface_hover": "#E5EAF2",
    "border": "#D9E0EA",
    "text": "#172033",
    "muted": "#667085",
    "accent": "#FF5D3D",
    "accent_hover": "#E94C2F",
    "success": "#20A464",
    "success_hover": "#198953",
    "danger": "#D92D50",
}

SORT_LABELS = {
    "name_asc": "이름 A→Z",
    "name_desc": "이름 Z→A",
    "recent_desc": "최신 · 새 항목 먼저",
    "recent_asc": "최신 · 오래된 항목 먼저",
}


def bundled_asset(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


class ManagerApp(tk.Tk):
    def __init__(self, paths: PortablePaths):
        super().__init__()
        self.paths = paths
        self.store = GameStore(paths)
        self.detector = GameDetector(paths)
        self.runtime_settings_store = RuntimeSettingsStore(paths)
        try:
            runtime_settings = self.runtime_settings_store.load()
        except ValueError:
            logging.getLogger(__name__).warning("Could not load runtime settings", exc_info=True)
            runtime_settings = RuntimeSettings()
        self.launcher = GameLauncher(paths, runtime_settings)
        self.games: dict[str, GameDefinition] = {}
        self.validation_errors: dict[str, str] = {}
        self.library_images: dict[str, tk.PhotoImage] = {}
        self.grid_images: dict[str, tk.PhotoImage] = {}
        self.grid_cards: dict[str, tk.Frame] = {}
        self.selected_game_key = ""
        self.active_library = "games"
        self.running_processes: dict[str, subprocess.Popen | ElevatedProcess] = {}
        ui_settings = self._load_ui_settings()
        self.view_mode = ui_settings["viewMode"]
        self.sort_mode = ui_settings["sortMode"]
        self._grid_columns = 0
        self._grid_resize_job: str | None = None

        self.title("Arcade Game Manager")
        self._app_icon = tk.PhotoImage(file=str(bundled_asset("app-icon-64.png")))
        self.iconphoto(True, self._app_icon)
        self.geometry("1180x720")
        self.minsize(900, 560)
        self.configure(background=COLORS["background"])
        self._configure_styles()
        self._build_ui()
        self.refresh()

    def report_callback_exception(self, exception_type, exception_value, traceback) -> None:
        logging.getLogger(__name__).error(
            "Unhandled tkinter callback error",
            exc_info=(exception_type, exception_value, traceback),
        )
        messagebox.showerror(
            "예기치 않은 오류",
            f"{exception_type.__name__}: {exception_value}\n\n자세한 내용은 data/logs/manager.log를 확인하세요.",
            parent=self,
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=COLORS["background"], foreground=COLORS["text"])
        style.configure("App.TFrame", background=COLORS["background"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("Card.TFrame", background=COLORS["surface"], relief=tk.FLAT)
        style.configure("TLabel", background=COLORS["background"], foreground=COLORS["text"])
        style.configure("Surface.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Title.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI Semibold", 20))
        style.configure("Subtitle.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 9))
        style.configure("Section.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI Semibold", 9))
        style.configure("GameTitle.TLabel", background=COLORS["surface"], foreground=COLORS["text"], font=("Segoe UI Semibold", 17))
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"])
        style.configure("Success.TLabel", background=COLORS["surface_alt"], foreground=COLORS["success"], font=("Segoe UI Semibold", 9), padding=(11, 6))
        style.configure("Error.TLabel", background=COLORS["surface_alt"], foreground=COLORS["danger"], font=("Segoe UI Semibold", 9), padding=(11, 6))
        style.configure("Status.TLabel", background=COLORS["surface"], foreground=COLORS["muted"], font=("Segoe UI", 9))

        button_base = {"font": ("Segoe UI Semibold", 9), "padding": (14, 8), "borderwidth": 0, "relief": tk.FLAT}
        style.configure("Primary.TButton", background=COLORS["accent"], foreground="#FFFFFF", **button_base)
        style.map("Primary.TButton", background=[("pressed", COLORS["accent"]), ("active", COLORS["accent_hover"])])
        style.configure("Launch.TButton", background=COLORS["success"], foreground="#FFFFFF", **button_base)
        style.map("Launch.TButton", background=[("pressed", COLORS["success"]), ("active", COLORS["success_hover"])])
        style.configure("Ghost.TButton", background=COLORS["surface_alt"], foreground=COLORS["text"], **button_base)
        style.map("Ghost.TButton", background=[("pressed", COLORS["surface_alt"]), ("active", COLORS["surface_hover"])])
        style.configure("TButton", background=COLORS["surface_alt"], foreground=COLORS["text"], **button_base)
        style.map("TButton", background=[("pressed", COLORS["surface_alt"]), ("active", COLORS["surface_hover"])])
        style.configure("Danger.TButton", background=COLORS["surface_alt"], foreground=COLORS["danger"], **button_base)
        style.map("Danger.TButton", background=[("pressed", COLORS["surface_alt"]), ("active", "#FDE7EC")])

        style.configure("Games.Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"], foreground=COLORS["text"], rowheight=72, borderwidth=0, relief=tk.FLAT)
        style.map("Games.Treeview", background=[("selected", COLORS["accent"])], foreground=[("selected", "#FFFFFF")])
        style.configure("Games.Treeview.Heading", background=COLORS["surface_alt"], foreground=COLORS["muted"], font=("Segoe UI Semibold", 9), padding=(8, 10), relief=tk.FLAT)
        style.map("Games.Treeview.Heading", background=[("active", COLORS["surface_hover"])])
        style.configure("Dark.Vertical.TScrollbar", background=COLORS["surface_alt"], troughcolor=COLORS["surface"], borderwidth=0, arrowcolor=COLORS["muted"])
        style.configure("App.TPanedwindow", background=COLORS["background"], sashwidth=8)
        style.configure("Dark.TSeparator", background=COLORS["border"])
        style.configure("TEntry", fieldbackground=COLORS["surface_alt"], foreground=COLORS["text"], insertcolor=COLORS["text"], bordercolor=COLORS["border"], padding=7)
        style.configure("TCombobox", fieldbackground=COLORS["surface_alt"], foreground=COLORS["text"], arrowcolor=COLORS["muted"], bordercolor=COLORS["border"], padding=6)
        style.configure("TNotebook", background=COLORS["background"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            padding=(16, 9),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["surface"]), ("active", COLORS["surface_hover"])],
            foreground=[("selected", COLORS["accent"])],
        )

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=(18, 16, 18, 10))
        shell.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(shell, style="Surface.TFrame", padding=(20, 16))
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, image=self._app_icon, style="Surface.TLabel").pack(side=tk.LEFT, padx=(0, 13))
        brand = ttk.Frame(header, style="Surface.TFrame")
        brand.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(brand, text="ARCADE GAME MANAGER", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(brand, text="One library. Multiple runtimes. Fully portable.", style="Subtitle.TLabel").pack(anchor=tk.W, pady=(1, 0))

        runtime_ready = self.launcher.spice_available()
        runtime_text = "●  SPICE2X READY" if runtime_ready else "●  SPICE2X OPTIONAL"
        runtime_style = "Success.TLabel" if runtime_ready else "Error.TLabel"
        self.runtime_label = ttk.Label(header, text=runtime_text, style=runtime_style)
        self.runtime_label.pack(side=tk.RIGHT, padx=(12, 0))

        toolbar = ttk.Frame(shell, style="Surface.TFrame", padding=(14, 11))
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="+  게임 추가", style="Primary.TButton", command=self.add_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="+  도구/서버", style="Ghost.TButton", command=self.add_support_item).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="편집", style="Ghost.TButton", command=self.edit_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="복제", style="Ghost.TButton", command=self.duplicate_game).pack(side=tk.LEFT, padx=(0, 7))
        self.configure_button = ttk.Button(toolbar, text="Spice 설정 실행", style="Ghost.TButton", command=self.configure_game)
        self.configure_button.pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="설정", style="Ghost.TButton", command=self.edit_settings).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="삭제", style="Danger.TButton", command=self.delete_game).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="새로고침", style="Ghost.TButton", command=self.refresh).pack(side=tk.RIGHT)

        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Frame(content, style="Card.TFrame", padding=(14, 12))
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_header = ttk.Frame(list_frame, style="Surface.TFrame")
        list_header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(list_header, text="LIBRARY", style="Section.TLabel").pack(side=tk.LEFT)
        self.games_tab_button = ttk.Button(list_header, text="게임", command=lambda: self._set_library_tab("games"))
        self.games_tab_button.pack(side=tk.LEFT, padx=(14, 5))
        self.support_tab_button = ttk.Button(
            list_header, text="도구 · 서버", command=lambda: self._set_library_tab("support")
        )
        self.support_tab_button.pack(side=tk.LEFT)
        self.game_count_var = tk.StringVar(value="0 GAMES")
        ttk.Label(list_header, textvariable=self.game_count_var, style="Muted.TLabel").pack(side=tk.RIGHT)
        self.list_mode_button = ttk.Button(
            list_header, text="리스트", command=lambda: self._set_view_mode("list")
        )
        self.list_mode_button.pack(side=tk.RIGHT, padx=(6, 10))
        self.thumbnail_mode_button = ttk.Button(
            list_header, text="썸네일", command=lambda: self._set_view_mode("thumbnail")
        )
        self.thumbnail_mode_button.pack(side=tk.RIGHT)
        sort_menu = tk.Menu(self, tearoff=False)
        for mode, label in SORT_LABELS.items():
            sort_menu.add_command(label=label, command=lambda value=mode: self._set_sort_mode(value))
        self.sort_button = ttk.Menubutton(
            list_header,
            text=self._sort_button_text(),
            style="Ghost.TButton",
            menu=sort_menu,
        )
        self.sort_button.pack(side=tk.RIGHT, padx=(0, 6))

        columns = ("status", "title", "version", "type", "path")
        self.list_view = ttk.Frame(list_frame, style="Surface.TFrame")
        self.tree = ttk.Treeview(self.list_view, columns=columns, show="tree headings", selectmode="browse", style="Games.Treeview")
        headings = {
            "status": "상태",
            "title": "게임명",
            "version": "버전",
            "type": "계열",
            "path": "게임 폴더",
        }
        widths = {"status": 105, "title": 245, "version": 160, "type": 160, "path": 360}
        self.tree.heading("#0", text="썸네일")
        self.tree.column("#0", width=108, minwidth=108, stretch=False, anchor=tk.CENTER)
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], minwidth=45)
        scrollbar = ttk.Scrollbar(self.list_view, orient=tk.VERTICAL, command=self.tree.yview, style="Dark.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", lambda _event: self.launch_game())
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selection)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda _event: self._restore_library_status())

        self.thumbnail_view = ttk.Frame(list_frame, style="Surface.TFrame")
        self.thumbnail_canvas = tk.Canvas(
            self.thumbnail_view,
            background=COLORS["surface"],
            highlightthickness=0,
            borderwidth=0,
        )
        grid_scrollbar = ttk.Scrollbar(
            self.thumbnail_view,
            orient=tk.VERTICAL,
            command=self.thumbnail_canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.thumbnail_canvas.configure(yscrollcommand=grid_scrollbar.set)
        self.thumbnail_grid = tk.Frame(self.thumbnail_canvas, background=COLORS["surface"])
        self.thumbnail_window = self.thumbnail_canvas.create_window(
            (0, 0), window=self.thumbnail_grid, anchor=tk.NW
        )
        self.thumbnail_grid.bind(
            "<Configure>",
            lambda _event: self.thumbnail_canvas.configure(scrollregion=self.thumbnail_canvas.bbox("all")),
        )
        self.thumbnail_canvas.bind("<Configure>", self._on_thumbnail_resize)
        self.thumbnail_canvas.bind("<MouseWheel>", self._on_thumbnail_mousewheel)
        self.thumbnail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        grid_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._set_view_mode(self.view_mode, persist=False)
        self._update_library_controls()

        self.status_var = tk.StringVar(value=f"Portable root: {self.paths.root}")
        status = ttk.Frame(self, style="Surface.TFrame", padding=(18, 7))
        status.pack(fill=tk.X)
        ttk.Label(status, text="●", style="Surface.TLabel", foreground=COLORS["accent"]).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(status, text="DOUBLE-CLICK TO LAUNCH", style="Status.TLabel").pack(side=tk.RIGHT)

    def refresh(self) -> None:
        selected = self.selected_game_id()
        try:
            self.launcher.update_runtime_settings(self.runtime_settings_store.load())
            loaded = self.store.load_all()
        except ValueError as error:
            messagebox.showerror("설정 오류", str(error), parent=self)
            return
        self.games = {game.id: game for game in loaded}
        self.running_processes = {
            game_id: process
            for game_id, process in self.running_processes.items()
            if process.poll() is None and game_id in self.games
        }
        self.validation_errors = {game.id: self.launcher.validation_error(game) for game in loaded}
        self.library_images.clear()
        self.tree.delete(*self.tree.get_children())
        visible = self._visible_games()
        titles = catalog_titles()
        for index, game in enumerate(visible):
            thumbnail = self._library_thumbnail(game)
            self.library_images[game.id] = thumbnail
            self.tree.insert(
                "",
                tk.END,
                iid=game.id,
                text="",
                image=thumbnail,
                values=(
                    self._item_status(game),
                    game.title,
                    game.version,
                    self._item_type_title(game, titles),
                    game.game_root,
                ),
                tags=("invalid" if self.validation_errors[game.id] else ("even" if index % 2 == 0 else "odd"),),
            )
        self.tree.tag_configure("even", background=COLORS["surface"])
        self.tree.tag_configure("odd", background=COLORS["surface_alt"])
        self.tree.tag_configure("invalid", foreground=COLORS["danger"], background="#FFF4F6")
        self._render_thumbnail_grid(force=True)
        visible_ids = {game.id for game in visible}
        if selected and selected in visible_ids:
            self._select_game(selected)
        elif visible:
            self._select_game(visible[0].id)
        else:
            self._select_game("")
        unit = "GAME" if self.active_library == "games" else "ITEM"
        self.game_count_var.set(f"{len(visible)} {unit}" + ("" if len(visible) == 1 else "S"))
        self._update_runtime_status()
        self._restore_library_status()

    def selected_game_id(self) -> str:
        return self.selected_game_key

    def selected_game(self) -> GameDefinition | None:
        return self.games.get(self.selected_game_id())

    def _visible_games(self) -> list[GameDefinition]:
        if self.active_library == "games":
            visible = [game for game in self.games.values() if game.item_kind == "game"]
        else:
            visible = [game for game in self.games.values() if game.item_kind in {"server", "tool"}]
        return sort_library_items(visible, self.sort_mode, self.store.modified_time)

    @staticmethod
    def _item_type_title(game: GameDefinition, titles: dict[str, str]) -> str:
        if game.item_kind == "server":
            return "가상 서버"
        if game.item_kind == "tool":
            return "보조 도구"
        return titles.get(game.game_type, game.game_type)

    def _item_status(self, game: GameDefinition) -> str:
        process = self.running_processes.get(game.id)
        if process is not None and process.poll() is None:
            return "● 실행 중"
        return "● 실행 가능" if not self.validation_errors.get(game.id) else "● 확인 필요"

    def _set_library_tab(self, tab: str) -> None:
        if tab not in {"games", "support"} or tab == self.active_library:
            return
        self.active_library = tab
        self.selected_game_key = ""
        self._update_library_controls()
        self.refresh()

    def _update_library_controls(self) -> None:
        games_active = self.active_library == "games"
        self.games_tab_button.configure(style="Primary.TButton" if games_active else "Ghost.TButton")
        self.support_tab_button.configure(style="Ghost.TButton" if games_active else "Primary.TButton")
        self.configure_button.configure(state=tk.NORMAL if games_active else tk.DISABLED)

    def _library_thumbnail(self, game: GameDefinition) -> tk.PhotoImage:
        if game.thumbnail:
            try:
                return load_thumbnail(self.paths.resolve(game.thumbnail), max_size=(96, 68))
            except (tk.TclError, OSError, ValueError):
                pass
        if game.launcher_type == "direct" and game.executable:
            try:
                executable = self.paths.resolve(game.executable, base=self.paths.resolve(game.game_root))
                return load_executable_icon(
                    executable,
                    max_size=(68, 68),
                    canvas_size=(96, 68),
                    cache_directory=self.paths.root / "data" / "cache" / "icons",
                )
            except (tk.TclError, OSError, ValueError):
                pass
        image = tk.PhotoImage(width=96, height=68)
        try:
            image.put(COLORS["surface_alt"], to=(0, 0, 96, 68))
        except tk.TclError:
            pass
        return image

    def _grid_thumbnail(self, game: GameDefinition) -> tk.PhotoImage:
        if game.thumbnail:
            try:
                return load_thumbnail(self.paths.resolve(game.thumbnail), max_size=(220, 132))
            except (tk.TclError, OSError, ValueError):
                pass
        if game.launcher_type == "direct" and game.executable:
            try:
                executable = self.paths.resolve(game.executable, base=self.paths.resolve(game.game_root))
                return load_executable_icon(
                    executable,
                    max_size=(112, 112),
                    canvas_size=(220, 132),
                    cache_directory=self.paths.root / "data" / "cache" / "icons",
                )
            except (tk.TclError, OSError, ValueError):
                pass
        image = tk.PhotoImage(width=220, height=132)
        image.put(COLORS["surface_alt"], to=(0, 0, 220, 132))
        return image

    def _load_ui_settings(self) -> dict[str, str]:
        settings_path = self.paths.root / "data" / "ui.json"
        try:
            values = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            values = {}
        if not isinstance(values, dict):
            values = {}
        view_mode = values.get("viewMode")
        sort_mode = values.get("sortMode")
        return {
            "viewMode": view_mode if view_mode in {"thumbnail", "list"} else "thumbnail",
            "sortMode": sort_mode if sort_mode in SORT_MODES else "name_asc",
        }

    def _save_ui_settings(self) -> None:
        settings_path = self.paths.root / "data" / "ui.json"
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps(
                    {"viewMode": self.view_mode, "sortMode": self.sort_mode},
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            logging.getLogger(__name__).warning("Could not save UI settings", exc_info=True)

    def _set_view_mode(self, mode: str, *, persist: bool = True) -> None:
        if mode not in {"thumbnail", "list"}:
            return
        self.view_mode = mode
        self.list_view.pack_forget()
        self.thumbnail_view.pack_forget()
        if mode == "thumbnail":
            self.thumbnail_view.pack(fill=tk.BOTH, expand=True)
        else:
            self.list_view.pack(fill=tk.BOTH, expand=True)
        self.thumbnail_mode_button.configure(style="Primary.TButton" if mode == "thumbnail" else "Ghost.TButton")
        self.list_mode_button.configure(style="Primary.TButton" if mode == "list" else "Ghost.TButton")
        if persist:
            self._save_ui_settings()

    def _sort_button_text(self) -> str:
        return f"정렬 · {SORT_LABELS.get(self.sort_mode, SORT_LABELS['name_asc'])}"

    def _set_sort_mode(self, mode: str) -> None:
        if mode not in SORT_MODES or mode == self.sort_mode:
            return
        self.sort_mode = mode
        self.sort_button.configure(text=self._sort_button_text())
        self._save_ui_settings()
        self.refresh()

    def _on_tree_selection(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection:
            self._select_game(selection[0], sync_tree=False)

    def _on_tree_motion(self, event) -> None:
        game_id = self.tree.identify_row(event.y)
        if game_id:
            self._show_validation_hint(game_id)

    def _show_validation_hint(self, game_id: str) -> None:
        error = self.validation_errors.get(game_id, "")
        if error:
            game = self.games.get(game_id)
            self.status_var.set(f"확인 필요: {game.title if game else game_id} · {error}")

    def _restore_library_status(self) -> None:
        visible_ids = {game.id for game in self._visible_games()}
        invalid_count = sum(bool(error) for game_id, error in self.validation_errors.items() if game_id in visible_ids)
        summary = f"확인 필요 {invalid_count}개" if invalid_count else "모두 실행 가능"
        label = "게임" if self.active_library == "games" else "도구·서버"
        self.status_var.set(f"{label} {len(visible_ids)}개 · {summary} · Portable root: {self.paths.root}")

    def _select_game(self, game_id: str, *, sync_tree: bool = True) -> None:
        previous_game_key = self.selected_game_key
        self.selected_game_key = game_id if game_id in self.games else ""
        if sync_tree:
            current = self.tree.selection()
            if self.selected_game_key and current != (self.selected_game_key,):
                self.tree.selection_set(self.selected_game_key)
                self.tree.see(self.selected_game_key)
            elif not self.selected_game_key and current:
                self.tree.selection_remove(*current)

        # Changing highlightthickness changes the card's requested size.  On the
        # first click that can move/repaint the widget before Tk receives the
        # second click, so a double-click is easily lost.  Keep the geometry
        # stable and repaint only the cards whose selection state changed.
        changed_card_ids = {previous_game_key, self.selected_game_key}
        for card_id in changed_card_ids:
            card = self.grid_cards.get(card_id)
            if card is None:
                continue
            selected = card_id == self.selected_game_key
            card.configure(
                highlightbackground=COLORS["accent"] if selected else COLORS["border"],
                highlightcolor=COLORS["accent"] if selected else COLORS["border"],
            )

    def _on_thumbnail_resize(self, event) -> None:
        self.thumbnail_canvas.itemconfigure(self.thumbnail_window, width=event.width)
        columns = max(1, (event.width - 14) // 240)
        if columns == self._grid_columns:
            return
        if self._grid_resize_job:
            self.after_cancel(self._grid_resize_job)
        self._grid_resize_job = self.after(80, self._render_thumbnail_grid)

    def _on_thumbnail_mousewheel(self, event):
        self.thumbnail_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

    def _render_thumbnail_grid(self, *, force: bool = False) -> None:
        self._grid_resize_job = None
        width = max(self.thumbnail_canvas.winfo_width(), 250)
        columns = max(1, (width - 14) // 240)
        if not force and columns == self._grid_columns and self.grid_cards:
            return
        self._grid_columns = columns
        for child in self.thumbnail_grid.winfo_children():
            child.destroy()
        self.grid_cards.clear()
        self.grid_images.clear()
        titles = catalog_titles()
        games = self._visible_games()
        for row_start in range(0, len(games), columns):
            row_frame = tk.Frame(self.thumbnail_grid, background=COLORS["surface"])
            row_frame.pack(fill=tk.X)
            aligned_row = tk.Frame(row_frame, background=COLORS["surface"])
            aligned_row.pack(anchor=tk.W)
            for game in games[row_start : row_start + columns]:
                self._build_thumbnail_card(aligned_row, game, titles)
        self._select_game(self.selected_game_key)

    def _build_thumbnail_card(self, parent: tk.Frame, game: GameDefinition, titles: dict[str, str]) -> None:
        card = tk.Frame(
                parent,
                background=COLORS["surface"],
                highlightbackground=COLORS["border"],
                highlightthickness=1,
                cursor="hand2",
                width=222,
            )
        card.pack(side=tk.LEFT, padx=8, pady=8, fill=tk.Y)
        image = self._grid_thumbnail(game)
        self.grid_images[game.id] = image
        image_label = tk.Label(card, image=image, background=COLORS["surface_alt"], height=132)
        image_label.pack(fill=tk.X)
        title_label = tk.Label(
                card,
                text=game.title or "이름 없는 게임",
                background=COLORS["surface"],
                foreground=COLORS["text"],
                font=("Segoe UI Semibold", 11),
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=198,
                height=2,
            )
        title_label.pack(fill=tk.X, padx=11, pady=(9, 1))
        summary = " · ".join(
            item for item in (game.version, self._item_type_title(game, titles)) if item
        )
        summary_label = tk.Label(
                card,
                text=summary or "아케이드 게임",
                background=COLORS["surface"],
                foreground=COLORS["muted"],
                font=("Segoe UI", 9),
                anchor=tk.W,
                width=28,
            )
        summary_label.pack(fill=tk.X, padx=11, pady=(0, 10))
        error = self.validation_errors.get(game.id, "")
        running = game.id in self.running_processes and self.running_processes[game.id].poll() is None
        status_label = tk.Label(
            card,
            text="● 실행 중" if running else ("● 실행 가능" if not error else "● 확인 필요"),
            background=COLORS["surface"],
            foreground=COLORS["success"] if running or not error else COLORS["danger"],
                font=("Segoe UI Semibold", 9),
                anchor=tk.W,
            )
        status_label.pack(fill=tk.X, padx=11, pady=(0, 10))
        for widget in (card, image_label, title_label, summary_label, status_label):
            widget.bind("<Button-1>", lambda _event, game_id=game.id: self._select_game(game_id))
            widget.bind("<Double-1>", lambda _event, game_id=game.id: self._launch_card(game_id))
            widget.bind("<MouseWheel>", self._on_thumbnail_mousewheel)
        if error:
            status_label.bind("<Enter>", lambda _event, game_id=game.id: self._show_validation_hint(game_id))
            status_label.bind("<Leave>", lambda _event: self._restore_library_status())
        self.grid_cards[game.id] = card

    def _launch_card(self, game_id: str) -> None:
        self._select_game(game_id)
        self.launch_game()

    def add_game(self) -> None:
        GameDialog(self, self.paths, self.store, self.detector, on_save=self._save_game)

    def add_support_item(self) -> None:
        self._set_library_tab("support")
        SupportItemDialog(self, self.paths, self.store, on_save=self._save_game)

    def edit_game(self) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("항목 편집", "편집할 항목을 선택하세요.", parent=self)
            return
        if game.item_kind == "game":
            GameDialog(self, self.paths, self.store, self.detector, game=game, on_save=self._save_game)
        else:
            SupportItemDialog(self, self.paths, self.store, item=game, on_save=self._save_game)

    def duplicate_game(self) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("항목 복제", "복제할 항목을 선택하세요.", parent=self)
            return
        if game.item_kind == "game":
            GameDialog(
                self,
                self.paths,
                self.store,
                self.detector,
                game=game,
                duplicate=True,
                on_save=self._save_game,
            )
        else:
            SupportItemDialog(
                self,
                self.paths,
                self.store,
                item=game,
                duplicate=True,
                on_save=self._save_game,
            )

    def _save_game(self, game: GameDefinition) -> bool:
        try:
            self.store.save(game)
        except (OSError, ValueError) as error:
            messagebox.showerror("저장 실패", str(error), parent=self)
            return False
        self.refresh()
        if game.id in self.games:
            self._select_game(game.id)
        self.status_var.set(f"저장됨: {game.title} {game.version}".strip())
        return True

    def delete_game(self) -> None:
        game = self.selected_game()
        if not game:
            return
        if not messagebox.askyesno("항목 삭제", f"'{game.title}' 등록을 삭제할까요?\n실제 파일은 삭제되지 않습니다.", parent=self):
            return
        try:
            self.store.delete(game.id)
        except OSError as error:
            messagebox.showerror("삭제 실패", str(error), parent=self)
            return
        self.refresh()

    def launch_game(self) -> None:
        self._run_selected(configure=False)

    def configure_game(self) -> None:
        self._run_selected(configure=True)

    def edit_settings(self) -> None:
        try:
            settings = self.runtime_settings_store.load()
        except ValueError as error:
            messagebox.showerror("런타임 설정 오류", str(error), parent=self)
            return
        SettingsDialog(self, self.paths, settings, self.view_mode, self._save_settings)

    def _save_settings(self, settings: RuntimeSettings, view_mode: str) -> bool:
        try:
            self.runtime_settings_store.save(settings)
        except (OSError, ValueError) as error:
            messagebox.showerror("설정 저장 실패", str(error), parent=self)
            return False
        self.launcher.update_runtime_settings(settings)
        self._set_view_mode(view_mode)
        self.refresh()
        self.status_var.set("설정을 저장했습니다.")
        return True

    def _update_runtime_status(self) -> None:
        ready = self.launcher.spice_available()
        self.runtime_label.configure(
            text="●  SPICE2X READY" if ready else "●  SPICE2X OPTIONAL",
            style="Success.TLabel" if ready else "Error.TLabel",
        )

    def _run_selected(self, *, configure: bool) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("실행", "실행할 항목을 선택하세요.", parent=self)
            return
        try:
            plan = self.launcher.plan(game, configure=configure)
            process = self.launcher.launch(game, configure=configure)
            if not configure and game.item_kind in {"server", "tool"}:
                self.running_processes[game.id] = process
            action = "설정 실행" if configure else "게임 실행"
            if game.item_kind == "server" and not configure:
                action = "서버 실행"
            elif game.item_kind == "tool" and not configure:
                action = "도구 실행"
            self.status_var.set(f"{action}: {game.title} · {subprocess.list2cmdline(plan.command)}")
            if game.item_kind != "game" and not configure:
                self.refresh()
                self.status_var.set(f"{action}: {game.title}")
        except (OSError, ValueError) as error:
            messagebox.showerror("실행 실패", str(error), parent=self)

class AdvancedLaunchOptions:
    def __init__(
        self,
        parent: ttk.Frame,
        paths: PortablePaths,
        folder_provider,
        item: GameDefinition | None,
        *,
        dialog_width: int,
        collapsed_height: int,
        expanded_height: int,
    ):
        self.paths = paths
        self.folder_provider = folder_provider
        self.window = parent.winfo_toplevel()
        self.dialog_width = dialog_width
        self.collapsed_height = collapsed_height
        self.expanded_height = expanded_height
        self.expanded = False
        self.run_as_admin_var = tk.BooleanVar(value=item.run_as_admin if item else False)
        self.pre_launch_var = tk.StringVar(value=item.pre_launch_executable if item else "")
        self.post_exit_var = tk.StringVar(value=item.post_exit_executable if item else "")

        self.toggle_button = ttk.Button(
            parent,
            text=self._toggle_text(item),
            style="Ghost.TButton",
            command=self.toggle,
        )
        self.panel = ttk.Frame(parent, style="App.TFrame", padding=(12, 8))
        self.panel.columnconfigure(1, weight=1)
        ttk.Label(
            self.panel,
            text="필요할 때만 펼쳐 사용하는 프로필별 실행 옵션입니다.",
            style="Muted.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 6))
        ttk.Checkbutton(
            self.panel,
            text="관리자 권한으로 실행 (Windows UAC)",
            variable=self.run_as_admin_var,
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=4)
        self._add_app_row(2, "시작 전 앱", self.pre_launch_var)
        self._add_app_row(3, "종료 후 앱", self.post_exit_var)
        ttk.Label(self.panel, text="추가 인자\n(한 줄에 하나)").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.arguments_hint = ttk.Label(
            self.panel,
            text='옵션과 값을 한 줄에 함께 적어도 됩니다. 공백이 들어간 값은 "큰따옴표"로 묶으세요.',
            style="Muted.TLabel",
            wraplength=520,
        )
        self.arguments_text = tk.Text(
            self.panel,
            height=5,
            wrap=tk.NONE,
            background=COLORS["surface_alt"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief=tk.FLAT,
            borderwidth=0,
            padx=8,
            pady=8,
            font=("Cascadia Mono", 9),
        )
        self.arguments_text.grid(row=4, column=1, columnspan=2, sticky=tk.EW, padx=8, pady=5)
        self.arguments_hint.grid(row=5, column=1, columnspan=2, sticky=tk.W, padx=8, pady=(0, 4))
        if item:
            self.arguments_text.insert("1.0", "\n".join(item.arguments))

    def _add_app_row(self, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(self.panel, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.panel, textvariable=variable).grid(row=row, column=1, sticky=tk.EW, padx=8)
        ttk.Button(
            self.panel,
            text="찾기",
            command=lambda target=variable, title=label: self._browse_app(target, title),
        ).grid(row=row, column=2)

    @staticmethod
    def _toggle_text(item: GameDefinition | None, *, expanded: bool = False) -> str:
        configured = bool(
            item
            and (
                item.run_as_admin
                or item.arguments
                or item.pre_launch_executable
                or item.post_exit_executable
            )
        )
        suffix = " · 설정됨" if configured else ""
        return f"{'▼' if expanded else '▶'} 고급 실행 옵션{suffix}"

    def grid(self, *, row: int) -> None:
        self.toggle_button.grid(row=row, column=0, columnspan=3, sticky=tk.W, pady=(8, 2))
        self.panel.grid(row=row + 1, column=0, columnspan=3, sticky=tk.EW)
        self.panel.grid_remove()

    def toggle(self) -> None:
        self.expanded = not self.expanded
        if self.expanded:
            self.panel.grid()
        else:
            self.panel.grid_remove()
        configured = bool(
            self.run_as_admin_var.get()
            or self.pre_launch_var.get().strip()
            or self.post_exit_var.get().strip()
            or self.arguments()
        )
        suffix = " · 설정됨" if configured else ""
        self.toggle_button.configure(text=f"{'▼' if self.expanded else '▶'} 고급 실행 옵션{suffix}")
        height = self.expanded_height if self.expanded else self.collapsed_height
        height = min(height, self.window.winfo_screenheight() - 80)
        self.window.geometry(f"{self.dialog_width}x{height}")

    def _browse_app(self, variable: tk.StringVar, label: str) -> None:
        try:
            folder = self.folder_provider()
        except (OSError, ValueError) as error:
            messagebox.showerror(f"{label} 선택", str(error), parent=self.window)
            return
        selected = filedialog.askopenfilename(
            parent=self.window,
            title=f"{label} 선택",
            initialdir=str(folder),
            filetypes=[("Executable", "*.exe *.bat *.cmd"), ("All files", "*.*")],
        )
        if selected:
            variable.set(self.paths.relative(Path(selected), base=folder))

    def arguments(self) -> list[str]:
        return [line.strip() for line in self.arguments_text.get("1.0", tk.END).splitlines() if line.strip()]


class SupportItemDialog(tk.Toplevel):
    TYPE_LABELS = {"가상 서버": "server", "보조 도구": "tool"}

    def __init__(
        self,
        parent: ManagerApp,
        paths: PortablePaths,
        store: GameStore,
        *,
        item: GameDefinition | None = None,
        duplicate: bool = False,
        on_save,
    ):
        super().__init__(parent)
        self.paths = paths
        self.store = store
        self.original = None if duplicate else item
        self.on_save = on_save
        self.title("도구·서버 복제" if duplicate else ("도구·서버 편집" if item else "도구·서버 추가"))
        self.geometry("760x630")
        self.minsize(660, 560)
        self.configure(background=COLORS["background"])
        self.transient(parent)
        self.grab_set()

        current_kind = item.item_kind if item else "server"
        kind_label = next(label for label, value in self.TYPE_LABELS.items() if value == current_kind)
        self.kind_var = tk.StringVar(value=kind_label)
        self.title_var = tk.StringVar(value=item.title if item else "")
        self.version_var = tk.StringVar(value=item.version if item else "")
        self.folder_var = tk.StringVar(value=str(paths.resolve(item.game_root)) if item else "")
        self.executable_var = tk.StringVar(value=item.executable if item else "")
        self.working_var = tk.StringVar(value=item.working_directory if item else ".")
        self.thumbnail_var = tk.StringVar(value=item.thumbnail if item else "")
        self._build(item)

    def _build(self, item: GameDefinition | None) -> None:
        form = ttk.Frame(self, style="App.TFrame", padding=20)
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="도구 · 서버 등록", font=("Segoe UI Semibold", 18)).grid(
            row=0, column=0, columnspan=3, sticky=tk.W
        )
        ttk.Label(
            form,
            text="게임 실행에 필요한 가상 서버와 보조 프로그램을 게임 라이브러리와 분리해 관리합니다.",
            foreground=COLORS["muted"],
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(3, 14))

        ttk.Label(form, text="유형").grid(row=2, column=0, sticky=tk.W, pady=6)
        ttk.Combobox(form, textvariable=self.kind_var, values=list(self.TYPE_LABELS), state="readonly").grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, padx=8
        )
        for row, (label, variable) in enumerate(
            (("이름", self.title_var), ("버전/설명", self.version_var)), start=3
        ):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=6)
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=8)

        ttk.Label(form, text="폴더").grid(row=5, column=0, sticky=tk.W, pady=6)
        ttk.Entry(form, textvariable=self.folder_var).grid(row=5, column=1, sticky=tk.EW, padx=8)
        ttk.Button(form, text="찾기", command=self._browse_folder).grid(row=5, column=2)
        ttk.Label(form, text="실행 파일").grid(row=6, column=0, sticky=tk.W, pady=6)
        ttk.Entry(form, textvariable=self.executable_var).grid(row=6, column=1, sticky=tk.EW, padx=8)
        ttk.Button(form, text="찾기", command=self._browse_executable).grid(row=6, column=2)
        ttk.Label(form, text="작업 폴더").grid(row=7, column=0, sticky=tk.W, pady=6)
        ttk.Entry(form, textvariable=self.working_var).grid(row=7, column=1, columnspan=2, sticky=tk.EW, padx=8)
        ttk.Label(form, text="썸네일").grid(row=8, column=0, sticky=tk.W, pady=6)
        ttk.Entry(form, textvariable=self.thumbnail_var).grid(row=8, column=1, sticky=tk.EW, padx=8)
        ttk.Button(form, text="찾기", command=self._browse_thumbnail).grid(row=8, column=2)

        self.advanced_options = AdvancedLaunchOptions(
            form,
            self.paths,
            self._folder_path,
            item,
            dialog_width=760,
            collapsed_height=630,
            expanded_height=780,
        )
        self.advanced_options.grid(row=9)

        buttons = ttk.Frame(form, style="App.TFrame")
        buttons.grid(row=11, column=0, columnspan=3, sticky=tk.E, pady=(16, 0))
        ttk.Button(buttons, text="취소", style="Ghost.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(7, 0))
        ttk.Button(buttons, text="저장", style="Primary.TButton", command=self._save).pack(side=tk.RIGHT)

    def _tools_initial_directory(self) -> Path:
        parent = self.paths.root.parent
        if parent.name.casefold() == "_tools":
            return parent
        sibling = parent / "_tools"
        return sibling if sibling.is_dir() else self.paths.root

    def _browse_folder(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="도구 또는 서버 폴더 선택",
            initialdir=str(self._tools_initial_directory()),
        )
        if not selected:
            return
        folder = Path(selected)
        self.folder_var.set(str(folder))
        if not self.title_var.get().strip():
            self.title_var.set(folder.name.replace("_", " ").replace("-", " "))
        candidates = sorted(
            (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in {".exe", ".bat", ".cmd"}),
            key=lambda path: (path.suffix.lower() != ".exe", path.name.casefold()),
        )
        if len(candidates) == 1:
            self.executable_var.set(candidates[0].name)

    def _folder_path(self) -> Path:
        value = self.folder_var.get().strip()
        if not value:
            raise ValueError("도구 또는 서버 폴더를 선택하세요.")
        path = Path(value)
        return path.resolve() if path.is_absolute() else self.paths.resolve(value)

    def _browse_executable(self) -> None:
        try:
            folder = self._folder_path()
        except ValueError as error:
            messagebox.showerror("실행 파일 선택", str(error), parent=self)
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="실행 파일 선택",
            initialdir=str(folder),
            filetypes=[("Executable", "*.exe *.bat *.cmd"), ("All files", "*.*")],
        )
        if selected:
            self.executable_var.set(self.paths.relative(Path(selected), base=folder))

    def _browse_thumbnail(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="썸네일 선택",
            initialdir=str(self.paths.root),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("All files", "*.*")],
        )
        if selected:
            self.thumbnail_var.set(self.paths.relative(Path(selected)))

    def _save(self) -> None:
        try:
            folder = self._folder_path()
            if not folder.is_dir():
                raise FileNotFoundError(f"폴더가 없습니다: {folder}")
            title = self.title_var.get().strip()
            if not title:
                raise ValueError("이름을 입력하세요.")
            executable = self.executable_var.get().strip()
            if not executable:
                raise ValueError("실행 파일을 선택하세요.")
            version = self.version_var.get().strip()
            item_id = self.original.id if self.original else self.store.make_unique_id(title, version)
            kind = self.TYPE_LABELS[self.kind_var.get()]
            arguments = self.advanced_options.arguments()
            item = GameDefinition(
                id=item_id,
                title=title,
                version=version,
                game_type=f"support-{kind}",
                game_root=self.paths.relative(folder),
                module_directory="",
                architecture="x64",
                thumbnail=self.thumbnail_var.get().strip(),
                arguments=arguments,
                launcher_type="direct",
                executable=executable,
                working_directory=self.working_var.get().strip() or ".",
                item_kind=kind,
                run_as_admin=self.advanced_options.run_as_admin_var.get(),
                pre_launch_executable=self.advanced_options.pre_launch_var.get().strip(),
                post_exit_executable=self.advanced_options.post_exit_var.get().strip(),
            )
        except (OSError, ValueError, KeyError) as error:
            messagebox.showerror("저장 실패", str(error), parent=self)
            return
        if self.on_save(item):
            self.destroy()


class SettingsDialog(tk.Toplevel):
    VIEW_MODES = {"썸네일": "thumbnail", "리스트": "list"}

    def __init__(
        self,
        parent: ManagerApp,
        paths: PortablePaths,
        settings: RuntimeSettings,
        view_mode: str,
        on_save,
    ):
        super().__init__(parent)
        self.paths = paths
        self.on_save = on_save
        self.title("설정")
        self.geometry("820x650")
        self.minsize(720, 600)
        self.configure(background=COLORS["background"])
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._save)

        view_label = next(
            (label for label, value in self.VIEW_MODES.items() if value == view_mode),
            "썸네일",
        )
        self.view_mode_var = tk.StringVar(value=view_label)
        self.x86_var = tk.StringVar(value=settings.spice_x86_executable)
        self.x64_var = tk.StringVar(value=settings.spice_x64_executable)
        self.configurator_var = tk.StringVar(value=settings.spice_configurator)
        self.config_var = tk.StringVar(value=settings.spice_config_path)
        self.patch_config_var = tk.StringVar(value=settings.spice_patch_manager_config_path)
        self.local_ea_var = tk.BooleanVar(value=settings.spice_local_ea)
        self.service_url_var = tk.StringVar(value=settings.spice_service_url)
        self.card0_var = tk.StringVar(value=settings.spice_card0)
        self.location_vars: list[tk.StringVar] = []
        self._build()

    def _build(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=20)
        shell.pack(fill=tk.BOTH, expand=True)

        ttk.Label(shell, text="설정", font=("Segoe UI Semibold", 18)).pack(anchor=tk.W)
        ttk.Label(
            shell,
            text="저장 위치와 화면 표시, 공용 런타임 경로를 한곳에서 확인하고 변경합니다.",
            foreground=COLORS["muted"],
        ).pack(anchor=tk.W, pady=(3, 14))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill=tk.BOTH, expand=True)

        general = ttk.Frame(notebook, style="Surface.TFrame", padding=18)
        spice = ttk.Frame(notebook, style="Surface.TFrame", padding=18)
        notebook.add(general, text="일반")
        notebook.add(spice, text="Spice2x")
        self._build_general_tab(general)
        self._build_spice_tab(spice)

        buttons = ttk.Frame(shell, style="App.TFrame")
        buttons.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(buttons, text="변경 취소", style="Ghost.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(7, 0))
        ttk.Button(buttons, text="저장 후 닫기", style="Primary.TButton", command=self._save).pack(side=tk.RIGHT)

    def _build_general_tab(self, form: ttk.Frame) -> None:
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="화면", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 8)
        )
        ttk.Label(form, text="라이브러리 보기", style="Surface.TLabel").grid(row=1, column=0, sticky=tk.W, pady=(0, 18))
        ttk.Combobox(
            form,
            textvariable=self.view_mode_var,
            values=list(self.VIEW_MODES),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky=tk.W, padx=(14, 0), pady=(0, 18))

        ttk.Separator(form).grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(0, 16))
        ttk.Label(form, text="현재 저장 위치", style="Section.TLabel").grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 4)
        )
        ttk.Label(
            form,
            text="업데이트해도 아래 폴더와 파일은 자동으로 이동하지 않습니다.",
            style="Muted.TLabel",
        ).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))

        locations = (
            ("Portable 루트", self.paths.root),
            ("데이터 폴더", self.paths.root / "data"),
            ("게임·도구 목록", self.paths.root / "data" / "games"),
            ("EXE 아이콘 캐시", self.paths.root / "data" / "cache" / "icons"),
            ("런타임 설정", self.paths.root / "data" / "settings.json"),
            ("화면 설정", self.paths.root / "data" / "ui.json"),
            ("로그", self.paths.root / "data" / "logs" / "manager.log"),
        )
        for row, (label, location) in enumerate(locations, start=5):
            ttk.Label(form, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky=tk.W, pady=4)
            variable = tk.StringVar(value=str(location))
            self.location_vars.append(variable)
            entry = ttk.Entry(form, textvariable=variable, state="readonly")
            entry.grid(row=row, column=1, sticky=tk.EW, padx=(14, 0), pady=4)

    def _build_spice_tab(self, form: ttk.Frame) -> None:
        form.columnconfigure(1, weight=1)
        ttk.Label(
            form,
            text="모든 값은 portable root 기준 상대경로로 저장됩니다. 빈 실행 파일은 표준 위치와 PATH에서 자동 탐색합니다.",
            style="Muted.TLabel",
            wraplength=700,
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 14))

        fields = (
            ("x86 실행 파일", self.x86_var, "executable"),
            ("x64 실행 파일", self.x64_var, "executable"),
            ("Configurator", self.configurator_var, "executable"),
            ("설정 파일 (XML)", self.config_var, "xml"),
            ("패치 관리자 설정 (JSON)", self.patch_config_var, "json"),
        )
        for row, (label, variable, kind) in enumerate(fields, start=1):
            ttk.Label(form, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky=tk.W, pady=7)
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, sticky=tk.EW, padx=9)
            ttk.Button(
                form,
                text="찾기",
                command=lambda target=variable, file_kind=kind: self._browse(target, file_kind),
            ).grid(row=row, column=2)

        ttk.Label(
            form,
            text="빈 설정 경로는 spice2x 기본값을 사용합니다. 패치 관리자 설정을 지정하면 -patchcfgpath로 전달합니다.",
            style="Muted.TLabel",
            wraplength=690,
        ).grid(row=6, column=0, columnspan=3, sticky=tk.W, pady=(16, 8))

        ttk.Separator(form).grid(row=7, column=0, columnspan=3, sticky=tk.EW, pady=(8, 12))
        ttk.Checkbutton(
            form,
            text="로컬 서버 에뮬레이션 (-ea)",
            variable=self.local_ea_var,
        ).grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=4)
        ttk.Label(form, text="원격 서버 주소 (-url)", style="Surface.TLabel").grid(
            row=9, column=0, sticky=tk.W, pady=7
        )
        ttk.Entry(form, textvariable=self.service_url_var).grid(row=9, column=1, columnspan=2, sticky=tk.EW, padx=9)
        ttk.Label(form, text="플레이어 1 카드 (-card0)", style="Surface.TLabel").grid(
            row=10, column=0, sticky=tk.W, pady=7
        )
        ttk.Entry(form, textvariable=self.card0_var).grid(row=10, column=1, columnspan=2, sticky=tk.EW, padx=9)
        ttk.Label(
            form,
            text="카드 번호는 16자리 16진수로 입력합니다. 빈 네트워크 값은 해당 인자를 전달하지 않습니다.",
            style="Muted.TLabel",
        ).grid(row=11, column=0, columnspan=3, sticky=tk.W, pady=(8, 0))

        spice_buttons = ttk.Frame(form, style="Surface.TFrame")
        spice_buttons.grid(row=12, column=0, columnspan=3, sticky=tk.E, pady=(10, 0))
        ttk.Button(spice_buttons, text="모두 자동", style="Ghost.TButton", command=self._clear).pack(side=tk.LEFT)
        ttk.Button(spice_buttons, text="저장", style="Primary.TButton", command=self._save).pack(
            side=tk.LEFT, padx=(7, 0)
        )

    def _browse(self, variable: tk.StringVar, kind: str) -> None:
        if kind == "executable":
            filetypes = [("Windows executable", "*.exe"), ("All files", "*.*")]
        elif kind == "json":
            filetypes = [("JSON config", "*.json"), ("All files", "*.*")]
        else:
            filetypes = [("XML config", "*.xml"), ("All files", "*.*")]
        selected = filedialog.askopenfilename(
            parent=self,
            title="Spice2x 파일 선택",
            initialdir=str(self.paths.root),
            filetypes=filetypes,
        )
        if selected:
            variable.set(self.paths.relative(Path(selected)))

    def _clear(self) -> None:
        for variable in (
            self.x86_var,
            self.x64_var,
            self.configurator_var,
            self.config_var,
            self.patch_config_var,
            self.service_url_var,
            self.card0_var,
        ):
            variable.set("")
        self.local_ea_var.set(False)

    def _save(self) -> None:
        settings = RuntimeSettings(
            spice_x86_executable=self.x86_var.get().strip(),
            spice_x64_executable=self.x64_var.get().strip(),
            spice_configurator=self.configurator_var.get().strip(),
            spice_config_path=self.config_var.get().strip(),
            spice_patch_manager_config_path=self.patch_config_var.get().strip(),
            spice_local_ea=self.local_ea_var.get(),
            spice_service_url=self.service_url_var.get().strip(),
            spice_card0=self.card0_var.get().strip(),
        )
        view_mode = self.VIEW_MODES.get(self.view_mode_var.get(), "thumbnail")
        if self.on_save(settings, view_mode):
            self.destroy()


class GameDialog(tk.Toplevel):
    def __init__(
        self,
        parent: ManagerApp,
        paths: PortablePaths,
        store: GameStore,
        detector: GameDetector,
        *,
        game: GameDefinition | None = None,
        duplicate: bool = False,
        on_save,
    ):
        super().__init__(parent)
        self.paths = paths
        self.store = store
        self.detector = detector
        self.original = None if duplicate else game
        self.duplicate = duplicate
        self.on_save = on_save
        self.candidates: list[DetectionCandidate] = []
        self.detected_dll = game.detected_dll if game else ""
        self.catalog = catalog_titles()
        self.catalog["other"] = "기타 아케이드 게임"
        self.type_labels = {f"{title} [{game_type}]": game_type for game_type, title in self.catalog.items()}
        self.launcher_labels = {
            "spice2x 공용 런타임": "spice2x",
            "일반 실행 파일": "direct",
        }

        self.title("게임 복제" if duplicate else ("게임 편집" if game else "게임 추가"))
        self.geometry("780x730")
        self.minsize(680, 650)
        self.configure(background=COLORS["background"])
        self.transient(parent)
        self.grab_set()
        self._build(game)

    def _build(self, game: GameDefinition | None) -> None:
        form = ttk.Frame(self, style="App.TFrame", padding=18)
        form.pack(fill=tk.BOTH, expand=True)
        form.columnconfigure(1, weight=1)

        heading = ttk.Frame(form, style="App.TFrame")
        heading.grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 14))
        dialog_title = "실행 프로필 복제" if self.duplicate else ("게임 편집" if game else "새 게임 등록")
        ttk.Label(heading, text=dialog_title, font=("Segoe UI Semibold", 18)).pack(anchor=tk.W)
        ttk.Label(heading, text="폴더를 선택하면 DLL과 폴더명을 분석해 기본값을 제안합니다.", foreground=COLORS["muted"]).pack(anchor=tk.W, pady=(2, 0))

        self.folder_var = tk.StringVar(value=str(self.paths.resolve(game.game_root)) if game else "")
        self.candidate_var = tk.StringVar()
        current_type = game.game_type if game else "iidx"
        current_launcher = game.launcher_type if game else "spice2x"
        current_type_label = next((label for label, value in self.type_labels.items() if value == current_type), "")
        current_launcher_label = next(
            (label for label, value in self.launcher_labels.items() if value == current_launcher),
            "spice2x 공용 런타임",
        )
        self.launcher_var = tk.StringVar(value=current_launcher_label)
        self.type_var = tk.StringVar(value=current_type_label)
        self.title_var = tk.StringVar(value=game.title if game else self.catalog.get(current_type, ""))
        self.version_var = tk.StringVar(value=game.version if game else "")
        self.arch_var = tk.StringVar(value=game.architecture if game else "x64")
        self.module_var = tk.StringVar(value=game.module_directory if game else "modules")
        self.thumbnail_var = tk.StringVar(value=game.thumbnail if game else "")
        self.executable_var = tk.StringVar(value=game.executable if game else "")
        self.working_directory_var = tk.StringVar(value=game.working_directory if game else ".")

        row = 1
        ttk.Label(form, text="실행 방식").grid(row=row, column=0, sticky=tk.W, pady=5)
        launcher_combo = ttk.Combobox(
            form,
            textvariable=self.launcher_var,
            values=list(self.launcher_labels),
            state="readonly",
        )
        launcher_combo.grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=8)
        launcher_combo.bind("<<ComboboxSelected>>", self._launcher_changed)
        row += 1
        ttk.Label(form, text="게임 폴더").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.folder_var).grid(row=row, column=1, sticky=tk.EW, padx=8)
        ttk.Button(form, text="찾기", command=self.browse_folder).grid(row=row, column=2)
        row += 1
        self.detect_label = ttk.Label(form, text="spice2x 감지 후보")
        self.detect_label.grid(row=row, column=0, sticky=tk.W, pady=5)
        self.candidate_combo = ttk.Combobox(form, textvariable=self.candidate_var, state="readonly")
        self.candidate_combo.grid(row=row, column=1, sticky=tk.EW, padx=8)
        self.candidate_combo.bind("<<ComboboxSelected>>", self.apply_candidate)
        self.detect_button = ttk.Button(form, text="DLL 탐색", command=self.detect_folder)
        self.detect_button.grid(row=row, column=2)
        row += 1
        ttk.Label(form, text="게임 계열").grid(row=row, column=0, sticky=tk.W, pady=5)
        type_combo = ttk.Combobox(form, textvariable=self.type_var, values=list(self.type_labels), state="readonly")
        type_combo.grid(row=row, column=1, sticky=tk.EW, padx=8)
        type_combo.bind("<<ComboboxSelected>>", self.apply_type_defaults)
        ttk.Button(form, text="기본값", command=self.apply_type_defaults).grid(row=row, column=2)
        row += 1

        for label, variable in (("게임명", self.title_var), ("버전", self.version_var)):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=8)
            row += 1

        ttk.Label(form, text="아키텍처").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.arch_combo = ttk.Combobox(form, textvariable=self.arch_var, values=("x86", "x64"), state="readonly", width=10)
        self.arch_combo.grid(row=row, column=1, sticky=tk.W, padx=8)
        row += 1
        ttk.Label(form, text="모듈 폴더").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.module_entry = ttk.Entry(form, textvariable=self.module_var)
        self.module_entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=8)
        row += 1
        ttk.Label(form, text="실행 파일").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.executable_entry = ttk.Entry(form, textvariable=self.executable_var)
        self.executable_entry.grid(row=row, column=1, sticky=tk.EW, padx=8)
        self.executable_button = ttk.Button(form, text="찾기", command=self.browse_executable)
        self.executable_button.grid(row=row, column=2)
        row += 1
        ttk.Label(form, text="작업 폴더").grid(row=row, column=0, sticky=tk.W, pady=5)
        self.working_directory_entry = ttk.Entry(form, textvariable=self.working_directory_var)
        self.working_directory_entry.grid(row=row, column=1, columnspan=2, sticky=tk.EW, padx=8)
        row += 1
        ttk.Label(form, text="썸네일").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(form, textvariable=self.thumbnail_var).grid(row=row, column=1, sticky=tk.EW, padx=8)
        ttk.Button(form, text="찾기", command=self.browse_thumbnail).grid(row=row, column=2)
        row += 1
        self.advanced_options = AdvancedLaunchOptions(
            form,
            self.paths,
            self._folder_path,
            game,
            dialog_width=780,
            collapsed_height=730,
            expanded_height=890,
        )
        self.advanced_options.grid(row=row)
        row += 2
        self.info_var = tk.StringVar(value="게임 폴더를 선택하고 DLL 탐색을 누르세요.")
        ttk.Label(form, textvariable=self.info_var, foreground="#555", wraplength=650).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 5)
        )
        row += 1
        buttons = ttk.Frame(form)
        buttons.grid(row=row, column=0, columnspan=3, sticky=tk.E, pady=(10, 0))
        ttk.Button(buttons, text="취소", style="Ghost.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(7, 0))
        ttk.Button(buttons, text="저장", style="Primary.TButton", command=self.save).pack(side=tk.RIGHT)
        self._launcher_changed()

    def browse_folder(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="게임 폴더 선택", initialdir=str(self.paths.root))
        if selected:
            self.folder_var.set(selected)
            if self.launcher_labels.get(self.launcher_var.get()) == "spice2x":
                self.detect_folder()
            else:
                self._suggest_direct_metadata(Path(selected))

    def browse_executable(self) -> None:
        try:
            folder = self._folder_path()
        except ValueError as error:
            messagebox.showerror("실행 파일 선택", str(error), parent=self)
            return
        selected = filedialog.askopenfilename(
            parent=self,
            title="게임 실행 파일 선택",
            initialdir=str(folder),
            filetypes=[("Windows executable", "*.exe"), ("All files", "*.*")],
        )
        if selected:
            self.executable_var.set(self.paths.relative(Path(selected), base=folder))
            self.info_var.set("실행 파일 아이콘을 기본 썸네일로 사용합니다. 별도 썸네일을 지정하면 그 이미지가 우선됩니다.")

    def _launcher_changed(self, _event=None) -> None:
        direct = self.launcher_labels.get(self.launcher_var.get()) == "direct"
        spice_state = "disabled" if direct else "readonly"
        entry_state = "normal" if direct else "disabled"
        self.candidate_combo.configure(state=spice_state)
        self.detect_button.configure(state=tk.DISABLED if direct else tk.NORMAL)
        self.arch_combo.configure(state=spice_state)
        self.module_entry.configure(state=tk.DISABLED if direct else tk.NORMAL)
        self.executable_entry.configure(state=entry_state)
        self.executable_button.configure(state=tk.NORMAL if direct else tk.DISABLED)
        self.working_directory_entry.configure(state=entry_state)
        if direct:
            other_label = next(label for label, value in self.type_labels.items() if value == "other")
            if not self.original or self.original.launcher_type != "direct":
                self.type_var.set(other_label)
            self.info_var.set("게임 폴더 내부의 EXE를 선택하세요. EXE 아이콘이 기본 썸네일로 표시됩니다.")
        else:
            self.info_var.set("게임 폴더를 선택하고 DLL 탐색을 누르세요.")

    def _suggest_direct_metadata(self, folder: Path) -> None:
        pretty = folder.name.replace("_", " ").replace("-", " ").strip()
        if not self.title_var.get().strip() or self.type_labels.get(self.type_var.get()) == "other":
            self.title_var.set(pretty)
        self.info_var.set("게임명과 버전을 확인하고 실행 파일을 선택하세요.")

    def browse_thumbnail(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="썸네일 선택",
            initialdir=str(self.paths.root),
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp *.bmp"), ("All files", "*.*")],
        )
        if selected:
            self.thumbnail_var.set(self.paths.relative(Path(selected)))

    def detect_folder(self) -> None:
        if self.launcher_labels.get(self.launcher_var.get()) != "spice2x":
            return
        try:
            folder = self._folder_path()
            if not folder.is_dir():
                raise FileNotFoundError(f"게임 폴더가 없습니다: {folder}")
            self.candidates = self.detector.detect(folder)
        except (OSError, ValueError) as error:
            messagebox.showerror("DLL 탐색 실패", str(error), parent=self)
            return

        labels = [self._candidate_label(item) for item in self.candidates]
        self.candidate_combo.configure(values=labels)
        if not self.candidates:
            self.candidate_var.set("")
            self.info_var.set("알려진 게임 DLL을 찾지 못했습니다. 게임 계열을 직접 선택하고 기본값을 적용할 수 있습니다.")
            return
        self.candidate_var.set(labels[0])
        self._apply_candidate_value(self.candidates[0])
        self.info_var.set(f"{len(self.candidates)}개 후보를 찾았습니다. 게임명과 버전을 확인한 뒤 필요하면 편집하세요.")

    def apply_candidate(self, _event=None) -> None:
        index = self.candidate_combo.current()
        if 0 <= index < len(self.candidates):
            self._apply_candidate_value(self.candidates[index])

    def _apply_candidate_value(self, candidate: DetectionCandidate) -> None:
        label = next((key for key, value in self.type_labels.items() if value == candidate.game_type), "")
        self.type_var.set(label)
        self.title_var.set(candidate.suggested_title)
        self.version_var.set(candidate.suggested_version)
        self.arch_var.set(candidate.architecture)
        self.module_var.set(candidate.module_directory)
        self.detected_dll = candidate.detected_dll
        self.folder_var.set(str(self.paths.resolve(candidate.game_root)))

    def apply_type_defaults(self, _event=None) -> None:
        game_type = self.type_labels.get(self.type_var.get())
        if not game_type:
            return
        try:
            folder = self._folder_path()
            candidate = self.detector.defaults_for(game_type, folder)
            self._apply_candidate_value(candidate)
            self.info_var.set("선택한 게임 계열의 기본값을 적용했습니다. 감지되지 않은 값은 실행 전에 확인하세요.")
        except (OSError, ValueError, KeyError) as error:
            self.title_var.set(self.catalog.get(game_type, game_type))
            self.info_var.set(str(error))

    def _folder_path(self) -> Path:
        value = self.folder_var.get().strip()
        if not value:
            raise ValueError("게임 폴더를 선택하세요.")
        path = Path(value)
        return path.resolve() if path.is_absolute() else self.paths.resolve(value)

    @staticmethod
    def _candidate_label(candidate: DetectionCandidate) -> str:
        version = f" {candidate.suggested_version}" if candidate.suggested_version else ""
        return f"{candidate.suggested_title}{version} · {candidate.detected_dll} · {candidate.architecture}"

    def save(self) -> None:
        try:
            folder = self._folder_path()
            if not folder.is_dir():
                raise FileNotFoundError(f"게임 폴더가 없습니다: {folder}")
            game_type = self.type_labels.get(self.type_var.get())
            if not game_type:
                raise ValueError("게임 계열을 선택하세요.")
            launcher_type = self.launcher_labels.get(self.launcher_var.get())
            if not launcher_type:
                raise ValueError("실행 방식을 선택하세요.")
            title = self.title_var.get().strip()
            version = self.version_var.get().strip()
            current_id = self.original.id if self.original else ""
            game_id = current_id or self.store.make_unique_id(title, version)
            arguments = self.advanced_options.arguments()
            game = GameDefinition(
                id=game_id,
                title=title,
                version=version,
                game_type=game_type,
                game_root=self.paths.relative(folder),
                module_directory=self.module_var.get().strip(),
                architecture=self.arch_var.get(),
                thumbnail=self.thumbnail_var.get().strip(),
                arguments=arguments,
                detected_dll=self.detected_dll,
                launcher_type=launcher_type,
                executable=self.executable_var.get().strip(),
                working_directory=self.working_directory_var.get().strip() or ".",
                run_as_admin=self.advanced_options.run_as_admin_var.get(),
                pre_launch_executable=self.advanced_options.pre_launch_var.get().strip(),
                post_exit_executable=self.advanced_options.post_exit_var.get().strip(),
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("저장 실패", str(error), parent=self)
            return
        if self.on_save(game):
            self.destroy()


def run(paths: PortablePaths | None = None) -> None:
    resolved_paths = paths or PortablePaths.discover()
    app = ManagerApp(resolved_paths)
    app.mainloop()
