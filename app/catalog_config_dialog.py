import wx
import wx.grid as gridlib
from typing import Dict, List, Tuple

from .config_store import CatalogConfig

class CatalogConfigDialog(wx.Dialog):
    """
    Edit and persist catalog-wide configuration:
      - General (default policy, nullable default, analysis-date mode)
      - Presets: Regex and Data-Type mappings (per friendly field name)
      - AI knobs (stored only; your main AI code can optionally read them)
    Saves to %APPDATA%/CatalogIQ/catalog_config.json (falls back to cwd).
    """

    def __init__(self, parent):
        super().__init__(parent, title="Configure Catalog", size=(900, 600))
        self.SetBackgroundColour("#FFFFFF")
        self.cfg = CatalogConfig.load()

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.nb = wx.Notebook(self)

        # --- General tab ---
        self.pnl_general = wx.Panel(self.nb)
        self._init_general_tab(self.pnl_general)
        self.nb.AddPage(self.pnl_general, "General")

        # --- Regex Presets tab ---
        self.pnl_regex = wx.Panel(self.nb)
        self.grid_regex = self._init_kv_grid(self.pnl_regex, ["Field (Friendly Name)", "Regex Pattern"])
        self.nb.AddPage(self.pnl_regex, "Regex Presets")

        # --- Data Type Presets tab ---
        self.pnl_dtype = wx.Panel(self.nb)
        self.grid_dtype = self._init_kv_grid(self.pnl_dtype, ["Field (Friendly Name)", "Data Type"])
        self.nb.AddPage(self.pnl_dtype, "Data Type Presets")

        # --- AI tab (optional knobs) ---
        self.pnl_ai = wx.Panel(self.nb)
        self._init_ai_tab(self.pnl_ai)
        self.nb.AddPage(self.pnl_ai, "AI Options")

        sizer.Add(self.nb, 1, wx.EXPAND | wx.ALL, 8)

        # buttons
        btns = wx.StdDialogButtonSizer()
        self.btn_defaults = wx.Button(self, wx.ID_ANY, "Reset to Defaults")
        self.btn_defaults.SetToolTip("Restore built-in defaults (you can still Cancel).")
        self.btn_save = wx.Button(self, wx.ID_OK, "Save")
        self.btn_cancel = wx.Button(self, wx.ID_CANCEL, "Cancel")
        btns.AddButton(self.btn_defaults)
        btns.AddButton(self.btn_save)
        btns.AddButton(self.btn_cancel)
        btns.Realize()
        sizer.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        self.SetSizer(sizer)
        self._load_into_ui()
        self._bind()

    # -------------------- UI builders --------------------

    def _init_general_tab(self, panel: wx.Panel):
        v = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=0, cols=2, hgap=10, vgap=8)
        grid.AddGrowableCol(1, 1)

        self.txt_default_policy = wx.TextCtrl(panel)
        self.cbo_nullable = wx.Choice(panel, choices=["No", "Yes"])
        self.cbo_analysis_mode = wx.Choice(panel, choices=["Auto Today", "Manual"])
        self.spn_profile_rows = wx.SpinCtrl(panel, min=0, max=10_000_000)

        def add(label, ctrl):
            grid.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        add("Default Policy:", self.txt_default_policy)
        add("Nullable Default:", self.cbo_nullable)
        add("Analysis Date Mode:", self.cbo_analysis_mode)
        add("Profile Sample Rows:", self.spn_profile_rows)

        v.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(v)

    def _init_kv_grid(self, panel: wx.Panel, headers: List[str]) -> gridlib.Grid:
        v = wx.BoxSizer(wx.VERTICAL)
        grid = gridlib.Grid(panel)
        grid.CreateGrid(0, 2)
        for i, h in enumerate(headers):
            grid.SetColLabelValue(i, h)
            grid.SetColSize(i, 300 if i == 0 else 400)
        grid.EnableEditing(True)
        grid.SetGridLineColour("#CCCCCC")
        v.Add(grid, 1, wx.EXPAND | wx.ALL, 8)

        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        btn_add = wx.Button(panel, label="Add Row")
        btn_del = wx.Button(panel, label="Delete Row")
        toolbar.Add(btn_add, 0, wx.RIGHT, 6)
        toolbar.Add(btn_del, 0)
        v.Add(toolbar, 0, wx.ALL, 8)

        def on_add(_):
            grid.AppendRows(1)

        def on_del(_):
            sel = grid.GetGridCursorRow()
            if 0 <= sel < grid.GetNumberRows():
                grid.DeleteRows(sel, 1)

        btn_add.Bind(wx.EVT_BUTTON, on_add)
        btn_del.Bind(wx.EVT_BUTTON, on_del)

        panel.SetSizer(v)
        return grid

    def _init_ai_tab(self, panel: wx.Panel):
        v = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(rows=0, cols=2, hgap=10, vgap=8)
        grid.AddGrowableCol(1, 1)

        self.chk_json_only = wx.CheckBox(panel, label="Require model to return JSON only")
        self.spn_temperature = wx.SpinCtrlDouble(panel, min=0.0, max=2.0, inc=0.1)
        self.spn_max_tokens = wx.SpinCtrl(panel, min=1, max=32000)

        def add(label, ctrl):
            grid.Add(wx.StaticText(panel, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        add("JSON Enforcement:", self.chk_json_only)
        add("Temperature:", self.spn_temperature)
        add("Max Tokens:", self.spn_max_tokens)

        v.Add(grid, 0, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(v)

    # -------------------- Data wiring --------------------

    def _bind(self):
        self.btn_defaults.Bind(wx.EVT_BUTTON, self._on_defaults)
        self.btn_save.Bind(wx.EVT_BUTTON, self._on_save)

    def _on_defaults(self, _):
        self.cfg = CatalogConfig()  # fresh defaults
        self._load_into_ui()

    def _load_into_ui(self):
        # General
        gen = self.cfg.general()
        self.txt_default_policy.SetValue(str(gen.get("default_policy", "")))
        self.cbo_nullable.SetStringSelection(gen.get("nullable_default", "No"))
        self.cbo_analysis_mode.SetStringSelection(gen.get("analysis_date_mode", "Auto Today"))
        self.spn_profile_rows.SetValue(int(gen.get("profile_sample_rows", 10000)))

        # Regex grid
        self._fill_grid(self.grid_regex, self.cfg.regex_presets().items())

        # DType grid
        self._fill_grid(self.grid_dtype, self.cfg.dtype_presets().items())

        # AI
        ai = self.cfg.data.get("ai", {})
        self.chk_json_only.SetValue(bool(ai.get("enforce_json_only", True)))
        self.spn_temperature.SetValue(float(ai.get("temperature", 0.2)))
        self.spn_max_tokens.SetValue(int(ai.get("max_tokens", 800)))

    def _fill_grid(self, grid: gridlib.Grid, items):
        # rebuild rows
        if grid.GetNumberRows() > 0:
            grid.DeleteRows(0, grid.GetNumberRows())
        pairs: List[Tuple[str, str]] = [(k, v) for k, v in items]
        if not pairs:
            grid.AppendRows(1)
        else:
            grid.AppendRows(len(pairs))
            for i, (k, v) in enumerate(pairs):
                grid.SetCellValue(i, 0, str(k))
                grid.SetCellValue(i, 1, str(v))

    def _collect_grid(self, grid: gridlib.Grid) -> Dict[str, str]:
        out: Dict[str, str] = {}
        rows = grid.GetNumberRows()
        for r in range(rows):
            key = grid.GetCellValue(r, 0).strip()
            val = grid.GetCellValue(r, 1).strip()
            if key:
                out[key] = val
        return out

    def _on_save(self, _):
        # Push UI → cfg
        gen = self.cfg.general()
        gen["default_policy"] = self.txt_default_policy.GetValue().strip() or "Standard"
        gen["nullable_default"] = self.cbo_nullable.GetStringSelection() or "No"
        gen["analysis_date_mode"] = self.cbo_analysis_mode.GetStringSelection() or "Auto Today"
        gen["profile_sample_rows"] = int(self.spn_profile_rows.GetValue())

        self.cfg.data["presets"]["regex"] = self._collect_grid(self.grid_regex)
        self.cfg.data["presets"]["data_types"] = self._collect_grid(self.grid_dtype)

        ai = self.cfg.data["ai"]
        ai["enforce_json_only"] = bool(self.chk_json_only.GetValue())
        ai["temperature"] = float(self.spn_temperature.GetValue())
        ai["max_tokens"] = int(self.spn_max_tokens.GetValue())

        ok, msg = self.cfg.validate()
        if not ok:
            wx.MessageBox(msg, "Validation Error", style=wx.ICON_ERROR | wx.OK)
            return

        path = self.cfg.save()
        wx.MessageBox(f"Catalog configuration saved:\n{path}", "Saved", style=wx.OK | wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)
