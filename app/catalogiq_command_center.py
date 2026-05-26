"""
CatalogIQ Phase 6 — Enterprise Connectors Command Center
Premium module + workspace selector for Classic CatalogIQ, Agentic Workspace, outputs, and published assets.
Does not patch main_window.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
WORKSPACE_DIR = ROOT / "catalogiq_workspace"
OUTPUTS_DIR = ROOT / "outputs"

BG = "#07111f"
PANEL = "#0f172a"
INK = "#0f172a"
MUTED = "#475569"
BORDER = "#d8dee9"
ACCENT = "#2563eb"


def _popen(args: list[str], env_extra: dict[str, str] | None = None) -> None:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        subprocess.Popen(args, cwd=str(ROOT), env=env)
    except Exception as exc:
        messagebox.showerror("CatalogIQ", f"Could not launch command:\n{' '.join(args)}\n\n{exc}")


def _open_path(path: Path, create: bool = True) -> None:
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        messagebox.showerror("CatalogIQ", f"Could not open:\n{path}\n\n{exc}")


def _load_assets() -> list[dict]:
    idx = WORKSPACE_DIR / "workspace_index.json"
    if not idx.exists():
        return []
    try:
        data = json.loads(idx.read_text(encoding="utf-8"))
        return list(data.get("assets", []))
    except Exception:
        return []


def _latest_output_packages() -> list[Path]:
    if not OUTPUTS_DIR.exists():
        return []
    return sorted([p for p in OUTPUTS_DIR.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)


class CommandCenter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CatalogIQ Enterprise Command Center v7")
        self.geometry("1180x720")
        self.minsize(1050, 650)
        self.configure(bg=BG)
        self.assets: list[dict] = []
        self.packages: list[Path] = []
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=28, pady=(24, 12))
        tk.Label(header, text="CatalogIQ Enterprise Command Center v7", fg="white", bg=BG, font=("Segoe UI", 24, "bold"), anchor="w").pack(fill="x")
        tk.Label(header, text="Choose a module, reopen a saved workspace asset, or jump into generated data product packages.", fg="#c7d2fe", bg=BG, font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(6, 0))

        body = tk.Frame(self, bg="#f4f7fb")
        body.pack(fill="both", expand=True, padx=28, pady=(10, 20))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._module_panel(body).grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self._workspace_panel(body).grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self._package_panel(body).grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        footer = tk.Frame(self, bg=BG)
        footer.pack(fill="x", padx=28, pady=(0, 16))
        tk.Label(footer, text=f"Project: {ROOT}", fg="#94a3b8", bg=BG, font=("Segoe UI", 8), anchor="w").pack(side="left")
        tk.Button(footer, text="Refresh", command=self.refresh_all, bg="#1e293b", fg="white", relief="flat", padx=14, pady=6).pack(side="right")

    def _card(self, parent):
        f = tk.Frame(parent, bg="white", highlightbackground=BORDER, highlightthickness=1)
        return f

    def _button(self, parent, text, cmd, primary=False):
        return tk.Button(parent, text=text, command=cmd, bg=(ACCENT if primary else PANEL), fg="white", activebackground="#1d4ed8", activeforeground="white", relief="flat", font=("Segoe UI", 9, "bold"), padx=12, pady=8)

    def _module_panel(self, parent):
        f = self._card(parent)
        tk.Label(f, text="1. Select Module", bg="white", fg=INK, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        tk.Label(f, text="Open the classic catalog or the enterprise agentic workspace. This is the premium module selector you liked, upgraded for Phase 6 enterprise workflows.", bg="white", fg=MUTED, font=("Segoe UI", 9), justify="left", wraplength=310, anchor="w").pack(fill="x", padx=18, pady=(0, 12))
        self.module_list = tk.Listbox(f, height=8, exportselection=False, font=("Segoe UI", 10), activestyle="none")
        for item in [
            "Classic CatalogIQ",
            "Agentic Catalog Workspace v7",
            "Connector Hub",
            "Governance Review",
            "Data Product Detail",
            "Output Packages Folder",
            "Published Workspace Assets Folder",
        ]:
            self.module_list.insert("end", item)
        self.module_list.selection_set(1)
        self.module_list.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._button(f, "Open Selected Module", self.open_selected_module, True).pack(fill="x", padx=18, pady=(0, 8))
        self._button(f, "Open Agentic Workspace", lambda: self.open_workspace()).pack(fill="x", padx=18, pady=(0, 18))
        return f

    def _workspace_panel(self, parent):
        f = self._card(parent)
        tk.Label(f, text="2. Select Workspace Asset", bg="white", fg=INK, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        tk.Label(f, text="Reopen a saved CatalogIQ data product asset directly inside the v5 workspace.", bg="white", fg=MUTED, font=("Segoe UI", 9), justify="left", wraplength=310, anchor="w").pack(fill="x", padx=18, pady=(0, 12))
        self.asset_list = tk.Listbox(f, height=12, exportselection=False, font=("Segoe UI", 10), activestyle="none")
        self.asset_list.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._button(f, "Open Selected Asset in Workspace", self.open_selected_asset, True).pack(fill="x", padx=18, pady=(0, 8))
        self._button(f, "Open Workspace Folder", lambda: _open_path(WORKSPACE_DIR)).pack(fill="x", padx=18, pady=(0, 18))
        return f

    def _package_panel(self, parent):
        f = self._card(parent)
        tk.Label(f, text="3. Open Data Product Package", bg="white", fg=INK, font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=18, pady=(18, 6))
        tk.Label(f, text="Open generated packages: HTML launcher, Excel catalog, governance report, DQ SQL, payloads, and manifests.", bg="white", fg=MUTED, font=("Segoe UI", 9), justify="left", wraplength=310, anchor="w").pack(fill="x", padx=18, pady=(0, 12))
        self.package_list = tk.Listbox(f, height=12, exportselection=False, font=("Segoe UI", 10), activestyle="none")
        self.package_list.pack(fill="both", expand=True, padx=18, pady=(0, 12))
        self._button(f, "Open Selected Package", self.open_selected_package, True).pack(fill="x", padx=18, pady=(0, 8))
        self._button(f, "Open Outputs Folder", lambda: _open_path(OUTPUTS_DIR)).pack(fill="x", padx=18, pady=(0, 18))
        return f

    def refresh_all(self):
        self.assets = _load_assets()
        self.asset_list.delete(0, "end")
        if self.assets:
            for a in self.assets:
                self.asset_list.insert("end", f"{a.get('dataset_name','Dataset')}  |  {a.get('risk_level','--')}  |  {a.get('readiness_score','--')}/100")
            self.asset_list.selection_set(0)
        else:
            self.asset_list.insert("end", "No published workspace assets yet")

        self.packages = _latest_output_packages()
        self.package_list.delete(0, "end")
        if self.packages:
            for p in self.packages[:25]:
                self.package_list.insert("end", p.name)
            self.package_list.selection_set(0)
        else:
            self.package_list.insert("end", "No output packages yet")

    def open_workspace(self, asset_file: str | None = None, start_command: str | None = None):
        env = {}
        if asset_file:
            env["CATALOGIQ_OPEN_ASSET_FILE"] = asset_file
        if start_command:
            env["CATALOGIQ_START_COMMAND"] = start_command
        _popen([PYTHON, "-m", "app.agentic_catalog_dialog"], env)

    def open_selected_module(self):
        idx = self.module_list.curselection()
        choice = self.module_list.get(idx[0]) if idx else "Agentic Catalog Workspace v7"
        if choice.startswith("Classic"):
            _popen([PYTHON, "-m", "app.main"])
        elif choice.startswith("Agentic"):
            self.open_workspace()
        elif choice.startswith("Connector"):
            self.open_workspace(start_command="connector")
        elif choice.startswith("Governance"):
            self.open_workspace(start_command="governance")
        elif choice.startswith("Data Product"):
            self.open_workspace(start_command="detail")
        elif choice.startswith("Output"):
            _open_path(OUTPUTS_DIR)
        else:
            _open_path(WORKSPACE_DIR)

    def open_selected_asset(self):
        idx = self.asset_list.curselection()
        if not idx or not self.assets or idx[0] >= len(self.assets):
            messagebox.showinfo("CatalogIQ", "Select a published workspace asset first.")
            return
        asset_file = str(self.assets[idx[0]].get("asset_file", ""))
        if not asset_file:
            messagebox.showerror("CatalogIQ", "Selected asset does not have an asset_file path.")
            return
        self.open_workspace(asset_file)

    def open_selected_package(self):
        idx = self.package_list.curselection()
        if not idx or not self.packages or idx[0] >= len(self.packages):
            messagebox.showinfo("CatalogIQ", "Select an output package first.")
            return
        _open_path(self.packages[idx[0]], create=False)


def main():
    app = CommandCenter()
    app.mainloop()


if __name__ == "__main__":
    main()
