"""Application controller: owns the Tk root, shared state, and screen navigation."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .dataset import Config, Pair, Progress, ScanResult, scan_pairs
from .taxonomy import Taxonomy, TaxonomyError, load_taxonomy


class AppController:
    def __init__(self, root: tk.Tk, app_dir: Path):
        self.root = root
        self.app_dir = app_dir
        self.config = Config(app_dir / "config.json")
        self.progress = Progress(app_dir / "progress.json")
        self.scan: ScanResult | None = None

        try:
            self.taxonomy: Taxonomy = load_taxonomy(app_dir / "lib" / "taxonomy.json")
        except TaxonomyError as exc:
            messagebox.showerror("Taxonomy error", str(exc))
            raise SystemExit(1) from exc

        self.root.title("Dogma Annotation Helper")
        self.root.geometry("1280x820")
        self.container = tk.Frame(self.root)
        self.container.pack(fill="both", expand=True)
        self._current = None

    # -- screen switching ------------------------------------------------ #
    def _swap(self, screen_factory) -> None:
        if self._current is not None:
            self._current.destroy()
        self._current = screen_factory(self.container, self)
        self._current.pack(fill="both", expand=True)

    def show_home(self) -> None:
        from .ui.home import HomeScreen

        self._swap(HomeScreen)

    def show_todo(self) -> None:
        from .ui.todo import TodoScreen

        self._swap(TodoScreen)

    def show_annotate(self, pair: Pair) -> None:
        from .ui.annotate import AnnotateScreen

        self._swap(lambda parent, ctrl: AnnotateScreen(parent, ctrl, pair))

    # -- actions --------------------------------------------------------- #
    def rescan(self) -> ScanResult:
        self.scan = scan_pairs(self.config.ann_dir, self.config.vid_dir)
        return self.scan
