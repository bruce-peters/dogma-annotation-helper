"""Reusable Tkinter widgets: scroll frame, tag picker, tag lists, object overlay."""

from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog, ttk

from PIL import Image, ImageTk

from ..taxonomy import Section

# Shared style constants.
RED = "#c0392b"
CHIP_BG = "#e8eef5"
CHIP_BAD_BG = "#f7d7d2"
POINT_PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
]


class ScrollFrame(ttk.Frame):
    """A vertically scrollable container. Add children to ``.body``."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Enter>", lambda e: self._bind_wheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_wheel())

    def _on_body_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _bind_wheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class TagPickerDialog(tk.Toplevel):
    """Modal searchable picker over a section's taxonomy. Sets ``self.result``."""

    def __init__(self, parent, section: Section, existing: set[str]):
        super().__init__(parent)
        self.title(f"Add tag — {section.label}")
        self.section = section
        self.existing = existing
        self.result: str | None = None
        # [(group_name, [(code, desc)])] with already-chosen tags removed.
        self._groups = [
            (name, [(c, d) for c, d in opts if c not in existing])
            for name, opts in section.grouped_options()
        ]

        self.transient(parent)
        self.geometry("560x520")

        self.query = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.query)
        entry.pack(fill="x", padx=8, pady=(8, 4))
        entry.bind("<KeyRelease>", lambda e: self._refresh())
        entry.bind("<Return>", lambda e: self._choose())
        entry.bind("<Down>", lambda e: self._focus_first())

        self.listbox = tk.Listbox(self, activestyle="dotbox")
        self.listbox.pack(fill="both", expand=True, padx=8, pady=4)
        self.listbox.bind("<Double-Button-1>", lambda e: self._choose())
        self.listbox.bind("<Return>", lambda e: self._choose())
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._show_desc())

        self.desc = ttk.Label(self, text="", wraplength=520, foreground="#555")
        self.desc.pack(fill="x", padx=8, pady=(0, 4))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text="Add", command=self._choose).pack(side="right")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="right", padx=4)

        # Per listbox line: the tag code, or None for a group header.
        self._line_codes: list[str | None] = []
        self._desc_by_code: dict[str, str] = {}
        self._refresh()
        entry.focus_set()
        self.grab_set()
        self.wait_window(self)

    def _refresh(self):
        q = self.query.get().strip().lower()
        self.listbox.delete(0, tk.END)
        self._line_codes = []
        self._desc_by_code = {}
        show_headers = len(self._groups) > 1 or (self._groups and self._groups[0][0])

        for name, opts in self._groups:
            matches = [
                (c, d) for c, d in opts
                if not q or q in c.lower() or q in d.lower()
            ]
            if not matches:
                continue
            if show_headers and name:
                self.listbox.insert(tk.END, f"— {name} —")
                self.listbox.itemconfig(tk.END, foreground="#1565c0")
                self._line_codes.append(None)
            for code, desc in matches:
                prefix = "    " if (show_headers and name) else ""
                self.listbox.insert(tk.END, f"{prefix}{code}  —  {desc}")
                self._line_codes.append(code)
                self._desc_by_code[code] = desc

        first = self._first_selectable()
        if first is not None:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(first)
            self._show_desc()

    def _first_selectable(self, start=0):
        for i in range(start, len(self._line_codes)):
            if self._line_codes[i] is not None:
                return i
        return None

    def _focus_first(self):
        first = self._first_selectable()
        if first is not None:
            self.listbox.focus_set()
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(first)
            self.listbox.see(first)

    def _show_desc(self):
        sel = self.listbox.curselection()
        if sel:
            code = self._line_codes[sel[0]]
            if code:
                self.desc.config(text=self._desc_by_code.get(code, ""))

    def _choose(self):
        sel = self.listbox.curselection()
        idx = sel[0] if sel else self._first_selectable()
        if idx is None:
            return
        code = self._line_codes[idx]
        if code is None:  # a header was selected; advance to the next tag
            nxt = self._first_selectable(idx + 1)
            if nxt is None:
                return
            code = self._line_codes[nxt]
        self.result = code
        self.destroy()


class _Chip(ttk.Frame):
    def __init__(self, parent, text: str, bad: bool, on_delete, tooltip: str = ""):
        super().__init__(parent)
        bg = CHIP_BAD_BG if bad else CHIP_BG
        fg = RED if bad else "#222"
        self.label = tk.Label(self, text=text, bg=bg, fg=fg, padx=6, pady=2)
        self.label.pack(side="left")
        close = tk.Label(self, text="×", bg=bg, fg=fg, padx=4, cursor="hand2")
        close.pack(side="left")
        close.bind("<Button-1>", lambda e: on_delete())
        if tooltip:
            _Tooltip(self.label, tooltip)


class _Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _e):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text, bg="#ffffe0", relief="solid", borderwidth=1,
            wraplength=320, justify="left", padx=4, pady=2,
        ).pack()

    def _hide(self, _e):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class SingleSelectWidget(ttk.Frame):
    """Combobox for a single-select section, with an unknown-value warning."""

    def __init__(self, parent, section: Section):
        super().__init__(parent)
        self.section = section
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text=section.label, font=("", 10, "bold")).pack(side="left")
        self.badge = tk.Label(header, text="", fg=RED, font=("", 9, "bold"))
        self.badge.pack(side="left", padx=6)

        self.var = tk.StringVar()
        values = [c for c, _ in section.options()]
        self.combo = ttk.Combobox(self, textvariable=self.var, values=values, state="normal")
        self.combo.pack(fill="x", pady=(2, 0))
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._update_badge())
        self.combo.bind("<KeyRelease>", lambda e: self._update_badge())

    def set_value(self, value):
        self.var.set(value or "")
        self._update_badge()

    def get_value(self) -> str:
        return self.var.get().strip()

    def has_unknown(self) -> bool:
        return bool(self.section.unknown([self.get_value()] if self.get_value() else []))

    def _update_badge(self):
        self.badge.config(text="⚠ not in taxonomy" if self.has_unknown() else "")


class TagListWidget(ttk.Frame):
    """Add/remove chip list for a multi-select section, with unknown flagging."""

    def __init__(self, parent, section: Section):
        super().__init__(parent)
        self.section = section
        self.values: list[str] = []

        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text=section.label, font=("", 10, "bold")).pack(side="left")
        self.badge = tk.Label(header, text="", fg=RED, font=("", 9, "bold"))
        self.badge.pack(side="left", padx=6)
        ttk.Button(header, text="+ Add", width=7, command=self._add).pack(side="right")

        self.chips = ttk.Frame(self)
        self.chips.pack(fill="x", pady=(2, 0))

    def set_values(self, values):
        self.values = list(values or [])
        self._render()

    def get_values(self) -> list[str]:
        return list(self.values)

    def has_unknown(self) -> bool:
        return bool(self.section.unknown(self.values))

    def _render(self):
        for child in self.chips.winfo_children():
            child.destroy()
        unknown = set(self.section.unknown(self.values))
        for value in self.values:
            bad = value in unknown
            tip = self.section.describe(value) or ("Not in taxonomy" if bad else "")
            chip = _Chip(
                self.chips, value, bad,
                on_delete=lambda v=value: self._remove(v), tooltip=tip,
            )
            chip.pack(side="left", padx=2, pady=2)
        self.badge.config(
            text=f"⚠ {len(unknown)} unknown" if unknown else ""
        )

    def _remove(self, value):
        if value in self.values:
            self.values.remove(value)
            self._render()
            self.event_generate("<<TagsChanged>>")

    def _add(self):
        if self.section.validated:
            dialog = TagPickerDialog(self, self.section, set(self.values))
            chosen = dialog.result
        else:
            chosen = simpledialog.askstring(
                f"Add tag — {self.section.label}", "Tag value:", parent=self
            )
            if chosen:
                chosen = chosen.strip()
        if chosen and chosen not in self.values:
            self.values.append(chosen)
            self._render()
            self.event_generate("<<TagsChanged>>")


def split_distance(meta: str) -> tuple[str, bool]:
    """Return (editable_value, had_prefix). Handles ``distance=4m`` style."""
    if isinstance(meta, str) and meta.startswith("distance="):
        return meta[len("distance="):], True
    return ("" if meta is None else str(meta)), False


class ObjectOverlay(ttk.Frame):
    """Frame image with colored detection points, plus an editable side list.

    ``objects`` are rows like ``[x, y, label, "distance=4m", ...]`` in original
    frame pixel coordinates. Editing a row's label/distance updates the canvas
    live. ``get_objects()`` rebuilds the rows, preserving x/y and any extra
    trailing elements.
    """

    MAX_W = 760
    MAX_H = 560
    COORD_SPACES = ("Video pixels", "Normalized 0-1", "Custom W×H")

    def __init__(self, parent, on_change=None, on_calibration=None,
                 swap_xy=False, coord_space="Video pixels",
                 ref_w=0.0, ref_h=0.0):
        super().__init__(parent)
        self.on_change = on_change            # annotation data changed (dirty)
        self.on_calibration = on_calibration  # display calibration changed (persist)
        self._rows: list[dict] = []
        self._photo = None
        self._disp_size = (1, 1)
        self._video_size = (1, 1)

        # Calibration state.
        self._swap = tk.BooleanVar(value=swap_xy)
        self._space = tk.StringVar(
            value=coord_space if coord_space in self.COORD_SPACES else self.COORD_SPACES[0])
        self._ref_w = tk.StringVar(value=str(ref_w or ""))
        self._ref_h = tk.StringVar(value=str(ref_h or ""))

        # Calibration strip (top, spans full width).
        strip = ttk.Frame(self)
        strip.pack(fill="x", pady=(0, 4))
        ttk.Checkbutton(strip, text="Swap X/Y", variable=self._swap,
                        command=self._calibrate).pack(side="left")
        ttk.Label(strip, text="  Coord space:").pack(side="left")
        combo = ttk.Combobox(strip, textvariable=self._space, values=self.COORD_SPACES,
                             state="readonly", width=14)
        combo.pack(side="left", padx=4)
        combo.bind("<<ComboboxSelected>>", lambda e: self._calibrate())
        self._custom = ttk.Frame(strip)
        self._custom.pack(side="left")
        ttk.Label(self._custom, text="ref").pack(side="left")
        ttk.Entry(self._custom, textvariable=self._ref_w, width=6).pack(side="left", padx=2)
        ttk.Label(self._custom, text="×").pack(side="left")
        ttk.Entry(self._custom, textvariable=self._ref_h, width=6).pack(side="left", padx=2)
        ttk.Button(self._custom, text="apply", width=6,
                   command=self._calibrate).pack(side="left", padx=2)

        content = ttk.Frame(self)
        content.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(content, bg="#111", highlightthickness=0,
                                width=self.MAX_W, height=self.MAX_H)
        self.canvas.pack(side="left", anchor="n")

        side = ttk.Frame(content)
        side.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ttk.Label(side, text="Detected objects", font=("", 10, "bold")).pack(anchor="w")
        self._list = ScrollFrame(side)
        self._list.pack(fill="both", expand=True)
        self._sync_custom_visibility()

    def calibration(self) -> dict:
        """Current display calibration (for persistence)."""
        return {
            "swap_xy": self._swap.get(),
            "coord_space": self._space.get(),
            "ref_w": self._float(self._ref_w.get()),
            "ref_h": self._float(self._ref_h.get()),
        }

    @staticmethod
    def _float(text, default=0.0):
        try:
            return float(text)
        except (TypeError, ValueError):
            return default

    def _sync_custom_visibility(self):
        if self._space.get() == "Custom W×H":
            self._custom.pack(side="left")
        else:
            self._custom.pack_forget()

    def _calibrate(self):
        """Recompute overlay positions after a calibration change."""
        self._sync_custom_visibility()
        self._redraw_canvas()
        if self.on_calibration:
            self.on_calibration(self.calibration())

    def _ref_size(self):
        """Reference resolution the stored coordinates are expressed in."""
        space = self._space.get()
        if space == "Normalized 0-1":
            return 1.0, 1.0
        if space == "Custom W×H":
            w = self._float(self._ref_w.get()) or self._video_size[0]
            h = self._float(self._ref_h.get()) or self._video_size[1]
            return max(w, 1e-9), max(h, 1e-9)
        return self._video_size  # Video pixels

    def set_frame(self, image: Image.Image, orig_size, objects):
        """Display ``image`` (a PIL frame) and overlay ``objects``."""
        self._video_size = (max(orig_size[0], 1), max(orig_size[1], 1))
        disp = image.copy()
        disp.thumbnail((self.MAX_W, self.MAX_H), Image.LANCZOS)
        self._disp_size = (disp.width, disp.height)
        self._photo = ImageTk.PhotoImage(disp)
        self.canvas.config(width=disp.width, height=disp.height)

        # Normalise rows into editable dicts.
        self._rows = []
        for obj in objects or []:
            obj = list(obj)
            x = obj[0] if len(obj) > 0 else 0
            y = obj[1] if len(obj) > 1 else 0
            label = obj[2] if len(obj) > 2 else ""
            meta = obj[3] if len(obj) > 3 else ""
            extra = obj[4:]
            dist, had_prefix = split_distance(meta)
            self._rows.append({
                "x": x, "y": y,
                "label_var": tk.StringVar(value=str(label)),
                "dist_var": tk.StringVar(value=dist),
                "had_prefix": had_prefix,
                "raw_meta": meta,
                "extra": extra,
                "color": POINT_PALETTE[len(self._rows) % len(POINT_PALETTE)],
            })
        self._render_list()
        self._redraw_canvas()

    def get_objects(self) -> list[list]:
        out = []
        for r in self._rows:
            label = r["label_var"].get()
            dist = r["dist_var"].get().strip()
            if r["had_prefix"]:
                meta = f"distance={dist}"
            else:
                meta = dist if dist else r["raw_meta"]
            out.append([r["x"], r["y"], label, meta, *r["extra"]])
        return out

    def _disp_xy(self, r):
        x, y = self._float(r["x"]), self._float(r["y"])
        if self._swap.get():
            x, y = y, x
        ref_w, ref_h = self._ref_size()
        disp_w, disp_h = self._disp_size
        return x * disp_w / ref_w, y * disp_h / ref_h

    def _redraw_canvas(self):
        self.canvas.delete("all")
        if self._photo is not None:
            self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        for r in self._rows:
            x, y = self._disp_xy(r)
            color = r["color"]
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5,
                                    fill=color, outline="white", width=2)
            label = r["label_var"].get()
            dist = r["dist_var"].get().strip()
            text = f"{label}  {dist}".strip()
            self.canvas.create_text(x + 8, y, anchor="w", text=text,
                                    fill=color, font=("", 9, "bold"))
            self.canvas.create_text(x + 8 + 1, y + 1, anchor="w", text=text,
                                    fill="black", font=("", 9, "bold"))
            # redraw colored text on top of the black shadow
            self.canvas.create_text(x + 8, y, anchor="w", text=text,
                                    fill=color, font=("", 9, "bold"))

    def _render_list(self):
        for child in self._list.body.winfo_children():
            child.destroy()
        if not self._rows:
            ttk.Label(self._list.body, text="(none)", foreground="#888").pack(anchor="w")
            return
        header = ttk.Frame(self._list.body)
        header.pack(fill="x", pady=(0, 2))
        for text, w in (("xy", 9), ("label", 16), ("dist", 8), ("", 3)):
            ttk.Label(header, text=text, width=w, font=("", 8, "bold")).pack(side="left")

        for i, r in enumerate(self._rows):
            row = ttk.Frame(self._list.body)
            row.pack(fill="x", pady=1)
            swatch = tk.Label(row, text="  ", bg=r["color"])
            swatch.pack(side="left", padx=(0, 2))
            ttk.Label(row, text=f"{r['x']},{r['y']}", width=8).pack(side="left")
            label_entry = ttk.Entry(row, textvariable=r["label_var"], width=16)
            label_entry.pack(side="left")
            dist_entry = ttk.Entry(row, textvariable=r["dist_var"], width=8)
            dist_entry.pack(side="left", padx=2)
            r["label_var"].trace_add("write", lambda *a: self._on_edit())
            r["dist_var"].trace_add("write", lambda *a: self._on_edit())
            ttk.Button(row, text="×", width=2,
                       command=lambda idx=i: self._delete(idx)).pack(side="left")

    def _on_edit(self):
        self._redraw_canvas()
        if self.on_change:
            self.on_change()

    def _delete(self, index):
        if 0 <= index < len(self._rows):
            del self._rows[index]
            # reassign palette colors so they stay distinct after deletion
            for j, r in enumerate(self._rows):
                r["color"] = POINT_PALETTE[j % len(POINT_PALETTE)]
            self._render_list()
            self._redraw_canvas()
            if self.on_change:
                self.on_change()
