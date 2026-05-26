# app/main.py
import os
import sys

# Ensure this directory is on sys.path so absolute fallback works when frozen
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Import MainWindow in a way that works both:
#  - in dev:  python -m app.main   (package context)
#  - in exe:  CatalogIQ.exe        (no package context)
try:
    # Dev run as a package
    from .main_window import MainWindow
except Exception:
    try:
        # Absolute import when "app" is visible on sys.path (exe / direct run)
        from app.main_window import MainWindow  # type: ignore
    except Exception:
        # Last resort: same folder import
        from main_window import MainWindow  # type: ignore

import wx


def main() -> None:
    """
    Launch the CatalogIQ MainWindow safely whether or not a wx.App already exists.
    (Some builds or test harnesses create the App for us.)
    """
    app = wx.GetApp()
    if app is None:
        app = wx.App(False)
        MainWindow()
        app.MainLoop()
    else:
        MainWindow()


if __name__ == "__main__":
    main()
