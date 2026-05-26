import wx
import wx.richtext as rt
import os
import json
import csv
import yaml

from .knowledge_utils import (
    list_knowledge_files,
    load_knowledge_file
)


# =====================================================================
# Knowledge Dialog — View/Add/Manage knowledge files
# =====================================================================

class KnowledgeDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Knowledge Base",
            size=(1000, 700),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # ================================================================
        # LEFT PANEL — FILE LIST
        # ================================================================
        left_panel = wx.Panel(self)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(left_panel, label="Knowledge Files")
        lbl.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        left_sizer.Add(lbl, 0, wx.ALL, 10)

        self.file_list = wx.ListBox(left_panel)
        left_sizer.Add(self.file_list, 1, wx.EXPAND | wx.ALL, 10)

        self.btn_reload = wx.Button(left_panel, label="🔄 Reload")
        left_sizer.Add(self.btn_reload, 0, wx.ALL | wx.EXPAND, 10)

        left_panel.SetSizer(left_sizer)
        main_sizer.Add(left_panel, 0, wx.EXPAND | wx.ALL, 5)

        # ================================================================
        # RIGHT PANEL — FILE CONTENT PREVIEW
        # ================================================================
        right_panel = wx.Panel(self)
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl2 = wx.StaticText(right_panel, label="Preview")
        lbl2.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(lbl2, 0, wx.ALL, 10)

        self.preview = rt.RichTextCtrl(
            right_panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.BORDER_SIMPLE
        )
        right_sizer.Add(self.preview, 1, wx.EXPAND | wx.ALL, 10)

        right_panel.SetSizer(right_sizer)
        main_sizer.Add(right_panel, 1, wx.EXPAND | wx.ALL, 5)

        # ================================================================
        # Bind Events
        # ================================================================
        self.file_list.Bind(wx.EVT_LISTBOX, self._on_select)
        self.btn_reload.Bind(wx.EVT_BUTTON, self._reload_files)

        # Populate list
        self._reload_files(None)

        self.SetSizer(main_sizer)

    # =====================================================================
    # Reload file list
    # =====================================================================
    def _reload_files(self, evt):
        self.file_list.Clear()

        try:
            files = list_knowledge_files()
            for f in files:
                self.file_list.Append(os.path.basename(f))
        except Exception as e:
            wx.MessageBox(f"Failed to load knowledge files:\n{e}", "Error")

    # =====================================================================
    # When a file is selected
    # =====================================================================
    def _on_select(self, evt):
        idx = self.file_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return

        filename = self.file_list.GetString(idx)

        try:
            # Get full path from utility
            files = list_knowledge_files()
            full_path = None
            for f in files:
                if os.path.basename(f) == filename:
                    full_path = f
                    break

            if not full_path:
                self.preview.SetValue("File not found.")
                return

            # Load content safely
            content = load_knowledge_file(full_path)
            self.preview.SetValue(content)

        except Exception as e:
            self.preview.SetValue(f"Failed to load file:\n{e}")
