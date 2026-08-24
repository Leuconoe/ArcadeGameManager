from __future__ import annotations

import json
import logging
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .bat_converter import BatConverter
from .catalog import SIGNATURE_BY_ID, catalog_titles
from .detector import GameDetector
from .launcher import GameLauncher
from .models import DetectionCandidate, GameDefinition
from .paths import PortablePaths
from .store import GameStore
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


class ManagerApp(tk.Tk):
    def __init__(self, paths: PortablePaths):
        super().__init__()
        self.paths = paths
        self.store = GameStore(paths)
        self.detector = GameDetector(paths)
        self.launcher = GameLauncher(paths)
        self.bat_converter = BatConverter(paths.root)
        self.games: dict[str, GameDefinition] = {}
        self.validation_errors: dict[str, str] = {}
        self.library_images: dict[str, tk.PhotoImage] = {}
        self.grid_images: dict[str, tk.PhotoImage] = {}
        self.grid_cards: dict[str, tk.Frame] = {}
        self.selected_game_key = ""
        self.view_mode = self._load_view_mode()
        self._grid_columns = 0
        self._grid_resize_job: str | None = None

        self.title("Arcade Game Manager")
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

    def _build_ui(self) -> None:
        shell = ttk.Frame(self, style="App.TFrame", padding=(18, 16, 18, 10))
        shell.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(shell, style="Surface.TFrame", padding=(20, 16))
        header.pack(fill=tk.X, pady=(0, 10))
        badge = tk.Label(header, text="AG", bg=COLORS["accent"], fg="#FFFFFF", font=("Segoe UI Black", 14), width=3, height=2)
        badge.pack(side=tk.LEFT, padx=(0, 13))
        brand = ttk.Frame(header, style="Surface.TFrame")
        brand.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(brand, text="ARCADE GAME MANAGER", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(brand, text="One library. Multiple runtimes. Fully portable.", style="Subtitle.TLabel").pack(anchor=tk.W, pady=(1, 0))

        runtime_ready = all(
            (self.paths.root / "spice2x" / name).is_file()
            for name in ("spice.exe", "spice64.exe", "spicecfg.exe", "spicetools.xml")
        )
        runtime_text = "●  SPICE2X READY" if runtime_ready else "●  SPICE2X OPTIONAL"
        runtime_style = "Success.TLabel" if runtime_ready else "Error.TLabel"
        self.runtime_label = ttk.Label(header, text=runtime_text, style=runtime_style)
        self.runtime_label.pack(side=tk.RIGHT, padx=(12, 0))

        toolbar = ttk.Frame(shell, style="Surface.TFrame", padding=(14, 11))
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(toolbar, text="+  게임 추가", style="Primary.TButton", command=self.add_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="게임 실행", style="Launch.TButton", command=self.launch_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="편집", style="Ghost.TButton", command=self.edit_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="복제", style="Ghost.TButton", command=self.duplicate_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="런타임 설정", style="Ghost.TButton", command=self.configure_game).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="Spice BAT 변환", style="Ghost.TButton", command=self.convert_bat).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Button(toolbar, text="삭제", style="Danger.TButton", command=self.delete_game).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="새로고침", style="Ghost.TButton", command=self.refresh).pack(side=tk.RIGHT)

        content = ttk.Frame(shell, style="Card.TFrame")
        content.pack(fill=tk.BOTH, expand=True)

        list_frame = ttk.Frame(content, style="Card.TFrame", padding=(14, 12))
        list_frame.pack(fill=tk.BOTH, expand=True)

        list_header = ttk.Frame(list_frame, style="Surface.TFrame")
        list_header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(list_header, text="GAME LIBRARY", style="Section.TLabel").pack(side=tk.LEFT)
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

        self.status_var = tk.StringVar(value=f"Portable root: {self.paths.root}")
        status = ttk.Frame(self, style="Surface.TFrame", padding=(18, 7))
        status.pack(fill=tk.X)
        ttk.Label(status, text="●", style="Surface.TLabel", foreground=COLORS["accent"]).pack(side=tk.LEFT, padx=(0, 7))
        ttk.Label(status, textvariable=self.status_var, style="Status.TLabel", anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(status, text="DOUBLE-CLICK TO LAUNCH", style="Status.TLabel").pack(side=tk.RIGHT)

    def refresh(self) -> None:
        selected = self.selected_game_id()
        try:
            loaded = self.store.load_all()
        except ValueError as error:
            messagebox.showerror("설정 오류", str(error), parent=self)
            return
        self.games = {game.id: game for game in loaded}
        self.validation_errors = {game.id: self.launcher.validation_error(game) for game in loaded}
        self.library_images.clear()
        self.tree.delete(*self.tree.get_children())
        titles = catalog_titles()
        for index, game in enumerate(loaded):
            thumbnail = self._library_thumbnail(game)
            self.library_images[game.id] = thumbnail
            self.tree.insert(
                "",
                tk.END,
                iid=game.id,
                text="",
                image=thumbnail,
                values=(
                    "● 실행 가능" if not self.validation_errors[game.id] else "● 확인 필요",
                    game.title,
                    game.version,
                    titles.get(game.game_type, game.game_type),
                    game.game_root,
                ),
                tags=("invalid" if self.validation_errors[game.id] else ("even" if index % 2 == 0 else "odd"),),
            )
        self.tree.tag_configure("even", background=COLORS["surface"])
        self.tree.tag_configure("odd", background=COLORS["surface_alt"])
        self.tree.tag_configure("invalid", foreground=COLORS["danger"], background="#FFF4F6")
        self._render_thumbnail_grid(force=True)
        if selected and selected in self.games:
            self._select_game(selected)
        elif loaded:
            self._select_game(loaded[0].id)
        else:
            self._select_game("")
        self.game_count_var.set(f"{len(loaded)} GAME" + ("" if len(loaded) == 1 else "S"))
        self._restore_library_status()

    def selected_game_id(self) -> str:
        return self.selected_game_key

    def selected_game(self) -> GameDefinition | None:
        return self.games.get(self.selected_game_id())

    def _library_thumbnail(self, game: GameDefinition) -> tk.PhotoImage:
        if game.thumbnail:
            try:
                return load_thumbnail(self.paths.resolve(game.thumbnail), max_size=(96, 68))
            except (tk.TclError, OSError, ValueError):
                pass
        if game.launcher_type == "direct" and game.executable:
            try:
                executable = self.paths.resolve(game.executable, base=self.paths.resolve(game.game_root))
                return load_executable_icon(executable, max_size=(68, 68), canvas_size=(96, 68))
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
                return load_executable_icon(executable, max_size=(112, 112), canvas_size=(220, 132))
            except (tk.TclError, OSError, ValueError):
                pass
        image = tk.PhotoImage(width=220, height=132)
        image.put(COLORS["surface_alt"], to=(0, 0, 220, 132))
        return image

    def _load_view_mode(self) -> str:
        settings_path = self.paths.root / "data" / "ui.json"
        try:
            value = json.loads(settings_path.read_text(encoding="utf-8")).get("viewMode")
            return value if value in {"thumbnail", "list"} else "thumbnail"
        except (OSError, ValueError, TypeError):
            return "thumbnail"

    def _save_view_mode(self) -> None:
        settings_path = self.paths.root / "data" / "ui.json"
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                json.dumps({"viewMode": self.view_mode}, ensure_ascii=False, indent=2) + "\n",
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
            self._save_view_mode()

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
        invalid_count = sum(bool(error) for error in self.validation_errors.values())
        summary = f"확인 필요 {invalid_count}개" if invalid_count else "모두 실행 가능"
        self.status_var.set(f"게임 {len(self.games)}개 · {summary} · Portable root: {self.paths.root}")

    def _select_game(self, game_id: str, *, sync_tree: bool = True) -> None:
        self.selected_game_key = game_id if game_id in self.games else ""
        if sync_tree:
            current = self.tree.selection()
            if self.selected_game_key and current != (self.selected_game_key,):
                self.tree.selection_set(self.selected_game_key)
                self.tree.see(self.selected_game_key)
            elif not self.selected_game_key and current:
                self.tree.selection_remove(*current)
        for card_id, card in self.grid_cards.items():
            selected = card_id == self.selected_game_key
            card.configure(
                highlightbackground=COLORS["accent"] if selected else COLORS["border"],
                highlightcolor=COLORS["accent"] if selected else COLORS["border"],
                highlightthickness=2 if selected else 1,
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
        games = list(self.games.values())
        for row_start in range(0, len(games), columns):
            row_frame = tk.Frame(self.thumbnail_grid, background=COLORS["surface"])
            row_frame.pack(fill=tk.X)
            centered_row = tk.Frame(row_frame, background=COLORS["surface"])
            centered_row.pack(anchor=tk.CENTER)
            for game in games[row_start : row_start + columns]:
                self._build_thumbnail_card(centered_row, game, titles)
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
        summary = " · ".join(item for item in (game.version, titles.get(game.game_type, game.game_type)) if item)
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
        status_label = tk.Label(
                card,
                text="● 실행 가능" if not error else "● 확인 필요",
                background=COLORS["surface"],
                foreground=COLORS["success"] if not error else COLORS["danger"],
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

    def edit_game(self) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("게임 편집", "편집할 게임을 선택하세요.", parent=self)
            return
        GameDialog(self, self.paths, self.store, self.detector, game=game, on_save=self._save_game)

    def duplicate_game(self) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("게임 복제", "복제할 게임을 선택하세요.", parent=self)
            return
        GameDialog(
            self,
            self.paths,
            self.store,
            self.detector,
            game=game,
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
        if not messagebox.askyesno("게임 삭제", f"'{game.title}' 등록을 삭제할까요?\n게임 파일은 삭제되지 않습니다.", parent=self):
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

    def _run_selected(self, *, configure: bool) -> None:
        game = self.selected_game()
        if not game:
            messagebox.showinfo("실행", "게임을 선택하세요.", parent=self)
            return
        try:
            plan = self.launcher.plan(game, configure=configure)
            self.launcher.launch(game, configure=configure)
            action = "설정 실행" if configure else "게임 실행"
            self.status_var.set(f"{action}: {game.title} · {subprocess.list2cmdline(plan.command)}")
        except (OSError, ValueError) as error:
            messagebox.showerror("실행 실패", str(error), parent=self)

    def convert_bat(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="변환할 기존 BAT 선택",
            filetypes=[("Batch file", "*.bat"), ("All files", "*.*")],
        )
        if not selected:
            return
        try:
            conversion = self.bat_converter.preview(Path(selected))
        except OSError as error:
            messagebox.showerror("BAT 읽기 실패", str(error), parent=self)
            return
        if conversion.replacements == 0:
            messagebox.showinfo("BAT 경로 변환", "변환할 spice 실행 파일 경로를 찾지 못했습니다.", parent=self)
            return

        PreviewDialog(self, conversion.converted_text, conversion.replacements, lambda: self._apply_bat(conversion))

    def _apply_bat(self, conversion) -> None:
        try:
            backup = self.bat_converter.apply(conversion)
        except (OSError, ValueError) as error:
            messagebox.showerror("BAT 변환 실패", str(error), parent=self)
            return
        messagebox.showinfo("BAT 변환 완료", f"spice 경로를 상대경로로 변경했습니다.\n백업: {backup}", parent=self)
        self.status_var.set(f"BAT 변환 완료: {conversion.path}")


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
        ttk.Label(form, text="추가 인자\n(한 줄에 하나)").grid(row=row, column=0, sticky=tk.NW, pady=5)
        self.arguments_text = tk.Text(
            form,
            height=7,
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
        self.arguments_text.grid(row=row, column=1, columnspan=2, sticky=tk.NSEW, padx=8)
        form.rowconfigure(row, weight=1)
        if game:
            self.arguments_text.insert("1.0", "\n".join(game.arguments))
        row += 1
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
            arguments = [line.strip() for line in self.arguments_text.get("1.0", tk.END).splitlines() if line.strip()]
            game = GameDefinition(
                id=game_id,
                title=title,
                version=version,
                game_type=game_type,
                game_root=self.paths.relative(folder),
                module_directory=self.module_var.get().strip() or ".",
                architecture=self.arch_var.get(),
                thumbnail=self.thumbnail_var.get().strip(),
                arguments=arguments,
                detected_dll=self.detected_dll,
                launcher_type=launcher_type,
                executable=self.executable_var.get().strip(),
                working_directory=self.working_directory_var.get().strip() or ".",
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("저장 실패", str(error), parent=self)
            return
        if self.on_save(game):
            self.destroy()


class PreviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, text: str, replacements: int, on_apply):
        super().__init__(parent)
        self.title("BAT 상대경로 변환 미리보기")
        self.geometry("850x560")
        self.configure(background=COLORS["background"])
        self.transient(parent)
        self.grab_set()

        header = ttk.Frame(self, style="Surface.TFrame", padding=(16, 13))
        header.pack(fill=tk.X, padx=14, pady=(14, 8))
        ttk.Label(header, text="BAT 변환 미리보기", style="GameTitle.TLabel").pack(anchor=tk.W)
        ttk.Label(header, text=f"spice 실행 경로 {replacements}곳을 변경합니다. 다른 명령과 인자는 유지됩니다.", style="Muted.TLabel").pack(anchor=tk.W, pady=(3, 0))
        editor = tk.Text(
            self,
            wrap=tk.NONE,
            background=COLORS["surface"],
            foreground=COLORS["text"],
            insertbackground=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=12,
            font=("Cascadia Mono", 9),
        )
        x_scroll = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=editor.xview)
        y_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=editor.yview, style="Dark.Vertical.TScrollbar")
        editor.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        editor.insert("1.0", text)
        editor.configure(state=tk.DISABLED)
        editor.pack(fill=tk.BOTH, expand=True, padx=10)
        x_scroll.pack(fill=tk.X, padx=10)
        y_scroll.place(relx=1.0, rely=0.08, relheight=0.82, anchor=tk.NE)
        buttons = ttk.Frame(self, style="App.TFrame", padding=10)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="취소", style="Ghost.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(7, 0))

        def apply_and_close() -> None:
            on_apply()
            self.destroy()

        ttk.Button(buttons, text="백업 후 적용", style="Primary.TButton", command=apply_and_close).pack(side=tk.RIGHT)


def run(paths: PortablePaths | None = None) -> None:
    resolved_paths = paths or PortablePaths.discover()
    app = ManagerApp(resolved_paths)
    app.mainloop()
