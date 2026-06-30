# Dogma Annotation Helper

A small Tkinter desktop tool for **validating a preexisting video-annotation
dataset**. A reviewer steps through each video frame-by-frame (annotations are
sampled at 1 fps), checks the auto-generated annotation, edits tags and object
detections, and marks each video/annotation pair as reviewed.

## Install

Requires Python 3.11+ with `tkinter` (bundled with the standard
python.org Windows build).

```
py -m pip install -r requirements.txt
```

This installs `opencv-python` (frame extraction) and `Pillow` (rendering).

## Run

```
py app.py
```

1. **Home** – pick the annotations folder (`[#]_annotation.json`) and the videos
   folder (`[#].mp4`), then **Scan / Load**. Folder paths are remembered in
   `config.json`.
2. **Todo** – every matched pair with a Done badge and a validation badge
   (red when any frame contains tags that are not in the taxonomy). Filter by
   All / Done / Not done. Double-click a row to open it.
3. **Annotate** – the video frame on the left with detection points overlaid;
   the annotation fields on the right.
   - `←` / `→` move between frames, or use the slider.
   - Single-select fields (e.g. `environment`) are dropdowns; multi-select
     fields are add/remove tag chips with a searchable picker.
   - Object detections are drawn as colored points on the frame; their **label
     and distance are editable** in the side list (x/y are read-only).
   - `Ctrl+S` saves back to the JSON (key order and any unknown fields are
     preserved). **Mark pair as done** records progress in `progress.json`.

## The taxonomy

All tags live in [`lib/taxonomy.json`](lib/taxonomy.json) and are loaded at
startup — edit that file to add, remove, or re-describe tags with no code
changes. Each section declares:

- `selection`: `"single"` (dropdown) or `"multi"` (tag chips)
- `validated`: `true` flags any tag not in the taxonomy with a red ⚠ indicator;
  `false` makes the field freeform (e.g. `surface_type`), where any value is
  accepted and nothing is flagged
- `tags`: `{ CODE: description }` powering the searchable picker

Invalid tags are highlighted but never auto-removed — the reviewer decides
whether to keep or delete them.

## Project layout

```
app.py                 entry point
lib/taxonomy.json      tag vocabulary (edit to change behavior)
src/
  taxonomy.py          load + query the taxonomy
  dataset.py           pair scanning, annotation I/O, config + progress
  video.py             OpenCV frame extraction -> PIL images
  controller.py        app state + screen navigation
  ui/
    widgets.py         tag picker, tag lists, object overlay, scroll frame
    home.py            setup screen
    todo.py            overview screen
    annotate.py        frame-by-frame review screen
```
# dogma-annotation-helper
