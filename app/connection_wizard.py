import wx
import pandas as pd

# ---------------------------------------------------------------------
# ConnectionWizard
# A simple 3-step wizard:
#  1. Choose data source type
#  2. Configure/Load the data
#  3. Preview & Import
# ---------------------------------------------------------------------

class ConnectionWizard(wx.Frame):
    def __init__(self, parent, on_import=None):
        super().__init__(parent, title="Connections Wizard",
                         size=(800, 600))

        self.on_import = on_import
        self.df_preview = None

        panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="CatalogIQ Data Import Wizard")
        title.SetFont(wx.Font(16, wx.FONTFAMILY_SWISS,
                              wx.FONTSTYLE_NORMAL,
                              wx.FONTWEIGHT_BOLD))
        self.sizer.add(title, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Step container
        self.step_panel = wx.Panel(panel)
        self.step_sizer = wx.BoxSizer(wx.VERTICAL)
        self.step_panel.SetSizer(self.step_sizer)
        self.sizer.Add(self.step_panel, 1, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(self.sizer)

        self._build_step_1()

        self.Centre()
        self.Show()

    # ------------------------------------------------------------------
    # STEP 1 – choose source
    # ------------------------------------------------------------------
    def _build_step_1(self):
        self.step_sizer.Clear(True)

        text = wx.StaticText(self.step_panel,
                             label="Select the data source:")
        text.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS,
                             wx.FONTSTYLE_NORMAL,
                             wx.FONTWEIGHT_BOLD))
        self.step_sizer.Add(text, 0, wx.ALL, 5)

        # Buttons
        choices = [
            ("📁 Local CSV File", self._step_2_csv),
            ("🟣 Microsoft Purview (Preview)", self._step_2_purview),
            ("🟦 Microsoft Fabric OneLake (Preview)", self._step_2_fabric),
        ]

        for label, handler in choices:
            btn = wx.Button(self.step_panel, label=label, size=(260, 40))
            btn.Bind(wx.EVT_BUTTON, handler)
            self.step_sizer.Add(btn, 0, wx.ALL, 4)

        self.step_panel.Layout()

    # ------------------------------------------------------------------
    # STEP 2A – CSV loader
    # ------------------------------------------------------------------
    def _step_2_csv(self, _):
        self.step_sizer.Clear(True)

        title = wx.StaticText(self.step_panel, label="Load CSV File")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS,
                              wx.FONTSTYLE_NORMAL,
                              wx.FONTWEIGHT_BOLD))
        self.step_sizer.Add(title, 0, wx.ALL, 6)

        load_btn = wx.Button(self.step_panel, label="Select CSV File")
        load_btn.Bind(wx.EVT_BUTTON, self._load_csv)
        self.step_sizer.Add(load_btn, 0, wx.ALL, 6)

        self._add_back_button()
        self.step_panel.Layout()

    def _load_csv(self, _):
        dlg = wx.FileDialog(self, "Select CSV", wildcard="*.csv")
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return

        path = dlg.GetPath()
        dlg.Destroy()

        try:
            df = pd.read_csv(path)
            self.df_preview = df
            self._step_3_preview()
        except Exception as e:
            wx.MessageBox("Error loading CSV:\n" + str(e),
                          "Error", wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------
    # STEP 2B – Purview placeholder
    # ------------------------------------------------------------------
    def _step_2_purview(self, _):
        self.step_sizer.Clear(True)

        msg = wx.StaticText(
            self.step_panel,
            label="Purview connector will authenticate using OAuth\n"
                  "and pull metadata / sample rows.\n\n"
                  "This feature is currently a UI placeholder."
        )
        self.step_sizer.Add(msg, 0, wx.ALL, 6)

        dummy_btn = wx.Button(self.step_panel, label="Load Example Data")
        dummy_btn.Bind(wx.EVT_BUTTON, self._load_dummy)
        self.step_sizer.Add(dummy_btn, 0, wx.ALL, 6)

        self._add_back_button()
        self.step_panel.Layout()

    # ------------------------------------------------------------------
    # STEP 2C – Fabric placeholder
    # ------------------------------------------------------------------
    def _step_2_fabric(self, _):
        self.step_sizer.Clear(True)

        msg = wx.StaticText(
            self.step_panel,
            label="Fabric OneLake connection will authenticate with Azure\n"
                  "and pull Parquet/CSV from Lakehouse.\n\n"
                  "This screen is a placeholder."
        )
        self.step_sizer.Add(msg, 0, wx.ALL, 6)

        dummy_btn = wx.Button(self.step_panel, label="Load Example Data")
        dummy_btn.Bind(wx.EVT_BUTTON, self._load_dummy)
        self.step_sizer.Add(dummy_btn, 0, wx.ALL, 6)

        self._add_back_button()
        self.step_panel.Layout()

    # ------------------------------------------------------------------
    # Dummy content for placeholders
    # ------------------------------------------------------------------
    def _load_dummy(self, _):
        df = pd.DataFrame({
            "Field": ["Email", "Address", "LoanAmount"],
            "ValueType": ["string", "string", "number"],
            "Sample": ["test@example.com", "123 Main St", "250000"]
        })
        self.df_preview = df
        self._step_3_preview()

    # ------------------------------------------------------------------
    # STEP 3 – preview and import
    # ------------------------------------------------------------------
    def _step_3_preview(self):
        self.step_sizer.Clear(True)

        title = wx.StaticText(self.step_panel, label="Preview Data")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_SWISS,
                              wx.FONTSTYLE_NORMAL,
                              wx.FONTWEIGHT_BOLD))
        self.step_sizer.Add(title, 0, wx.ALL, 6)

        if self.df_preview is None:
            self.step_sizer.Add(wx.StaticText(self.step_panel,
                                             label="(No data loaded)"),
                                0, wx.ALL, 6)
        else:
            grid = wx.Grid(self.step_panel)
            grid.CreateGrid(len(self.df_preview), len(self.df_preview.columns))

            for c, col in enumerate(self.df_preview.columns):
                grid.SetColLabelValue(c, col)

            for r in range(len(self.df_preview)):
                for c, col in enumerate(self.df_preview.columns):
                    grid.SetCellValue(r, c, str(self.df_preview.iloc[r, c]))

            grid.SetDefaultCellBackgroundColour(wx.Colour(230, 230, 235))
            grid.SetLabelBackgroundColour(wx.Colour(200, 200, 210))
            grid.AutoSizeColumns()

            self.step_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 8)

        import_btn = wx.Button(self.step_panel,
                               label="✅ Import into CatalogIQ")
        import_btn.SetBackgroundColour(wx.Colour(0, 120, 90))
        import_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        import_btn.Bind(wx.EVT_BUTTON, self._import)
        self.step_sizer.Add(import_btn, 0, wx.ALL, 6)

        self._add_back_button()
        self.step_panel.Layout()

    # ------------------------------------------------------------------
    # Import to parent
    # ------------------------------------------------------------------
    def _import(self, _):
        if self.df_preview is None:
            wx.MessageBox("No data to import.", "Import Error",
                          wx.OK | wx.ICON_ERROR)
            return

        if callable(self.on_import):
            self.on_import(self.df_preview)

        self.Close()

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------
    def _add_back_button(self):
        back = wx.Button(self.step_panel, label="← Back")
        back.Bind(wx.EVT_BUTTON, lambda evt: self._build_step_1())
        self.step_sizer.Add(back, 0, wx.ALL, 6)
