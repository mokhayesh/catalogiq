# start_catalogiq.py  -- stable entrypoint for PyInstaller
import os, sys, importlib

# Make repo root importable (so "app" is a package)
repo_root = os.path.abspath(os.path.dirname(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

def _fallback_boot():
    import wx
    from app.main_window import MainWindow
    app = wx.App(False)
    MainWindow()
    app.MainLoop()

def main():
    try:
        m = importlib.import_module("app.main")
        if hasattr(m, "main"):
            return m.main()
    except Exception:
        pass
    _fallback_boot()

if __name__ == "__main__":
    main()
