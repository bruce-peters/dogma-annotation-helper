"""Todo / overview screen: list pairs with done + validation status."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..dataset import get_frames, load_annotation


def _pair_status(controller, pair):
    """Return (frame_count, has_unknown, error) for a complete pair."""
    if not pair.complete:
        return 0, False, "missing file"
    try:
        doc = load_annotation(pair.ann_path)
    except Exception:  # noqa: BLE001 - corrupt JSON is reported, not fatal
        return 0, False, "corrupt JSON"
    frames = get_frames(doc)
    has_unknown = False
    for frame in frames:
        for section in controller.taxonomy:
            if not section.validated:
                continue
            if section.unknown(frame.get(section.name)):
                has_unknown = True
                break
        if has_unknown:
            break
    return len(frames), has_unknown, ""


class TodoScreen(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, padding=16)
        self.controller = controller

        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Button(top, text="← Setup", command=controller.show_home).pack(side="left")
        ttk.Label(top, text="Video / annotation pairs",
                  font=("", 14, "bold")).pack(side="left", padx=12)

        self.filter_var = tk.StringVar(value="All")
        for text in ("All", "Done", "Not done"):
            ttk.Radiobutton(top, text=text, value=text, variable=self.filter_var,
                            command=self._render).pack(side="left", padx=2)

        cols = ("id", "status", "frames", "validation", "reviewed")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22)
        for col, text, width in (
            ("id", "#", 60), ("status", "Status", 110), ("frames", "Frames", 80),
            ("validation", "Validation", 160), ("reviewed", "Last reviewed", 200),
        ):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w")
        self.tree.tag_configure("done", foreground="#2e7d32")
        self.tree.tag_configure("bad", foreground="#c0392b")
        self.tree.pack(fill="both", expand=True, pady=8)
        self.tree.bind("<Double-Button-1>", self._open)

        self._rows: dict[str, int] = {}
        self._render()

    def _render(self):
        self.tree.delete(*self.tree.get_children())
        self._rows.clear()
        scan = self.controller.scan
        if scan is None:
            return
        flt = self.filter_var.get()
        for pair in scan.sorted_pairs:
            done = self.controller.progress.is_done(pair.pair_id)
            if flt == "Done" and not done:
                continue
            if flt == "Not done" and done:
                continue
            count, has_unknown, error = _pair_status(self.controller, pair)
            status = "Done" if done else ("— " if pair.complete else "Incomplete")
            if error:
                validation = f"⚠ {error}"
            elif has_unknown:
                validation = "⚠ unknown tags"
            else:
                validation = "OK" if pair.complete else "—"
            tags = []
            if done:
                tags.append("done")
            if has_unknown or error:
                tags.append("bad")
            iid = self.tree.insert(
                "", "end",
                values=(
                    pair.pair_id, status, count or "—", validation,
                    self.controller.progress.last_reviewed(pair.pair_id) or "—",
                ),
                tags=tuple(tags),
            )
            self._rows[iid] = pair.pair_id

    def _open(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        pair_id = self._rows.get(sel[0])
        pair = self.controller.scan.pairs.get(pair_id)
        if pair and pair.complete:
            self.controller.show_annotate(pair)
