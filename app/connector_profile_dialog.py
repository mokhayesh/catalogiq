from __future__ import annotations

import json
from typing import Dict, Any

import wx

from app.connector_profiles import (
    delete_profile,
    get_profile,
    list_profiles,
    masked_profile,
    profile_store_path,
    save_profile,
)


CONNECTOR_TYPES = ["snowflake", "aws_s3", "local_file"]


DEFAULT_CONFIGS: Dict[str, Dict[str, str]] = {
    "snowflake": {
        "account": "",
        "user": "",
        "role": "",
        "warehouse": "",
        "database": "",
        "schema": "",
        "table": "",
        "password_env": "SNOWFLAKE_PASSWORD",
    },
    "aws_s3": {
        "aws_profile": "default",
        "region": "us-east-1",
        "bucket": "",
        "object_key_prefix": "",
        "access_key_env": "AWS_ACCESS_KEY_ID",
        "secret_key_env": "AWS_SECRET_ACCESS_KEY",
        "session_token_env": "AWS_SESSION_TOKEN",
    },
    "local_file": {
        "default_folder": "",
        "allowed_extensions": ".csv,.txt,.xlsx,.xls",
    },
}


class ConnectorProfileDialog(wx.Frame):
    def __init__(self):
        super().__init__(
            None,
            title="CatalogIQ Connector Profile Manager",
            size=(980, 680),
        )

        self.SetBackgroundColour(wx.Colour("#F5F7FB"))

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        header = wx.Panel(panel)
        header.SetBackgroundColour(wx.Colour("#071226"))
        hs = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(header, label="Connector Profile Manager")
        title.SetForegroundColour(wx.WHITE)
        title.SetFont(wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        subtitle = wx.StaticText(
            header,
            label="Save reusable Snowflake, AWS S3, and local connector profiles without storing secrets.",
        )
        subtitle.SetForegroundColour(wx.Colour("#D8E3F5"))

        hs.Add(title, 0, wx.ALL, 14)
        hs.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        header.SetSizer(hs)

        root.Add(header, 0, wx.EXPAND)

        body = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.Panel(panel)
        left.SetBackgroundColour(wx.Colour("#EEF2F7"))
        ls = wx.BoxSizer(wx.VERTICAL)

        lbl_profiles = wx.StaticText(left, label="SAVED PROFILES")
        lbl_profiles.SetForegroundColour(wx.Colour("#23395D"))
        lbl_profiles.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        self.profile_list = wx.ListBox(left)
        self.btn_refresh = wx.Button(left, label="Refresh")
        self.btn_load = wx.Button(left, label="Load Selected")
        self.btn_delete = wx.Button(left, label="Delete Selected")
        self.btn_store = wx.Button(left, label="Open Local Store Folder")

        ls.Add(lbl_profiles, 0, wx.ALL, 10)
        ls.Add(self.profile_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        ls.Add(self.btn_refresh, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        ls.Add(self.btn_load, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        ls.Add(self.btn_delete, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        ls.Add(self.btn_store, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        left.SetSizer(ls)

        right = wx.Panel(panel)
        rs = wx.BoxSizer(wx.VERTICAL)

        form = wx.FlexGridSizer(rows=0, cols=2, vgap=8, hgap=10)
        form.AddGrowableCol(1, 1)

        self.name = wx.TextCtrl(right)
        self.connector_type = wx.Choice(right, choices=CONNECTOR_TYPES)
        self.connector_type.SetSelection(0)

        form.Add(wx.StaticText(right, label="Profile Name"), 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.name, 0, wx.EXPAND)

        form.Add(wx.StaticText(right, label="Connector Type"), 0, wx.ALIGN_CENTER_VERTICAL)
        form.Add(self.connector_type, 0, wx.EXPAND)

        rs.Add(form, 0, wx.ALL | wx.EXPAND, 16)

        cfg_label = wx.StaticText(right, label="Profile Config JSON")
        cfg_label.SetForegroundColour(wx.Colour("#23395D"))
        cfg_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        help_text = wx.StaticText(
            right,
            label="Use environment variable names for secrets. Do not paste real passwords, API keys, or access keys here.",
        )
        help_text.SetForegroundColour(wx.Colour("#5D6B82"))

        self.config_json = wx.TextCtrl(
            right,
            style=wx.TE_MULTILINE | wx.TE_RICH2,
        )
        self.config_json.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_template = wx.Button(right, label="Load Template")
        self.btn_save = wx.Button(right, label="Save Profile")
        self.btn_masked = wx.Button(right, label="Show Masked Preview")
        self.btn_close = wx.Button(right, label="Close")

        buttons.Add(self.btn_template, 0, wx.RIGHT, 8)
        buttons.Add(self.btn_save, 0, wx.RIGHT, 8)
        buttons.Add(self.btn_masked, 0, wx.RIGHT, 8)
        buttons.AddStretchSpacer(1)
        buttons.Add(self.btn_close, 0)

        self.output = wx.TextCtrl(
            right,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, 130),
        )
        self.output.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        rs.Add(cfg_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 16)
        rs.Add(help_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)
        rs.Add(self.config_json, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)
        rs.Add(buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)
        rs.Add(wx.StaticText(right, label="Console"), 0, wx.LEFT | wx.RIGHT, 16)
        rs.Add(self.output, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 16)
        right.SetSizer(rs)

        body.Add(left, 0, wx.EXPAND)
        body.Add(right, 1, wx.EXPAND)

        root.Add(body, 1, wx.EXPAND)
        panel.SetSizer(root)

        self.btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.btn_load.Bind(wx.EVT_BUTTON, self.on_load)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_store.Bind(wx.EVT_BUTTON, self.on_open_store)
        self.btn_template.Bind(wx.EVT_BUTTON, self.on_template)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        self.btn_masked.Bind(wx.EVT_BUTTON, self.on_masked_preview)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda _evt: self.Close())
        self.connector_type.Bind(wx.EVT_CHOICE, self.on_template)

        self.on_template(None)
        self.on_refresh(None)

    def log(self, message: str) -> None:
        self.output.AppendText(message.rstrip() + "\n")

    def selected_profile_name(self) -> str:
        selection = self.profile_list.GetSelection()
        if selection == wx.NOT_FOUND:
            return ""
        item = self.profile_list.GetString(selection)
        return item.split(" | ", 1)[0].strip()

    def current_connector_type(self) -> str:
        return self.connector_type.GetStringSelection() or "snowflake"

    def on_refresh(self, _evt) -> None:
        self.profile_list.Clear()
        profiles = list_profiles()
        for profile in profiles:
            self.profile_list.Append(
                f"{profile.get('name')} | {profile.get('connector_type')} | updated {profile.get('updated_at')}"
            )
        self.log(f"Refreshed profiles. Count: {len(profiles)}")

    def on_template(self, _evt) -> None:
        ctype = self.current_connector_type()
        template = DEFAULT_CONFIGS.get(ctype, {})
        self.config_json.SetValue(json.dumps(template, indent=2))
        self.log(f"Loaded {ctype} template.")

    def on_load(self, _evt) -> None:
        name = self.selected_profile_name()
        if not name:
            wx.MessageBox("Select a profile first.", "No profile selected", wx.OK | wx.ICON_WARNING)
            return

        profile = get_profile(name)
        if not profile:
            wx.MessageBox("Profile not found.", "Missing profile", wx.OK | wx.ICON_ERROR)
            return

        self.name.SetValue(profile.get("name", ""))
        ctype = profile.get("connector_type", "snowflake")
        if ctype in CONNECTOR_TYPES:
            self.connector_type.SetSelection(CONNECTOR_TYPES.index(ctype))
        self.config_json.SetValue(json.dumps(profile.get("config", {}), indent=2))
        self.log(f"Loaded profile: {name}")

    def on_delete(self, _evt) -> None:
        name = self.selected_profile_name()
        if not name:
            wx.MessageBox("Select a profile first.", "No profile selected", wx.OK | wx.ICON_WARNING)
            return

        confirm = wx.MessageBox(
            f"Delete profile '{name}'?",
            "Confirm delete",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if confirm != wx.YES:
            return

        if delete_profile(name):
            self.log(f"Deleted profile: {name}")
            self.on_refresh(None)
        else:
            self.log(f"Profile not found: {name}")

    def on_open_store(self, _evt) -> None:
        path = profile_store_path()
        import os
        os.startfile(os.path.dirname(path))
        self.log(f"Opened profile store folder: {path}")

    def on_save(self, _evt) -> None:
        name = self.name.GetValue().strip()
        if not name:
            wx.MessageBox("Enter a profile name.", "Missing name", wx.OK | wx.ICON_WARNING)
            return

        ctype = self.current_connector_type()

        try:
            config: Dict[str, Any] = json.loads(self.config_json.GetValue())
            if not isinstance(config, dict):
                raise ValueError("Config JSON must be an object.")
        except Exception as exc:
            wx.MessageBox(f"Invalid JSON:\n{exc}", "Invalid config", wx.OK | wx.ICON_ERROR)
            return

        saved = save_profile(name=name, connector_type=ctype, config=config)
        self.log(f"Saved profile: {saved.get('name')} ({saved.get('connector_type')})")
        self.on_refresh(None)

    def on_masked_preview(self, _evt) -> None:
        name = self.name.GetValue().strip() or "preview"
        ctype = self.current_connector_type()

        try:
            config: Dict[str, Any] = json.loads(self.config_json.GetValue())
        except Exception as exc:
            wx.MessageBox(f"Invalid JSON:\n{exc}", "Invalid config", wx.OK | wx.ICON_ERROR)
            return

        preview = masked_profile(
            {
                "name": name,
                "connector_type": ctype,
                "config": config,
                "created_at": "",
                "updated_at": "",
            }
        )
        self.log("Masked preview:")
        self.log(json.dumps(preview, indent=2))


def main() -> None:
    app = wx.App(False)
    frame = ConnectorProfileDialog()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
