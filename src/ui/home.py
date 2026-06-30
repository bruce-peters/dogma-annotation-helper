"""Home / setup screen: choose the two folders and scan for pairs."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class HomeScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=24)
        self.controller = controller

        ttk.Label(self, text="Dogma Annotation Helper",
                  font=("", 18, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text="Point to the annotations folder ([#]_annotation.json) and the "
                 "videos folder ([#].mp4).",
            foreground="#555",
        ).pack(anchor="w", pady=(2, 16))

        self.ann_var = tk.StringVar(value=controller.config.ann_dir)
        self.vid_var = tk.StringVar(value=controller.config.vid_dir)

        self._folder_row("Annotations folder", self.ann_var)
        self._folder_row("Videos folder", self.vid_var)

        ttk.Button(self, text="Scan / Load", command=self._scan).pack(anchor="w", pady=12)

        self.summary = ttk.Label(self, text="", foreground="#333", justify="left")
        self.summary.pack(anchor="w", pady=8)

        if controller.config.ann_dir and controller.config.vid_dir:
            self._scan(navigate=False)

    def _folder_row(self, label, var):
        row = ttk.Frame(self)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text=label, width=18).pack(side="left")
        ttk.Entry(row, textvariable=var, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…",
                   command=lambda: self._browse(var)).pack(side="left", padx=4)

    def _browse(self, var):
        chosen = filedialog.askdirectory(initialdir=var.get() or ".")
        if chosen:
            var.set(chosen)

    def _scan(self, navigate=True):
        ann, vid = self.ann_var.get().strip(), self.vid_var.get().strip()
        if not ann or not vid:
            if navigate:
                messagebox.showwarning("Missing folders", "Choose both folders first.")
            return
        self.controller.config.ann_dir = ann
        self.controller.config.vid_dir = vid
        self.controller.config.save()
        result = self.controller.rescan()
        n_complete = len(result.complete_pairs)
        self.summary.config(
            text=(
                f"Matched pairs: {n_complete}\n"
                f"Orphan annotations (no video): {len(result.orphan_annotations)}\n"
                f"Orphan videos (no annotation): {len(result.orphan_videos)}"
            )
        )
        if navigate:
            if not result.pairs:
                messagebox.showinfo("Nothing found", "No matching files in those folders.")
                return
            self.controller.show_todo()
