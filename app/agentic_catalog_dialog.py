from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path

import pandas as pd
import wx
import wx.grid as gridlib

try:
    from .platform_core import (
        agent_recommendations,
        answer_agent_question,
        export_catalog_package,
        load_workspace_asset,
        load_workspace_index,
        profile_dataset,
        profile_dataframe,
        profile_scorecard_df,
        profile_to_catalog_df,
        profile_to_dictionary_df,
        profile_to_glossary_df,
        publish_to_local_workspace,
        risk_level,
        workspace_assets_df,
    )
except Exception:  # pragma: no cover - standalone fallback
    from platform_core import (  # type: ignore
        agent_recommendations,
        answer_agent_question,
        export_catalog_package,
        load_workspace_asset,
        load_workspace_index,
        profile_dataset,
        profile_dataframe,
        profile_scorecard_df,
        profile_to_catalog_df,
        profile_to_dictionary_df,
        profile_to_glossary_df,
        publish_to_local_workspace,
        risk_level,
        workspace_assets_df,
    )

try:
    from .enterprise_connectors import read_s3_dataset, read_snowflake_dataset
except Exception:  # pragma: no cover - standalone fallback
    from enterprise_connectors import read_s3_dataset, read_snowflake_dataset  # type: ignore


class AgenticCatalogDialog(wx.Dialog):
    """CatalogIQ Phase 4B Enterprise Agentic Catalog Workspace.

    Enterprise workspace for connecting to datasets, profiling them, publishing local data assets, reopening saved assets, reviewing lineage/policies, and asking catalog/governance questions.
    """

    def __init__(self, parent=None):
        super().__init__(
            parent,
            title="CatalogIQ Platform Core v7 — Enterprise Connectors",
            size=(1500, 900),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX,
        )
        self.df: pd.DataFrame | None = None
        self.profile = None
        self.source_path = ""
        self.connected_dataset_name = ""
        self.connected_connector = "Local File"
        self.last_package_dir: Path | None = None
        self.workspace_dir = os.path.join(os.getcwd(), "catalogiq_workspace")
        self.workspace_assets: list[dict] = []
        self._build_ui()
        self._refresh_workspace_assets()
        wx.CallAfter(self._auto_open_from_launcher)
        self.CentreOnParent()

    def _build_ui(self):
        root = wx.BoxSizer(wx.VERTICAL)

        hero = wx.Panel(self)
        hero.SetBackgroundColour("#0B1220")
        hs = wx.BoxSizer(wx.HORIZONTAL)
        copy = wx.BoxSizer(wx.VERTICAL)
        title = wx.StaticText(hero, label="CatalogIQ Platform Core v7")
        title.SetForegroundColour("#F8FAFC")
        title.SetFont(wx.Font(22, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        subtitle = wx.StaticText(hero, label="Enterprise catalog agent with active CSV/Excel, AWS S3, and Snowflake connectors plus governance, lineage, DQ, and AI-ready metadata.")
        subtitle.SetForegroundColour("#CBD5E1")
        copy.Add(title, 0, wx.BOTTOM, 7)
        copy.Add(subtitle, 0, wx.BOTTOM, 2)
        hs.Add(copy, 1, wx.ALL | wx.EXPAND, 18)
        self.btn_close = wx.Button(hero, wx.ID_CLOSE, label="Close")
        hs.Add(self.btn_close, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 16)
        hero.SetSizer(hs)
        root.Add(hero, 0, wx.EXPAND)

        body = wx.BoxSizer(wx.HORIZONTAL)

        left = wx.Panel(self)
        left.SetBackgroundColour("#F8FAFC")
        ls = wx.BoxSizer(wx.VERTICAL)
        step_label = wx.StaticText(left, label="AGENT ACTIONS")
        step_label.SetForegroundColour("#475569")
        step_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        ls.Add(step_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)

        self.btn_open = self._side_button(left, "1. Connect Dataset")
        self.btn_profile = self._side_button(left, "2. Auto Profile")
        self.btn_metadata = self._side_button(left, "3. Generate Views")
        self.btn_export = self._side_button(left, "4. Export Package")
        self.btn_publish = self._side_button(left, "5. Publish Local Asset")
        self.btn_open_pkg = self._side_button(left, "Open Last Package")
        self.btn_open_workspace = self._side_button(left, "Open Workspace Folder")

        workflow_label = wx.StaticText(left, label="ENTERPRISE WORKFLOWS")
        workflow_label.SetForegroundColour("#475569")
        workflow_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))

        self.btn_connector_hub = self._side_button(left, "Connector Hub")
        self.btn_product_detail = self._side_button(left, "Data Product Detail")
        self.btn_governance_review = self._side_button(left, "Governance Review")
        self.btn_find_pii = self._side_button(left, "Find PII / Sensitive")
        self.btn_generate_dq = self._side_button(left, "Generate DQ Rules")

        for b in [self.btn_open, self.btn_profile, self.btn_metadata, self.btn_export, self.btn_publish, self.btn_open_pkg, self.btn_open_workspace]:
            ls.Add(b, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        ls.Add(workflow_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)
        for b in [self.btn_connector_hub, self.btn_product_detail, self.btn_governance_review, self.btn_find_pii, self.btn_generate_dq]:
            ls.Add(b, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        ls.AddSpacer(14)
        self.kpi_score = self._kpi(left, "Readiness", "--")
        self.kpi_risk = self._kpi(left, "Risk", "--")
        self.kpi_fields = self._kpi(left, "Fields", "--")
        self.kpi_sensitive = self._kpi(left, "Sensitive", "--")
        for k in [self.kpi_score, self.kpi_risk, self.kpi_fields, self.kpi_sensitive]:
            ls.Add(k, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        ls.AddStretchSpacer()
        left.SetSizer(ls)
        body.Add(left, 0, wx.EXPAND)

        center = wx.Panel(self)
        cs = wx.BoxSizer(wx.VERTICAL)
        self.summary = wx.StaticText(center, label="No dataset connected yet. Start with Connect Dataset or open a saved workspace asset.")
        self.summary.SetFont(wx.Font(11, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.summary.Wrap(850)
        cs.Add(self.summary, 0, wx.EXPAND | wx.ALL, 12)

        self.notebook = wx.Notebook(center)
        self.grid_scorecard = self._make_grid_page("Scorecard")
        self.grid_catalog = self._make_grid_page("Catalog")
        self.grid_glossary = self._make_grid_page("Business Glossary")
        self.grid_dictionary = self._make_grid_page("Data Dictionary")
        self.grid_findings = self._make_grid_page("Governance Findings")
        self.grid_lineage = self._make_grid_page("Lineage")
        self.grid_policies = self._make_grid_page("Policy Review")
        self.log = wx.TextCtrl(self.notebook, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE)
        self.notebook.AddPage(self.log, "Agent Console")
        cs.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        center.SetSizer(cs)
        body.Add(center, 1, wx.EXPAND)

        right = wx.Panel(self)
        right.SetBackgroundColour("#F8FAFC")
        rs = wx.BoxSizer(wx.VERTICAL)
        ws_label = wx.StaticText(right, label="WORKSPACE ASSETS")
        ws_label.SetForegroundColour("#475569")
        ws_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        rs.Add(ws_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.asset_list = wx.ListBox(right)
        rs.Add(self.asset_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        self.btn_refresh_assets = self._side_button(right, "Refresh Assets")
        self.btn_open_asset = self._side_button(right, "Open Selected Asset")
        rs.Add(self.btn_refresh_assets, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        rs.Add(self.btn_open_asset, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        rec_label = wx.StaticText(right, label="AGENT RECOMMENDATIONS")
        rec_label.SetForegroundColour("#475569")
        rec_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        rs.Add(rec_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)
        self.recommendations = wx.TextCtrl(right, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE)
        self.recommendations.SetMinSize((300, 180))
        rs.Add(self.recommendations, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)

        ask_label = wx.StaticText(right, label="ASK CATALOGIQ AGENT")
        ask_label.SetForegroundColour("#475569")
        ask_label.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        rs.Add(ask_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 18)
        self.agent_question = wx.TextCtrl(right, value="explain risk and suggest next actions", style=wx.TE_PROCESS_ENTER)
        self.btn_ask = self._side_button(right, "Run Agent Question")
        rs.Add(self.agent_question, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12)
        rs.Add(self.btn_ask, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        right.SetSizer(rs)
        body.Add(right, 0, wx.EXPAND)

        root.Add(body, 1, wx.EXPAND)
        self.SetSizer(root)

        self.btn_open.Bind(wx.EVT_BUTTON, self._connect_dataset)
        self.btn_profile.Bind(wx.EVT_BUTTON, self._auto_profile)
        self.btn_metadata.Bind(wx.EVT_BUTTON, self._generate_metadata)
        self.btn_export.Bind(wx.EVT_BUTTON, self._export_package)
        self.btn_publish.Bind(wx.EVT_BUTTON, self._publish_local)
        self.btn_open_pkg.Bind(wx.EVT_BUTTON, self._open_last_package)
        self.btn_open_workspace.Bind(wx.EVT_BUTTON, lambda evt: self._open_folder(Path(self.workspace_dir)))
        self.btn_connector_hub.Bind(wx.EVT_BUTTON, self._open_connector_hub)
        self.btn_product_detail.Bind(wx.EVT_BUTTON, self._show_data_product_detail)
        self.btn_governance_review.Bind(wx.EVT_BUTTON, self._run_governance_review)
        self.btn_find_pii.Bind(wx.EVT_BUTTON, self._quick_find_sensitive)
        self.btn_generate_dq.Bind(wx.EVT_BUTTON, self._quick_generate_dq)
        self.btn_refresh_assets.Bind(wx.EVT_BUTTON, lambda evt: self._refresh_workspace_assets())
        self.btn_open_asset.Bind(wx.EVT_BUTTON, self._open_selected_asset)
        self.btn_ask.Bind(wx.EVT_BUTTON, self._ask_agent)
        self.agent_question.Bind(wx.EVT_TEXT_ENTER, self._ask_agent)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))

        self.btn_profile.Enable(False)
        self.btn_metadata.Enable(False)
        self.btn_export.Enable(False)
        self.btn_publish.Enable(False)
        self.btn_open_pkg.Enable(False)

    def _side_button(self, parent, label: str) -> wx.Button:
        b = wx.Button(parent, label=label)
        b.SetMinSize((210, 42))
        return b

    def _kpi(self, parent, label: str, value: str) -> wx.Panel:
        p = wx.Panel(parent)
        p.SetBackgroundColour("#FFFFFF")
        s = wx.BoxSizer(wx.VERTICAL)
        l = wx.StaticText(p, label=label.upper())
        l.SetForegroundColour("#64748B")
        l.SetFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        v = wx.StaticText(p, label=value)
        v.SetForegroundColour("#0F172A")
        v.SetFont(wx.Font(17, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        p.value = v  # type: ignore[attr-defined]
        s.Add(l, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        s.Add(v, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        p.SetSizer(s)
        return p

    def _make_grid_page(self, label: str) -> gridlib.Grid:
        panel = wx.Panel(self.notebook)
        s = wx.BoxSizer(wx.VERTICAL)
        g = gridlib.Grid(panel)
        g.CreateGrid(0, 0)
        g.EnableEditing(False)
        g.SetRowLabelSize(34)
        g.SetColLabelSize(30)
        s.Add(g, 1, wx.EXPAND | wx.ALL, 4)
        panel.SetSizer(s)
        self.notebook.AddPage(panel, label)
        return g

    def _log(self, msg: str):
        self.log.AppendText(msg.rstrip() + "\n")

    def _connect_dataset(self, _evt):
        wildcard = "Data files (*.csv;*.txt;*.xlsx;*.xls)|*.csv;*.txt;*.xlsx;*.xls|CSV (*.csv)|*.csv|Excel (*.xlsx;*.xls)|*.xlsx;*.xls|All files (*.*)|*.*"
        with wx.FileDialog(self, "Choose a dataset", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            self.source_path = dlg.GetPath()
        try:
            self._log(f"[1/5] Connecting local dataset: {self.source_path}")
            from .platform_core import read_dataset
            self.df = read_dataset(self.source_path)
            self.connected_dataset_name = Path(self.source_path).stem
            self.connected_connector = "Local File"
            self.summary.SetLabel(f"Connected Local File: {Path(self.source_path).name} | Rows: {len(self.df):,} | Columns: {len(self.df.columns):,}")
            self.summary.Wrap(850)
            self.btn_profile.Enable(True)
            self._log("[OK] Local dataset connected. Next: Auto Profile.")
        except Exception as e:
            self._show_error("Connect Dataset failed", e)

    def _auto_profile(self, _evt):
        if not self.source_path:
            wx.MessageBox("Connect a dataset first.", "CatalogIQ")
            return
        try:
            self._log(f"[2/5] Profiling {self.connected_connector} dataset: schema, nulls, uniqueness, PII, sensitivity, and DQ candidates...")
            if self.df is not None:
                dataset_name = self.connected_dataset_name or (Path(self.source_path).stem if self.source_path else "connected_dataset")
                self.profile = profile_dataframe(self.df, dataset_name=dataset_name, source_path=self.source_path)
            else:
                self.df, self.profile = profile_dataset(self.source_path)
            self.summary.SetLabel(self.profile.executive_summary)
            self.summary.Wrap(850)
            self._render_profile()
            self._update_kpis()
            self._refresh_recommendations()
            self.btn_metadata.Enable(True)
            self.btn_export.Enable(True)
            self.btn_publish.Enable(True)
            self._log("[OK] Profile complete. Review Scorecard, Catalog, Dictionary, Glossary, and Governance Findings.")
        except Exception as e:
            self._show_error("Auto Profile failed", e)

    def _generate_metadata(self, _evt):
        if not self.profile:
            wx.MessageBox("Run Auto Profile first.", "CatalogIQ")
            return
        self._log("[3/5] Generating premium metadata views...")
        self._render_profile()
        self._update_kpis()
        self._refresh_recommendations()
        self.notebook.SetSelection(0)
        self._log("[OK] Metadata views refreshed.")

    def _export_package(self, _evt):
        if not self.profile:
            wx.MessageBox("Run Auto Profile first.", "CatalogIQ")
            return
        default_dir = os.path.join(os.getcwd(), "outputs")
        os.makedirs(default_dir, exist_ok=True)
        with wx.DirDialog(self, "Choose export folder", defaultPath=default_dir, style=wx.DD_DEFAULT_STYLE) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            out_dir = dlg.GetPath()
        try:
            self._log("[4/5] Exporting premium data product package...")
            self.last_package_dir = export_catalog_package(self.profile, out_dir)
            self.btn_open_pkg.Enable(True)
            self._log(f"[OK] Exported package: {self.last_package_dir}")
            self._log("[OK] Package includes index.html, manifest, summary, publish payload, DQ SQL, Excel, and CSV views.")
            wx.MessageBox(f"Catalog package exported:\n\n{self.last_package_dir}", "CatalogIQ Export Complete")
        except Exception as e:
            self._show_error("Export Package failed", e)

    def _publish_local(self, _evt):
        if not self.profile:
            wx.MessageBox("Run Auto Profile first.", "CatalogIQ")
            return
        try:
            self._log("[5/5] Publishing data asset to local CatalogIQ workspace index...")
            asset_path = publish_to_local_workspace(self.profile, self.workspace_dir)
            self._log(f"[OK] Published local asset: {asset_path}")
            self._refresh_workspace_assets()
            wx.MessageBox(f"Published to local CatalogIQ workspace:\n\n{asset_path}", "CatalogIQ Publish Complete")
        except Exception as e:
            self._show_error("Publish Local Asset failed", e)

    def _open_last_package(self, _evt):
        if not self.last_package_dir or not self.last_package_dir.exists():
            wx.MessageBox("No exported package folder found yet.", "CatalogIQ")
            return
        self._open_folder(self.last_package_dir)

    def _open_folder(self, folder: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            self._show_error("Open Folder failed", e)

    def _refresh_workspace_assets(self):
        try:
            index = load_workspace_index(self.workspace_dir)
            self.workspace_assets = list(index.get("assets", []))
            labels = []
            for a in self.workspace_assets:
                labels.append(f"{a.get('dataset_name', 'Dataset')}  |  {a.get('risk_level', '--')}  |  {a.get('readiness_score', '--')}/100")
            self.asset_list.Set(labels)
            self._log(f"[OK] Workspace refreshed. {len(labels)} asset(s) available.")
        except Exception as e:
            self._show_error("Refresh Workspace failed", e)


    def _auto_open_from_launcher(self):
        """Open a workspace asset or run a starting command from the v6 Command Center."""
        asset_file = os.environ.get("CATALOGIQ_OPEN_ASSET_FILE", "").strip()
        if asset_file:
            self._open_asset_file(asset_file, source="Command Center")
        start_cmd = os.environ.get("CATALOGIQ_START_COMMAND", "").strip().lower()
        if start_cmd:
            wx.CallLater(450, self._run_start_command, start_cmd)

    def _run_start_command(self, start_cmd: str):
        if "connector" in start_cmd:
            self._open_connector_hub(None)
        elif "governance" in start_cmd:
            self._run_governance_review(None)
        elif "dq" in start_cmd or "quality" in start_cmd:
            self._quick_generate_dq(None)
        elif "pii" in start_cmd or "sensitive" in start_cmd:
            self._quick_find_sensitive(None)
        elif "detail" in start_cmd:
            self._show_data_product_detail(None)

    def _open_asset_file(self, asset_file: str, source: str = "Workspace"):
        try:
            self.profile = load_workspace_asset(asset_file)
            self.df = None
            self.source_path = self.profile.source_path
            self.summary.SetLabel(self.profile.executive_summary)
            self.summary.Wrap(850)
            self._render_profile()
            self._update_kpis()
            self._refresh_recommendations()
            self.btn_export.Enable(True)
            self.btn_publish.Enable(True)
            self.btn_metadata.Enable(True)
            self.notebook.SetSelection(0)
            self._log(f"[OK] Opened workspace asset from {source}: {self.profile.dataset_name}")
        except Exception as e:
            self._show_error("Open Workspace Asset failed", e)

    def _open_selected_asset(self, _evt):
        idx = self.asset_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.workspace_assets):
            wx.MessageBox("Select a workspace asset first.", "CatalogIQ")
            return
        asset = self.workspace_assets[idx]
        self._open_asset_file(asset.get("asset_file", ""), source="Workspace panel")

    def _open_connector_hub(self, _evt):
        """Connector hub with active Local File, AWS S3, and Snowflake starter connectors."""
        choices = [
            "Local File — CSV / TXT / Excel (active)",
            "AWS S3 — CSV / TXT / Excel object (active)",
            "Snowflake — table or SQL query (active)",
            "Postgres / SQL Server (next connector)",
            "Databricks / Unity Catalog (roadmap)",
            "API / JSON endpoint (roadmap)",
        ]
        dlg = wx.SingleChoiceDialog(self, "Choose a connector type.", "CatalogIQ Connector Hub v7", choices)
        try:
            dlg.SetSelection(0)
            if dlg.ShowModal() != wx.ID_OK:
                return
            choice = dlg.GetStringSelection()
        finally:
            dlg.Destroy()
        if choice.startswith("Local File"):
            self._log("[CONNECTOR HUB] Local file connector selected. Opening dataset picker...")
            self._connect_dataset(None)
            return
        if choice.startswith("AWS S3"):
            self._connect_s3_dataset()
            return
        if choice.startswith("Snowflake"):
            self._connect_snowflake_dataset()
            return
        msg = (
            f"{choice}\n\n"
            "This connector is staged for the next enterprise expansion. The implementation path is: connection profile, test connection, schema browser, metadata ingestion adapter, and optional pushdown profiling."
        )
        self._log(f"[CONNECTOR HUB] Selected roadmap connector: {choice}")
        wx.MessageBox(msg, "CatalogIQ Connector Hub", wx.OK | wx.ICON_INFORMATION)

    def _connect_s3_dataset(self):
        """Collect S3 settings and load a CSV/TXT/Excel object into the profiler."""
        dlg = wx.Dialog(self, title="CatalogIQ AWS S3 Connector", size=(720, 620), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        s = wx.BoxSizer(wx.VERTICAL)
        note = wx.StaticText(dlg, label="Connect to an S3 object. Credentials are used for this session only and are not saved. You can use an AWS profile/environment credentials or paste temporary keys.")
        note.Wrap(660)
        s.Add(note, 0, wx.ALL | wx.EXPAND, 12)
        grid = wx.FlexGridSizer(0, 2, 8, 10)
        grid.AddGrowableCol(1, 1)
        fields = {}
        specs = [
            ("bucket", "Bucket", ""),
            ("key", "Object key", ""),
            ("region", "Region", "us-east-1"),
            ("profile_name", "AWS profile name (optional)", ""),
            ("access_key_id", "Access key ID (optional)", ""),
            ("secret_access_key", "Secret access key (optional)", ""),
            ("session_token", "Session token (optional)", ""),
            ("endpoint_url", "Endpoint URL (optional)", ""),
        ]
        for key, label, default in specs:
            grid.Add(wx.StaticText(dlg, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            style = wx.TE_PASSWORD if key == "secret_access_key" else 0
            txt = wx.TextCtrl(dlg, value=default, style=style)
            fields[key] = txt
            grid.Add(txt, 1, wx.EXPAND)
        s.Add(grid, 1, wx.ALL | wx.EXPAND, 12)
        btns = dlg.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        s.Add(btns, 0, wx.ALL | wx.EXPAND, 12)
        dlg.SetSizer(s)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        params = {k: v.GetValue() for k, v in fields.items()}
        dlg.Destroy()
        try:
            self._log(f"[S3 CONNECTOR] Downloading s3://{params.get('bucket')}/{params.get('key')} ...")
            result = read_s3_dataset(**params)
            self.df = result.dataframe
            self.source_path = result.source_label
            self.connected_dataset_name = result.dataset_name
            self.connected_connector = "AWS S3"
            self.summary.SetLabel(f"Connected AWS S3: {result.source_label} | Rows: {len(self.df):,} | Columns: {len(self.df.columns):,}")
            self.summary.Wrap(850)
            self.btn_profile.Enable(True)
            self._log(f"[OK] S3 object loaded. Cached copy: {result.cached_file}")
            self._log("[OK] Next: Auto Profile.")
        except Exception as e:
            self._show_error("AWS S3 Connector failed", e)

    def _connect_snowflake_dataset(self):
        """Collect Snowflake settings and load a table/query into the profiler."""
        dlg = wx.Dialog(self, title="CatalogIQ Snowflake Connector", size=(760, 760), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        s = wx.BoxSizer(wx.VERTICAL)
        note = wx.StaticText(dlg, label="Connect to Snowflake and profile a starter sample. Password is used for this session only and is not saved. Enter either a table name or SQL query.")
        note.Wrap(700)
        s.Add(note, 0, wx.ALL | wx.EXPAND, 12)
        grid = wx.FlexGridSizer(0, 2, 8, 10)
        grid.AddGrowableCol(1, 1)
        fields = {}
        specs = [
            ("account", "Account", ""),
            ("user", "User", ""),
            ("password", "Password", ""),
            ("role", "Role (optional)", ""),
            ("warehouse", "Warehouse", ""),
            ("database", "Database", ""),
            ("schema", "Schema", "PUBLIC"),
            ("table", "Table name (optional if SQL is used)", ""),
            ("row_limit", "Row limit", "10000"),
        ]
        for key, label, default in specs:
            grid.Add(wx.StaticText(dlg, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            style = wx.TE_PASSWORD if key == "password" else 0
            txt = wx.TextCtrl(dlg, value=default, style=style)
            fields[key] = txt
            grid.Add(txt, 1, wx.EXPAND)
        s.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
        s.Add(wx.StaticText(dlg, label="SQL query (optional, used instead of table if provided)"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        sql_txt = wx.TextCtrl(dlg, value="", style=wx.TE_MULTILINE)
        sql_txt.SetMinSize((-1, 140))
        s.Add(sql_txt, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 12)
        btns = dlg.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL)
        s.Add(btns, 0, wx.ALL | wx.EXPAND, 12)
        dlg.SetSizer(s)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        params = {k: v.GetValue() for k, v in fields.items()}
        params["sql"] = sql_txt.GetValue()
        try:
            params["row_limit"] = int(params.get("row_limit") or 10000)
        except Exception:
            params["row_limit"] = 10000
        dlg.Destroy()
        try:
            target = params.get("table") or "SQL query"
            self._log(f"[SNOWFLAKE CONNECTOR] Connecting to Snowflake target: {target} ...")
            result = read_snowflake_dataset(**params)
            self.df = result.dataframe
            self.source_path = result.source_label
            self.connected_dataset_name = result.dataset_name
            self.connected_connector = "Snowflake"
            self.summary.SetLabel(f"Connected Snowflake: {result.source_label} | Rows: {len(self.df):,} | Columns: {len(self.df.columns):,}")
            self.summary.Wrap(850)
            self.btn_profile.Enable(True)
            self._log("[OK] Snowflake data loaded into CatalogIQ starter profiler. Next: Auto Profile.")
        except Exception as e:
            self._show_error("Snowflake Connector failed", e)

    def _show_data_product_detail(self, _evt):
        if not self.profile:
            wx.MessageBox("Open/profile a data asset first.", "CatalogIQ")
            return
        sensitive = [f for f in self.profile.fields if f.pii_flag == "Yes" or f.sensitivity in {"Confidential", "Restricted"}]
        text = (
            f"DATA PRODUCT DETAIL\n\n"
            f"Name: {self.profile.dataset_name}\n"
            f"Source: {self.profile.source_path}\n"
            f"Rows: {self.profile.row_count:,}\n"
            f"Fields: {self.profile.column_count:,}\n"
            f"Readiness: {self.profile.quality_score}/100\n"
            f"Risk: {risk_level(self.profile)}\n"
            f"Sensitive Fields: {len(sensitive)}\n\n"
            f"Executive Summary:\n{self.profile.executive_summary}\n\n"
            "Recommended Enterprise Actions:\n"
            "1. Confirm business owner and steward.\n"
            "2. Review sensitive fields and policy tags.\n"
            "3. Validate generated DQ rules with engineering.\n"
            "4. Export/publish the data product package.\n"
        )
        dlg = wx.Dialog(self, title="CatalogIQ Data Product Detail", size=(760, 620), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        s = wx.BoxSizer(wx.VERTICAL)
        txt = wx.TextCtrl(dlg, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY)
        s.Add(txt, 1, wx.EXPAND | wx.ALL, 12)
        btn = wx.Button(dlg, wx.ID_CLOSE, "Close")
        s.Add(btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 12)
        dlg.SetSizer(s)
        btn.Bind(wx.EVT_BUTTON, lambda evt: dlg.EndModal(wx.ID_CLOSE))
        dlg.ShowModal()
        dlg.Destroy()

    def _run_governance_review(self, _evt):
        if not self.profile:
            wx.MessageBox("Open/profile a data asset first.", "CatalogIQ")
            return
        self._render_profile()
        self.notebook.SetSelection(6)  # Policy Review tab
        sensitive = [f for f in self.profile.fields if f.pii_flag == "Yes" or f.sensitivity in {"Confidential", "Restricted"}]
        self._log("\n[GOVERNANCE REVIEW] Started policy and sensitivity review.")
        if sensitive:
            for f in sensitive:
                self._log(f"- {f.name}: {f.pii_category or 'Sensitive'} / {f.sensitivity} — confirm owner, policy tag, masking/access rule.")
        else:
            self._log("- No sensitive fields detected by starter scan. Confirm with the business data owner.")
        self._log("[GOVERNANCE REVIEW] Next: assign owner/steward, approve policies, export package.")

    def _quick_find_sensitive(self, _evt):
        if not self.profile:
            wx.MessageBox("Open/profile a data asset first.", "CatalogIQ")
            return
        sensitive = [f for f in self.profile.fields if f.pii_flag == "Yes" or f.sensitivity in {"Confidential", "Restricted"}]
        self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
        self._log("\n[AGENT ACTION] Find PII / Sensitive Fields")
        if not sensitive:
            self._log("No PII/sensitive fields detected by the starter scan.")
            return
        for f in sensitive:
            self._log(f"- {f.name}: {f.pii_category or 'Sensitive'} | {f.sensitivity} | null {f.null_pct}% | unique {f.unique_pct}%")

    def _quick_generate_dq(self, _evt):
        if not self.profile:
            wx.MessageBox("Open/profile a data asset first.", "CatalogIQ")
            return
        self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
        self._log("\n[AGENT ACTION] Generate DQ Rules")
        self._log("Suggested implementation rules:")
        for f in self.profile.fields:
            if f.null_pct == 0:
                self._log(f"- {f.name}: NOT NULL check")
            if f.unique_pct >= 95:
                self._log(f"- {f.name}: uniqueness / candidate key check")
            if f.pii_flag == "Yes":
                self._log(f"- {f.name}: sensitive data classification and masking/access policy check")
        self._log("Use Export Package to generate quality_rules.sql for downstream implementation.")

    def _ask_agent(self, _evt):
        if not self.profile:
            wx.MessageBox("Connect/profile a dataset or open a workspace asset first.", "CatalogIQ")
            return
        try:
            question = self.agent_question.GetValue()
            answer = self._v4_answer(question) or answer_agent_question(self.profile, question)
            self.notebook.SetSelection(self.notebook.GetPageCount() - 1)
            self._log(f"\n[AGENT QUESTION] {question}\n{answer}\n")
        except Exception as e:
            self._show_error("Agent Question failed", e)

    def _refresh_recommendations(self):
        if not self.profile:
            self.recommendations.SetValue("No active data asset. Connect/profile a dataset or open a saved workspace asset.")
            return
        recs = agent_recommendations(self.profile)
        self.recommendations.SetValue("\n".join(f"• {r}" for r in recs))

    def _render_profile(self):
        if not self.profile:
            return
        self._df_to_grid(self.grid_scorecard, profile_scorecard_df(self.profile))
        self._df_to_grid(self.grid_catalog, profile_to_catalog_df(self.profile))
        self._df_to_grid(self.grid_glossary, profile_to_glossary_df(self.profile))
        self._df_to_grid(self.grid_dictionary, profile_to_dictionary_df(self.profile))
        findings = self.profile.governance_findings or ["No major governance findings detected by the starter scan."]
        recs = agent_recommendations(self.profile)
        self._df_to_grid(self.grid_findings, pd.DataFrame({"Type": ["Finding"] * len(findings) + ["Recommendation"] * len(recs), "Item": findings + recs}))
        self._df_to_grid(self.grid_lineage, self._lineage_df())
        self._df_to_grid(self.grid_policies, self._policy_review_df())

    def _update_kpis(self):
        if not self.profile:
            return
        sensitive = sum(1 for f in self.profile.fields if f.pii_flag == "Yes")
        self.kpi_score.value.SetLabel(f"{self.profile.quality_score}/100")  # type: ignore[attr-defined]
        self.kpi_risk.value.SetLabel(risk_level(self.profile))  # type: ignore[attr-defined]
        self.kpi_fields.value.SetLabel(str(self.profile.column_count))  # type: ignore[attr-defined]
        self.kpi_sensitive.value.SetLabel(str(sensitive))  # type: ignore[attr-defined]
        self.Layout()

    def _df_to_grid(self, grid: gridlib.Grid, df: pd.DataFrame):
        grid.ClearGrid()
        if grid.GetNumberRows():
            grid.DeleteRows(0, grid.GetNumberRows())
        if grid.GetNumberCols():
            grid.DeleteCols(0, grid.GetNumberCols())
        if len(df.columns):
            grid.AppendCols(len(df.columns))
        if len(df):
            grid.AppendRows(len(df))
        for c, col in enumerate(df.columns):
            grid.SetColLabelValue(c, str(col))
            grid.SetColSize(c, max(130, min(520, len(str(col)) * 12 + 42)))
        for r in range(len(df)):
            for c in range(len(df.columns)):
                v = df.iloc[r, c]
                grid.SetCellValue(r, c, "" if pd.isna(v) else str(v))
        grid.AutoSizeRows(False)



    def _lineage_df(self) -> pd.DataFrame:
        """Starter lineage view for the local data product lifecycle."""
        if not self.profile:
            return pd.DataFrame(columns=["Step", "Asset", "System", "Description"])
        package = str(self.last_package_dir) if self.last_package_dir else "Not exported yet"
        return pd.DataFrame([
            {"Step": "1", "Asset": Path(self.profile.source_path).name or self.profile.dataset_name, "System": "Source Dataset", "Description": "Original connected CSV/Excel dataset."},
            {"Step": "2", "Asset": self.profile.dataset_name, "System": "CatalogIQ Profiler", "Description": "Schema, quality, PII, sensitivity, and governance profiling."},
            {"Step": "3", "Asset": self.profile.dataset_name, "System": "CatalogIQ Workspace", "Description": "Published local asset JSON used for search, reopen, and agent context."},
            {"Step": "4", "Asset": package, "System": "Data Product Package", "Description": "Exported catalog, glossary, dictionary, DQ SQL, governance report, and publish payload."},
        ])

    def _policy_review_df(self) -> pd.DataFrame:
        """Generate a practical policy review queue from sensitive fields."""
        if not self.profile:
            return pd.DataFrame(columns=["Field", "Sensitivity", "PII Category", "Recommended Policy", "Action"])
        rows = []
        for f in self.profile.fields:
            if f.pii_flag == "Yes" or f.sensitivity in {"Confidential", "Restricted"}:
                policy = "Restricted Data Handling" if f.sensitivity == "Restricted" else "Confidential Data Handling"
                rows.append({
                    "Field": f.name,
                    "Sensitivity": f.sensitivity,
                    "PII Category": f.pii_category or "Sensitive",
                    "Recommended Policy": policy,
                    "Action": "Confirm business owner, apply policy tag, validate masking/access rules.",
                })
        if not rows:
            rows.append({"Field": "No sensitive fields detected", "Sensitivity": "Internal", "PII Category": "", "Recommended Policy": "Standard Data Handling", "Action": "Review with data owner."})
        return pd.DataFrame(rows)

    def _v4_answer(self, question: str) -> str | None:
        """Small v4 command layer before the existing rule-based agent."""
        if not self.profile:
            return None
        q = (question or "").lower()
        if "connector" in q or "connect" in q:
            return "Connector Hub v7 supports active Local File, AWS S3 object, and Snowflake table/query ingestion now. Postgres/SQL Server, Databricks, and API connectors remain next adapters."
        if "detail" in q or "data product" in q:
            return f"Data product {self.profile.dataset_name}: {self.profile.row_count:,} rows, {self.profile.column_count:,} fields, readiness {self.profile.quality_score}/100, risk {risk_level(self.profile)}. Use Data Product Detail for the business/technical review card."
        if "lineage" in q:
            return "Lineage view created from the current data product lifecycle: source dataset → CatalogIQ profiler → local workspace asset → exported data product package. Review the Lineage tab for the starter chain."
        if "policy" in q or "mask" in q or "access" in q:
            sensitive = [f for f in self.profile.fields if f.pii_flag == "Yes" or f.sensitivity in {"Confidential", "Restricted"}]
            if not sensitive:
                return "No sensitive fields were detected by the starter scan. Still confirm with the business owner before publishing."
            lines = ["Policy review queue:"]
            for f in sensitive:
                lines.append(f"- {f.name}: {f.pii_category or 'Sensitive'} / {f.sensitivity}. Apply policy tag and confirm masking/access requirements.")
            return "\n".join(lines)
        if "next" in q or "recommend" in q or "action" in q:
            return "Recommended next actions:\n" + "\n".join(f"- {r}" for r in agent_recommendations(self.profile))
        if "score" in q or "readiness" in q:
            return f"Readiness score is {self.profile.quality_score}/100. Risk is {risk_level(self.profile)}. Improve the score by resolving sensitive-field policy gaps, reviewing glossary terms, validating DQ rules, and assigning ownership."
        return None

    def _show_error(self, title: str, err: Exception):
        details = traceback.format_exc()
        self._log(f"[ERROR] {title}: {err}\n{details}")
        wx.MessageBox(f"{title}:\n\n{err}", "CatalogIQ", wx.OK | wx.ICON_ERROR)


def launch():
    app = wx.App(False)
    dlg = AgenticCatalogDialog(None)
    dlg.ShowModal()
    dlg.Destroy()
    app.MainLoop()


if __name__ == "__main__":
    launch()
