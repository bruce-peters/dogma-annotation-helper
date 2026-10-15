"""Annotate screen: frame-by-frame review of one video/annotation pair."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from ..dataset import get_frames, load_annotation, save_annotation
from ..video import FrameSource, VideoError
from .widgets import ObjectOverlay, ScrollFrame, SingleSelectWidget, TagListWidget

# Fields handled outside the taxonomy-driven section widgets.
SPECIAL_FIELDS = {"objects_detected", "description", "transition", "frame_number", "timestamp"}


class AnnotateScreen(ttk.Frame):
    def __init__(self, parent, controller, pair):
        super().__init__(parent)
        self.controller = controller
        self.pair = pair
        self.index = 0
        self.dirty = False
        self.section_widgets: dict[str, object] = {}

        # Error paths below go back to the Todo screen *after* this constructor
        # returns: calling show_todo() directly from inside the controller's
        # _swap() would leave both this half-built screen and the new Todo
        # screen packed in the container.
        try:
            self.doc = load_annotation(pair.ann_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Cannot open", f"Failed to read annotation:\n{exc}")
            controller.root.after_idle(controller.show_todo)
            return
        self.frames = get_frames(self.doc)
        if not self.frames:
            messagebox.showinfo("Empty", "This annotation has no frames.")
            controller.root.after_idle(controller.show_todo)
            return

        try:
            self.video = FrameSource(pair.vid_path)
            # FrameSource opens lazily; open it now so a missing or unreadable
            # video is reported here instead of escaping from _load_frame().
            self.video.frame_count
        except VideoError as exc:
            messagebox.showerror("Video error", str(exc))
            controller.root.after_idle(controller.show_todo)
            return

        self._build_ui()
        self._load_frame(0)
        self._bind_shortcuts()

    # ------------------------------------------------------------------ UI #
    def _build_ui(self):
        # --- All controls live in a top toolbar (two rows). --------------- #
        toolbar = ttk.Frame(self, padding=(8, 6))
        toolbar.pack(fill="x")

        actions = ttk.Frame(toolbar)
        actions.pack(fill="x")
        ttk.Button(actions, text="← Todo", command=self._back).pack(side="left")
        self.title_label = ttk.Label(actions, text="", font=("", 12, "bold"))
        self.title_label.pack(side="left", padx=12)
        ttk.Button(actions, text="Mark pair as done",
                   command=self._mark_done).pack(side="right")
        ttk.Button(actions, text="Save (Ctrl+S)",
                   command=self._save).pack(side="right", padx=6)

        nav = ttk.Frame(toolbar)
        nav.pack(fill="x", pady=(6, 0))
        ttk.Button(nav, text="◀ Prev", command=self._prev).pack(side="left")
        ttk.Button(nav, text="Next ▶", command=self._next).pack(side="left", padx=4)
        self.frame_label = ttk.Label(nav, text="")
        self.frame_label.pack(side="left", padx=12)
        self.slider = ttk.Scale(nav, from_=0, to=max(len(self.frames) - 1, 0),
                                orient="horizontal", command=self._on_slider)
        self.slider.pack(side="left", fill="x", expand=True, padx=8)

        ttk.Label(nav, text="Frame mapping:").pack(side="left", padx=(8, 2))
        self.mapping_var = tk.StringVar(value=self.controller.config.frame_mapping)
        mapping = ttk.Combobox(
            nav, textvariable=self.mapping_var, state="readonly", width=14,
            values=("Auto", "By frame_number", "Sequential", "Proportional"))
        mapping.pack(side="left")
        mapping.bind("<<ComboboxSelected>>", self._on_mapping_change)

        ttk.Separator(self, orient="horizontal").pack(fill="x")

        # --- Resizable split: frame overlay | tags column. --------------- #
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, padding=8)
        cal = self.controller.config.calibration
        self.overlay = ObjectOverlay(
            left,
            on_change=self._mark_dirty,
            on_calibration=self._save_calibration,
            swap_xy=bool(cal.get("swap_xy", False)),
            coord_space=cal.get("coord_space", "Video pixels"),
            ref_w=cal.get("ref_w", 0.0),
            ref_h=cal.get("ref_h", 0.0),
        )
        self.overlay.pack(fill="both", expand=True)
        body.add(left, weight=3)

        right = ScrollFrame(body)
        body.add(right, weight=2)
        panel = ttk.Frame(right.body, padding=10)
        panel.pack(fill="both", expand=True)

        for section in self.controller.taxonomy:
            if section.is_multi:
                w = TagListWidget(panel, section)
                w.bind("<<TagsChanged>>", self._mark_dirty)
            else:
                w = SingleSelectWidget(panel, section)
                w.combo.bind("<<ComboboxSelected>>", self._mark_dirty, add=True)
                w.combo.bind("<KeyRelease>", self._mark_dirty, add=True)
            w.pack(fill="x", pady=6)
            self.section_widgets[section.name] = w

        ttk.Separator(panel).pack(fill="x", pady=6)
        ttk.Label(panel, text="Description", font=("", 10, "bold")).pack(anchor="w")
        self.desc_text = tk.Text(panel, height=5, wrap="word")
        self.desc_text.pack(fill="x", pady=(2, 6))
        self.desc_text.bind("<KeyRelease>", self._mark_dirty)

        ttk.Label(panel, text="Transition (read-only)",
                  font=("", 10, "bold")).pack(anchor="w")
        self.trans_text = tk.Text(panel, height=6, wrap="word", state="disabled",
                                  background="#f4f4f4")
        self.trans_text.pack(fill="x", pady=(2, 6))

    def _bind_shortcuts(self):
        root = self.winfo_toplevel()
        root.bind("<Left>", lambda e: self._prev())
        root.bind("<Right>", lambda e: self._next())
        root.bind("<Control-s>", lambda e: self._save())

    # ----------------------------------------------------------- frame nav #
    def _load_frame(self, index):
        index = max(0, min(index, len(self.frames) - 1))
        self.index = index
        frame = self.frames[index]

        frame_number = int(frame.get("frame_number", index))
        video_index = self._video_index(index, frame_number)
        image = self.video.get_frame(video_index)
        self.overlay.set_frame(image, self.video.size, frame.get("objects_detected", []))

        for name, widget in self.section_widgets.items():
            value = frame.get(name)
            if isinstance(widget, TagListWidget):
                widget.set_values(value or [])
            else:
                widget.set_value(value or "")

        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", frame.get("description", "") or "")

        self.trans_text.config(state="normal")
        self.trans_text.delete("1.0", tk.END)
        transition = frame.get("transition")
        if transition is not None:
            self.trans_text.insert("1.0", json.dumps(transition, indent=2, ensure_ascii=False))
        self.trans_text.config(state="disabled")

        ts = frame.get("timestamp", "")
        self.frame_label.config(
            text=(f"frame {index + 1}/{len(self.frames)} ({ts})  ·  "
                  f"video idx {video_index} of {self.video.frame_count}")
        )
        if abs(self.slider.get() - index) > 0.5:
            self.slider.set(index)
        self._update_title()

    # -------------------------------------------------- frame index mapping #
    def _video_index(self, ann_index, frame_number):
        """Map an annotation entry to a source-video frame index.

        Datasets vary: some videos are full-rate (frame_number is the real
        index), some are downsampled to one stored frame per annotation, and
        some are a different length entirely. ``Auto`` picks a sane option.
        """
        mode = self.mapping_var.get()
        n = len(self.frames)
        fc = self.video.frame_count

        if mode == "By frame_number":
            return frame_number
        if mode == "Sequential":
            return ann_index
        if mode == "Proportional":
            return round(ann_index / (n - 1) * (fc - 1)) if n > 1 and fc > 1 else ann_index

        # Auto
        max_fn = max((int(f.get("frame_number", i)) for i, f in enumerate(self.frames)),
                     default=0)
        if fc and fc >= max_fn + 1:
            return frame_number                      # full-rate video
        if fc and abs(fc - n) <= max(2, int(n * 0.1)):
            return ann_index                         # ~one frame per annotation
        if fc and n > 1:
            return round(ann_index / (n - 1) * (fc - 1))  # different length -> scale
        return frame_number

    def _on_mapping_change(self, _event=None):
        self.controller.config.frame_mapping = self.mapping_var.get()
        self.controller.config.save()
        self._load_frame(self.index)

    def _save_calibration(self, calibration):
        self.controller.config.calibration = calibration
        self.controller.config.save()

    def _commit_current(self):
        """Write widget state back into the in-memory frame dict."""
        frame = self.frames[self.index]
        for name, widget in self.section_widgets.items():
            if isinstance(widget, TagListWidget):
                frame[name] = widget.get_values()
            else:
                frame[name] = widget.get_value()
        frame["description"] = self.desc_text.get("1.0", "end-1c")
        frame["objects_detected"] = self.overlay.get_objects()

    def _goto(self, index):
        if index == self.index:
            return
        self._commit_current()
        self._load_frame(index)

    def _prev(self):
        self._goto(self.index - 1)

    def _next(self):
        self._goto(self.index + 1)

    def _on_slider(self, value):
        index = int(round(float(value)))
        if index != self.index:
            self._goto(index)

    # -------------------------------------------------------------- state #
    def _mark_dirty(self, *_):
        if not self.dirty:
            self.dirty = True
            self._update_title()

    def _update_title(self):
        star = " *" if self.dirty else ""
        unknown = self._unknown_count()
        warn = f"  ⚠ {unknown} unknown in this frame" if unknown else ""
        self.title_label.config(text=f"Pair {self.pair.pair_id}{star}{warn}")

    def _unknown_count(self):
        total = 0
        for name, widget in self.section_widgets.items():
            if widget.has_unknown():
                if isinstance(widget, TagListWidget):
                    total += len(widget.section.unknown(widget.get_values()))
                else:
                    total += 1
        return total

    # ------------------------------------------------------------ actions #
    def _save(self):
        self._commit_current()
        try:
            save_annotation(self.pair.ann_path, self.doc)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.dirty = False
        self._update_title()

    def _mark_done(self):
        self._save()
        self.controller.progress.set_done(self.pair.pair_id, True)
        self._close_video()
        self.controller.show_todo()

    def _back(self):
        if self.dirty and not self._confirm_discard():
            return
        self._close_video()
        self.controller.show_todo()

    def _confirm_discard(self):
        choice = messagebox.askyesnocancel(
            "Unsaved changes", "Save changes before leaving?")
        if choice is None:
            return False
        if choice:
            self._save()
        return True

    def _close_video(self):
        self._unbind_shortcuts()
        try:
            self.video.close()
        except Exception:  # noqa: BLE001
            pass

    def _unbind_shortcuts(self):
        root = self.winfo_toplevel()
        for seq in ("<Left>", "<Right>", "<Control-s>"):
            root.unbind(seq)
