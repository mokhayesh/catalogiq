# =====================================================================
#  CatalogIQ — Import Preview Dialog (A1: Popup Version)
# =====================================================================

import wx
import wx.grid as gridlib
import pandas as pd


DARK_BG   = wx.Colour(38, 38, 46)
PANEL_BG  = wx.Colour(48, 48, 56)
HEADER_FG = wx.Colour(240, 240, 245)
GRID_BG   = wx.Colour(44, 44, 52)
GRID_TXT  = wx.Colour(230, 230, 235)
BTN_BG    = wx.Colour(86, 70, 180)
BTN_FG    = wx.Colour(255, 255, 255)
LINE_COL  = wx.Colour(80, 80, 90)


class ImportPreviewDialog(wx.Dialog):
    """
    Excel / PowerBI style import preview window.
    Shows:
      - Left: Schema preview with data types
      - Right: Data preview (first 50 rows)
    """

    def __init__(self, parent, df: pd.DataFrame, title="Preview Import"):
        super().__init__(parent, title=title, size=(1200, 750))

        self.df = df.head(50).copy()          # preview sample
        self.schema_info = self._infer_schema(df)

        self.SetBackgroundColour(PANEL_BG)

        outer = wx.BoxSizer(wx.HORIZONTAL)

        # ==================================================================
        # LEFT — SCHEMA PREVIEW
        # ==================================================================
        left = wx.Panel(self)
        left.SetBackgroundColour(DARK_BG)
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(left, label="Detected Schema")
        header.SetForegroundColour(HEADER_FG)
        header.SetFont(wx.Font(13, wx.FONTFAMILY_SWISS,
                               wx.FONTSTYLE_NORMAL,
                               wx.FONTWEIGHT_BOLD))
        left_sizer.Add(header, 0, wx.ALL, 10)

        self.schema_grid = gridlib.Grid(left)
        self.schema_grid.CreateGrid(len(self.schema_info), 4)
        self.schema_grid.SetColLabelValue(0, "Include")
        self.schema_grid.SetColLabelValue(1, "Column")
        self.schema_grid.SetColLabelValue(2, "Data Type")
        self.schema_grid.SetColLabelValue(3, "Example Value")

        self.schema_grid.SetDefaultCellBackgroundColour(GRID_BG)
        self.schema_grid.SetDefaultCellTextColour(GRID_TXT)
        self.schema_grid.SetGridLineColour(LINE_COL)
        self.schema_grid.SetLabelBackgroundColour(wx.Colour(30, 30, 36))
        self.schema_grid.SetLabelTextColour(HEADER_FG)

        for i, col in enumerate(self.schema_info):
            include_checkbox = "1"
            self.schema_grid.SetCellValue(i, 0, include_checkbox)
            self.schema_grid.SetReadOnly(i, 0, False)

            self.schema_grid.SetCellValue(i, 1, col["name"])
            self.schema_grid.SetReadOnly(i, 1)

            self.schema_grid.SetCellValue(i, 2, col["dtype"])
            self.schema_grid.SetReadOnly(i, 2)

            self.schema_grid.SetCellValue(i, 3, col["example"])
            self.schema_grid.SetReadOnly(i, 3)

        left_sizer.Add(self.schema_grid, 1, wx.EXPAND | wx.ALL, 5)
        left.SetSizer(left_sizer)

        outer.Add(left, 0, wx.EXPAND | wx.ALL, 5)

        # ==================================================================
        # RIGHT — DATA PREVIEW GRID
        # ==================================================================
        right = wx.Panel(self)
        right.SetBackgroundColour(PANEL_BG)
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(right, label="Data Preview (First 50 rows)")
        title.SetForegroundColour(HEADER_FG)
        title.SetFont(wx.Font(13, wx.FONTFAMILY_SWISS,
                              wx.FONTSTYLE_NORMAL,
                              wx.FONTWEIGHT_BOLD))
        right_sizer.Add(title, 0, wx.ALL, 10)

        # table
        self.data_grid = gridlib.Grid(right)
        self.data_grid.CreateGrid(self.df.shape[0], self.df.shape[1])

        # Set column names
        for idx, name in enumerate(self.df.columns):
            self.data_grid.SetColLabelValue(idx, str(name))

        self.data_grid.SetDefaultCellBackgroundColour(GRID_BG)
        self.data_grid.SetDefaultCellTextColour(GRID_TXT)
        self.data_grid.SetGridLineColour(LINE_COL)
        self.data_grid.SetLabelBackgroundColour(wx.Colour(30, 30, 36))
        self.data_grid.SetLabelTextColour(HEADER_FG)

        # Populate cells
        for r in range(self.df.shape[0]):
            for c in range(self.df.shape[1]):
                val = str(self.df.iat[r, c])
                self.data_grid.SetCellValue(r, c, val)

        right_sizer.Add(self.data_grid, 1, wx.EXPAND | wx.ALL, 5)
        right.SetSizer(right_sizer)

        outer.Add(right, 1, wx.EXPAND | wx.ALL, 5)

        # ==================================================================
        # BUTTON BAR
        # ==================================================================
        btns = wx.BoxSizer(wx.HORIZONTAL)

        btn_import = wx.Button(self, label="✅ Import Into Catalog")
        btn_import.SetBackgroundColour(BTN_BG)
        btn_import.SetForegroundColour(BTN_FG)
        btn_import.Bind(wx.EVT_BUTTON, self._on_import)

        btn_cancel = wx.Button(self, label="✖ Cancel")
        btn_cancel.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))

        btns.Add(btn_import, 0, wx.ALL, 10)
        btns.Add(btn_cancel, 0, wx.ALL, 10)

        main = wx.BoxSizer(wx.VERTICAL)
        main.Add(outer, 1, wx.EXPAND)
        main.Add(btns, 0, wx.ALIGN_RIGHT)

        self.SetSizer(main)
        self.Layout()

    # ==================================================================
    # Infer data types + examples
    # ==================================================================
    def _infer_schema(self, df: pd.DataFrame):
        schema = []

        for col in df.columns:
            series = df[col]
            dtype = str(series.dtype)

            example = ""
            for v in series:
                if str(v).strip() not in ("", "nan", "None"):
                    example = str(v)
                    break

            schema.append({
                "name": col,
                "dtype": dtype,
                "example": example
            })
        return schema

    # ==================================================================
    # Import handler
    # ==================================================================
    def _on_import(self, _):
        selected_cols = []
        for r in range(self.schema_grid.GetNumberRows()):
            include = self.schema_grid.GetCellValue(r, 0).strip() == "1"
            if include:
                selected_cols.append(self.schema_grid.GetCellValue(r, 1))

        if not selected_cols:
            wx.MessageBox("No columns selected!", "Error", wx.ICON_ERROR)
            return

        self.selected_df = self.df[selected_cols].copy()
        self.EndModal(wx.ID_OK)

    # ==================================================================
    # Retrieve imported dataframe
    # ==================================================================
    def get_imported_dataframe(self):
        return getattr(self, "selected_df", None)

