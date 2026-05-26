"""
CatalogIQ Premium Suite Launcher
Safe Phase 4 integration: launches Classic CatalogIQ and the Agentic Catalog Workspace
without patching main_window.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run_module(module_name: str) -> None:
    try:
        subprocess.Popen([PYTHON, "-m", module_name], cwd=str(ROOT))
    except Exception as exc:
        messagebox.showerror("CatalogIQ", f"Could not launch {module_name}:\n\n{exc}")


def _open_path(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # type: ignore[attr-defined]
    except Exception as exc:
        messagebox.showerror("CatalogIQ", f"Could not open folder:\n{path}\n\n{exc}")


def _build_app() -> tk.Tk:
    root = tk.Tk()
    root.title("CatalogIQ Premium Launcher")
    root.geometry("720x460")
    root.minsize(650, 420)
    root.configure(bg="#07111f")

    header = tk.Frame(root, bg="#07111f")
    header.pack(fill="x", padx=24, pady=(22, 10))

    title = tk.Label(
        header,
        text="CatalogIQ Premium Suite",
        fg="white",
        bg="#07111f",
        font=("Segoe UI", 22, "bold"),
        anchor="w",
    )
    title.pack(fill="x")

    subtitle = tk.Label(
        header,
        text="Classic catalog + agentic data product workspace. Safe Phase 4 launcher — no main_window patching.",
        fg="#c7d2fe",
        bg="#07111f",
        font=("Segoe UI", 10),
        anchor="w",
    )
    subtitle.pack(fill="x", pady=(6, 0))

    body = tk.Frame(root, bg="#f4f7fb")
    body.pack(fill="both", expand=True, padx=24, pady=18)

    def card(parent, title_text, desc, command, row, col):
        frame = tk.Frame(parent, bg="white", highlightbackground="#d8dee9", highlightthickness=1)
        frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
        parent.grid_columnconfigure(col, weight=1)
        parent.grid_rowconfigure(row, weight=1)

        tk.Label(frame, text=title_text, bg="white", fg="#0f172a", font=("Segoe UI", 13, "bold"), anchor="w").pack(fill="x", padx=18, pady=(16, 4))
        tk.Label(frame, text=desc, bg="white", fg="#334155", font=("Segoe UI", 9), anchor="w", justify="left", wraplength=270).pack(fill="x", padx=18, pady=(0, 14))
        tk.Button(frame, text="Open", command=command, bg="#0f172a", fg="white", activebackground="#1e293b", activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=12, pady=8).pack(anchor="w", padx=18, pady=(0, 18))

    card(
        body,
        "Classic CatalogIQ",
        "Open the original catalog application. Use this for existing catalog/import workflows.",
        lambda: _run_module("app.main"),
        0,
        0,
    )
    card(
        body,
        "Agentic Catalog Workspace",
        "Open Platform Core v3 for profiling datasets, creating metadata packages, governance findings, and agent questions.",
        lambda: _run_module("app.agentic_catalog_dialog"),
        0,
        1,
    )
    card(
        body,
        "Output Packages",
        "Open generated data product packages, including Excel, HTML, governance reports, payloads, and SQL rules.",
        lambda: _open_path(ROOT / "outputs"),
        1,
        0,
    )
    card(
        body,
        "Published Workspace Assets",
        "Open the local CatalogIQ workspace index and saved asset JSON files.",
        lambda: _open_path(ROOT / "catalogiq_workspace"),
        1,
        1,
    )

    footer = tk.Label(
        root,
        text=f"Project: {ROOT}",
        fg="#94a3b8",
        bg="#07111f",
        font=("Segoe UI", 8),
        anchor="w",
    )
    footer.pack(fill="x", padx=24, pady=(0, 14))
    return root


def main() -> None:
    app = _build_app()
    app.mainloop()


if __name__ == "__main__":
    main()
