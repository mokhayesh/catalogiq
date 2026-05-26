from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import wx

APP_ROOT = Path(__file__).resolve().parents[1]


def _python_exe() -> str:
    return sys.executable or "python"


def launch_module(module_name: str) -> None:
    subprocess.Popen(
        [_python_exe(), "-m", module_name],
        cwd=str(APP_ROOT),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    os.startfile(str(path))


class CatalogIQCommandCenter(wx.Frame):
    def __init__(self):
        super().__init__(
            None,
            title="CatalogIQ Command Center v8 — Enterprise Control Plane",
            size=(1040, 720),
        )
        self.SetBackgroundColour(wx.Colour("#F5F7FB"))

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(panel)
        header.SetBackgroundColour(wx.Colour("#071226"))
        hs = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(header, label="CatalogIQ Command Center v8")
        title.SetForegroundColour(wx.WHITE)
        title.SetFont(wx.Font(22, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        subtitle = wx.StaticText(
            header,
            label="Enterprise control plane for catalog workspaces, connector profiles, data products, and governance outputs.",
        )
        subtitle.SetForegroundColour(wx.Colour("#D8E3F5"))
        subtitle.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        hs.Add(title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)
        hs.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 18)
        header.SetSizer(hs)
        root.Add(header, 0, wx.EXPAND)

        body = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.Panel(panel)
        left.SetBackgroundColour(wx.Colour("#FFFFFF"))
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        section = wx.StaticText(left, label="ENTERPRISE MODULES")
        section.SetForegroundColour(wx.Colour("#23395D"))
        section.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        left_sizer.Add(section, 0, wx.ALL, 14)

        self.add_button(left_sizer, left, "Agentic Catalog Workspace", "Open profiling, catalog, governance, and data product workspace.", lambda: launch_module("app.agentic_catalog_dialog"))
        self.add_button(left_sizer, left, "Connector Profile Manager", "Save and manage Snowflake, AWS S3, and local file profiles safely.", lambda: launch_module("app.connector_profile_dialog"))
        self.add_button(left_sizer, left, "Classic CatalogIQ", "Open the original CatalogIQ application shell.", lambda: launch_module("app.main"))
        self.add_button(left_sizer, left, "Output Packages", "Open generated data product export packages.", lambda: open_folder(APP_ROOT / "outputs"))
        self.add_button(left_sizer, left, "Published Workspace Assets", "Open locally published CatalogIQ workspace assets.", lambda: open_folder(APP_ROOT / "catalogiq_workspace"))
        self.add_button(left_sizer, left, "Connector Profile Store", "Open the local-only connector profile JSON store folder.", lambda: open_folder(APP_ROOT / ".catalogiq_local"))
        self.add_button(left_sizer, left, "Healthcheck", "Run the Phase 8 dependency and repository healthcheck.", lambda: launch_module("app.phase8_healthcheck"))

        left.SetSizer(left_sizer)

        right = wx.Panel(panel)
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        hero = wx.StaticText(right, label="Enterprise Catalog Agent")
        hero.SetForegroundColour(wx.Colour("#071226"))
        hero.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(hero, 0, wx.ALL, 18)

        message = wx.StaticText(
            right,
            label=(
                "CatalogIQ now supports a safer enterprise workflow:\n\n"
                "1. Use Connector Profile Manager to save reusable non-secret connection profiles.\n"
                "2. Open Agentic Catalog Workspace to connect data sources, profile datasets, and generate metadata views.\n"
                "3. Export a Data Product Package for governance, quality, glossary, and catalog payloads.\n"
                "4. Publish local assets for reuse across sessions.\n\n"
                "Secrets should stay in .env or your environment variables. Profiles store profile names, accounts, "
                "warehouses, bucket names, object prefixes, and env-var references — not raw passwords or keys."
            ),
        )
        message.Wrap(650)
        message.SetForegroundColour(wx.Colour("#334155"))
        message.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        right_sizer.Add(message, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 18)

        tips_box = wx.TextCtrl(
            right,
            value=(
                "Recommended next flow:\n"
                "• Open Connector Profile Manager\n"
                "• Create dev_snowflake and dev_s3 profiles\n"
                "• Open Agentic Catalog Workspace\n"
                "• Use Connector Hub for Local File, S3, or Snowflake\n"
                "• Auto Profile → Generate Views → Export Package → Publish Local Asset\n\n"
                "Git safety:\n"
                "• .env is ignored\n"
                "• .catalogiq_local/ is ignored\n"
                "• outputs/ and catalogiq_workspace/ are ignored\n"
            ),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
            size=(-1, 220),
        )
        tips_box.SetBackgroundColour(wx.Colour("#EEF2F7"))
        tips_box.SetForegroundColour(wx.Colour("#0F172A"))
        tips_box.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        right_sizer.Add(tips_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 18)

        self.status = wx.StaticText(right, label=f"Workspace: {APP_ROOT}")
        self.status.SetForegroundColour(wx.Colour("#64748B"))
        right_sizer.AddStretchSpacer(1)
        right_sizer.Add(self.status, 0, wx.ALL, 18)

        right.SetSizer(right_sizer)

        body.Add(left, 0, wx.EXPAND | wx.ALL, 12)
        body.Add(right, 1, wx.EXPAND | wx.TOP | wx.RIGHT | wx.BOTTOM, 12)
        root.Add(body, 1, wx.EXPAND)

        panel.SetSizer(root)

    def add_button(self, sizer: wx.BoxSizer, parent: wx.Window, title: str, description: str, callback):
        card = wx.Panel(parent)
        card.SetBackgroundColour(wx.Colour("#F8FAFC"))
        cs = wx.BoxSizer(wx.VERTICAL)

        btn = wx.Button(card, label=title, size=(-1, 38))
        btn.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        desc = wx.StaticText(card, label=description)
        desc.SetForegroundColour(wx.Colour("#5D6B82"))
        desc.Wrap(310)

        def _handler(_evt):
            try:
                callback()
                self.status.SetLabel(f"Launched: {title}")
            except Exception as exc:
                wx.MessageBox(str(exc), f"Could not launch {title}", wx.OK | wx.ICON_ERROR)
                self.status.SetLabel(f"Failed: {title}")

        btn.Bind(wx.EVT_BUTTON, _handler)

        cs.Add(btn, 0, wx.ALL | wx.EXPAND, 8)
        cs.Add(desc, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        card.SetSizer(cs)
        sizer.Add(card, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)


def main() -> None:
    app = wx.App(False)
    frame = CatalogIQCommandCenter()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
