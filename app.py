"""Entry point for the Dogma Annotation Helper desktop app."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from src.controller import AppController

APP_DIR = Path(__file__).resolve().parent


def main() -> None:
    root = tk.Tk()
    controller = AppController(root, APP_DIR)
    controller.show_home()
    root.mainloop()


if __name__ == "__main__":
    main()
