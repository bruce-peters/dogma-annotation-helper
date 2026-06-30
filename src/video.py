"""Frame extraction from mp4 via OpenCV, returned as PIL images.

Annotations are sampled at 1 fps but each frame carries an explicit
``frame_number`` that is the index into the source video, so we seek by that
index directly. ``source_fps`` is only used as a fallback for deriving a
timestamp and is not needed for lookups.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

try:
    import cv2
except ImportError:  # pragma: no cover - surfaced to the user at runtime
    cv2 = None


class VideoError(Exception):
    pass


def _placeholder(width: int, height: int, message: str) -> Image.Image:
    img = Image.new("RGB", (max(width, 320), max(height, 180)), (32, 32, 36))
    draw = ImageDraw.Draw(img)
    draw.text((12, 12), message, fill=(220, 120, 120))
    return img


class FrameSource:
    """Lazily opens a video and serves frames by index as PIL images."""

    def __init__(self, path: str | Path):
        if cv2 is None:
            raise VideoError(
                "opencv-python is not installed. Run: pip install -r requirements.txt"
            )
        self.path = Path(path)
        self._cap = None
        self._width = 0
        self._height = 0
        self._frame_count = 0
        self._cache_index: int | None = None
        self._cache_image: Image.Image | None = None

    # -- lifecycle -------------------------------------------------------- #
    def _ensure_open(self):
        if self._cap is not None:
            return
        if not self.path.exists():
            raise VideoError(f"Video not found: {self.path}")
        cap = cv2.VideoCapture(str(self.path))
        if not cap.isOpened():
            raise VideoError(f"Could not open video: {self.path}")
        self._cap = cap
        self._width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0
        self._height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0
        self._frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        self._fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0

    def close(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # -- properties ------------------------------------------------------- #
    @property
    def size(self) -> tuple[int, int]:
        self._ensure_open()
        return self._width, self._height

    @property
    def frame_count(self) -> int:
        self._ensure_open()
        return self._frame_count

    @property
    def fps(self) -> float:
        self._ensure_open()
        return self._fps

    # -- frame access ----------------------------------------------------- #
    def get_frame(self, frame_number: int) -> Image.Image:
        """Return the frame at ``frame_number`` as an RGB PIL image.

        Out-of-range indices return a labeled placeholder rather than raising,
        so the UI keeps working on truncated clips.
        """
        self._ensure_open()
        if self._cache_index == frame_number and self._cache_image is not None:
            return self._cache_image

        if frame_number < 0 or (self._frame_count and frame_number >= self._frame_count):
            return _placeholder(
                self._width,
                self._height,
                f"Frame {frame_number} is out of range (clip has {self._frame_count}).",
            )

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return _placeholder(
                self._width, self._height, f"Could not read frame {frame_number}."
            )
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        self._cache_index = frame_number
        self._cache_image = image
        return image
