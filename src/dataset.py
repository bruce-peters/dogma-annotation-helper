"""Dataset discovery, annotation I/O, and persisted app state.

Pairs are matched by the integer ``#`` in ``[#]_annotation.json`` and ``[#].mp4``.
Annotation save is round-trip safe: ``json`` preserves dict insertion order, so
key order and any fields the app does not understand are kept intact.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ANNOTATION_RE = re.compile(r"^(\d+)_annotation\.json$", re.IGNORECASE)
VIDEO_RE = re.compile(r"^(\d+)\.mp4$", re.IGNORECASE)


@dataclass
class Pair:
    pair_id: int
    ann_path: Path | None = None
    vid_path: Path | None = None

    @property
    def complete(self) -> bool:
        return self.ann_path is not None and self.vid_path is not None


@dataclass
class ScanResult:
    pairs: dict[int, Pair] = field(default_factory=dict)
    orphan_annotations: list[Path] = field(default_factory=list)
    orphan_videos: list[Path] = field(default_factory=list)

    @property
    def complete_pairs(self) -> list[Pair]:
        return [p for p in self.sorted_pairs if p.complete]

    @property
    def sorted_pairs(self) -> list[Pair]:
        return [self.pairs[k] for k in sorted(self.pairs)]


def scan_pairs(ann_dir: str | Path, vid_dir: str | Path) -> ScanResult:
    """Match annotation/video files by their integer id."""
    ann_dir, vid_dir = Path(ann_dir), Path(vid_dir)
    result = ScanResult()

    anns: dict[int, Path] = {}
    if ann_dir.is_dir():
        for p in sorted(ann_dir.iterdir()):
            m = ANNOTATION_RE.match(p.name)
            if m:
                anns[int(m.group(1))] = p

    vids: dict[int, Path] = {}
    if vid_dir.is_dir():
        for p in sorted(vid_dir.iterdir()):
            m = VIDEO_RE.match(p.name)
            if m:
                vids[int(m.group(1))] = p

    for pid in sorted(set(anns) | set(vids)):
        ann = anns.get(pid)
        vid = vids.get(pid)
        result.pairs[pid] = Pair(pid, ann, vid)
        if ann and not vid:
            result.orphan_annotations.append(ann)
        if vid and not ann:
            result.orphan_videos.append(vid)
    return result


def load_annotation(path: str | Path) -> dict:
    """Load an annotation document. Raises on malformed JSON."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def get_frames(doc: dict) -> list[dict]:
    """Return the frames list from an annotation document.

    Accepts the documented ``{"frames": [...]}`` shape and, defensively, a bare
    top-level list.
    """
    if isinstance(doc, list):
        return doc
    frames = doc.get("frames")
    return frames if isinstance(frames, list) else []


def save_annotation(path: str | Path, doc: dict) -> None:
    """Write the document back, preserving key order and unknown fields."""
    path = Path(path)
    text = json.dumps(doc, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Persisted app state: config.json and progress.json (next to the app).
# --------------------------------------------------------------------------- #


class _JsonStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}
        self.load()

    def load(self) -> None:
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, json.JSONDecodeError):
            self.data = {}

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass


class Config(_JsonStore):
    @property
    def ann_dir(self) -> str:
        return self.data.get("ann_dir", "")

    @ann_dir.setter
    def ann_dir(self, value: str) -> None:
        self.data["ann_dir"] = value

    @property
    def vid_dir(self) -> str:
        return self.data.get("vid_dir", "")

    @vid_dir.setter
    def vid_dir(self, value: str) -> None:
        self.data["vid_dir"] = value

    @property
    def source_fps(self) -> float:
        return float(self.data.get("source_fps", 30.0))

    @source_fps.setter
    def source_fps(self, value: float) -> None:
        self.data["source_fps"] = value

    @property
    def frame_mapping(self) -> str:
        return self.data.get("frame_mapping", "Sequential")

    @frame_mapping.setter
    def frame_mapping(self, value: str) -> None:
        self.data["frame_mapping"] = value

    @property
    def calibration(self) -> dict:
        cal = self.data.get("calibration")
        return cal if isinstance(cal, dict) else {}

    @calibration.setter
    def calibration(self, value: dict) -> None:
        self.data["calibration"] = value


class Progress(_JsonStore):
    def is_done(self, pair_id: int) -> bool:
        return bool(self.data.get(str(pair_id), {}).get("done", False))

    def last_reviewed(self, pair_id: int) -> str:
        return self.data.get(str(pair_id), {}).get("last_reviewed", "")

    def set_done(self, pair_id: int, done: bool = True) -> None:
        self.data[str(pair_id)] = {
            "done": done,
            "last_reviewed": datetime.now().isoformat(timespec="seconds"),
        }
        self.save()
