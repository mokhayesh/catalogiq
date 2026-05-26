# app/main_window.py
import wx
import wx.grid as gridlib
import pandas as pd
import os
import re
import json
import datetime
import threading
import requests
from typing import Dict, Tuple, Optional, List, IO

# Optional imports guarded to avoid crashes if dialogs not present
try:
    from .dialogs import DataBuddyDialog
except Exception:
    DataBuddyDialog = None

try:
    from .knowledge_dialog import KnowledgeDialog
except Exception:
    KnowledgeDialog = None

# Try to import external Connections dialog. If not available, we'll use our fallback below.
try:
    from .connections_dialog import ConnectionsDialog  # type: ignore
except Exception:
    ConnectionsDialog = None

from .settings import (
    SettingsWindow,
    settings_defaults as DEFAULTS,
)

APP_NAME = "CatalogIQ"
APPDATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", APP_NAME)
USER_SETTINGS = os.path.join(APPDATA_DIR, "settings.json")
KERNEL_PATHS = [
    os.path.join(APPDATA_DIR, "kernel.json"),
    os.path.join(os.getcwd(), "app", "kernel.json"),
    os.path.join(os.getcwd(), "kernel.json"),
]

# Default columns for the Current/Primary catalog view
CATALOG_COLUMNS = [
    "Field", "Friendly Name", "Description", "Data Type",
    "Nullable", "Example", "Analysis Date", "Policy", "Regex Pattern"
]

# Business Glossary / Data Dictionary schemas
GLOSSARY_COLUMNS = [
    "Term Name","Definition","Business Context","Synonyms/Aliases","Owner/Steward",
    "Approval Status","Related Terms","Data Sensitivity","Source System","Last Reviewed Date"
]
DICTIONARY_COLUMNS = [
    "Table Name","Column Name","Data Type","Length/Precision","Nullable",
    "Default Value","Primary Key","Foreign Key","Business Term Link",
    "Data Sensitivity","Source System","Last Modified Date","Owner/Steward"
]

# ------------------ basic helpers ------------------

def _ensure_dirs():
    try:
        os.makedirs(APPDATA_DIR, exist_ok=True)
    except Exception:
        pass

def _read_json(path: str) -> Optional[dict]:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None
    return None

def _write_json(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _load_kernel() -> dict:
    for p in KERNEL_PATHS:
        data = _read_json(p)
        if data is not None:
            return data
    return {
        "business_glossary": {"columns": GLOSSARY_COLUMNS, "rows": []},
        "data_dictionary": {"columns": DICTIONARY_COLUMNS, "rows": []},
        "primary_catalog": {"columns": CATALOG_COLUMNS, "rows": []}
    }

def _save_kernel(kernel: dict):
    _write_json(KERNEL_PATHS[0], kernel)

# ------------------ settings ------------------

def load_ai_settings() -> Tuple[Dict[str, str], Optional[str]]:
    search_paths = [
        USER_SETTINGS,
        os.path.join(os.getcwd(), "app", "settings.json"),
        os.path.join(os.getcwd(), "settings.json"),
        os.path.join(os.path.expanduser("~"), ".catalogiq", "settings.json"),
    ]
    cfg = dict(DEFAULTS)
    warn = None

    # env overrides
    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    env_url = os.environ.get("OPENAI_CHAT_URL", "").strip()
    env_model = os.environ.get("OPENAI_DEFAULT_MODEL", "").strip()
    if env_key:
        cfg["provider"] = "openai"
        cfg["openai_api_key"] = env_key
    if env_url:
        cfg["openai_url"] = env_url
    if env_model:
        cfg["openai_default_model"] = env_model

    for p in search_paths:
        data = _read_json(p)
        if data:
            cfg.update(data)
            break

    provider = cfg.get("provider", "openai")
    if provider == "openai":
        url = cfg.get("openai_url", "https://api.openai.com/v1/chat/completions")
        api_key = cfg.get("openai_api_key", "")
        model = cfg.get("openai_default_model", "gpt-4o-mini")
        org = cfg.get("openai_org", "")
    elif provider == "custom":
        url = cfg.get("custom_url", cfg.get("url", "http://127.0.0.1:8000/v1/chat/completions"))
        api_key = cfg.get("custom_api_key", cfg.get("api_key", ""))
        model = cfg.get("custom_model", cfg.get("default_model", "aldin-mini"))
        org = ""
    else:
        url = cfg.get("openai_url", "https://api.openai.com/v1/chat/completions")
        api_key = cfg.get("openai_api_key", "")
        model = cfg.get("openai_default_model", "gpt-4o-mini")
        org = cfg.get("openai_org", "")

    merged = {
        "provider": provider,
        "url": url,
        "api_key": api_key,
        "model": model,
        "fast_model": cfg.get("openai_fast_model", cfg.get("fast_model", model)),
        "org": org,
        "max_tokens": int(float(cfg.get("max_tokens", "800"))),
        "temperature": float(cfg.get("temperature", "0.4")),
        "top_p": float(cfg.get("top_p", "1.0")),
        "frequency_penalty": float(cfg.get("frequency_penalty", "0.0")),
        "presence_penalty": float(cfg.get("presence_penalty", "0.0")),
    }

    if not merged["api_key"]:
        warn = (
            "Missing API key. Add it in Settings or set OPENAI_API_KEY.\n\n"
            "Looked for settings.json in:\n"
            + "\n".join(search_paths)
        )
    return merged, warn

def preflight_check(parent) -> Optional[Dict[str, str]]:
    cfg, warn = load_ai_settings()
    if warn and not cfg.get("api_key"):
        wx.MessageBox(warn, "AI Assist", wx.OK | wx.ICON_INFORMATION, parent)
        return None

    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    if cfg.get("org"):
        headers["OpenAI-Organization"] = cfg["org"]
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": "Return {\"value\":\"ok\"}"}],
        "temperature": 0,
        "max_tokens": 8,
    }
    try:
        r = requests.post(cfg["url"], json=body, headers=headers, timeout=20)
        if r.status_code == 200:
            return cfg
        wx.MessageBox(
            f"AI preflight failed:\nStatus: {r.status_code}\nURL: {cfg['url']}\nModel: {cfg['model']}\n\n{r.text[:1000]}",
            "AI Assist", wx.OK | wx.ICON_INFORMATION, parent,
        )
        return None
    except Exception as e:
        wx.MessageBox(f"AI preflight exception:\n{e}", "AI Assist", wx.OK | wx.ICON_ERROR, parent)
        return None

# ------------------ robust JSON parsing (unchanged core) ------------------

_EXPECTED_KEYS = {
    "friendlyname": "Friendly Name",
    "friendly_name": "Friendly Name",
    "friendly name": "Friendly Name",
    "description": "Description",
    "datatype": "Data Type",
    "data type": "Data Type",
    "nullable": "Nullable",
    "example": "Example",
    "analysisdate": "Analysis Date",
    "analysis date": "Analysis Date",
    "date": "Analysis Date",
    "policy": "Policy",
    "regex": "Regex Pattern",
    "regexpattern": "Regex Pattern",
    "regex pattern": "Regex Pattern",
    "pattern": "Regex Pattern",
    "dataclassification": "Data Classification",
    "data_classification": "Data Classification",
    "data classification": "Data Classification",
    "classification": "Data Classification",
    "sensitivity": "Data Sensitivity",
    "data_sensitivity": "Data Sensitivity",
    "data sensitivity": "Data Sensitivity",
}
def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(k).lower())
def _strip_fences(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        if s.startswith("json"):
            s = s[4:]
        s = s.rstrip("`").strip()
    return s
def _find_balanced_json(s: str) -> Optional[str]:
    start = None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    return s[start:i+1]
    return None
def _decode_possible_object(text: str) -> Optional[dict]:
    if not text:
        return None
    t = _strip_fences(text)
    try:
        o = json.loads(t)
        if isinstance(o, dict):
            return o
    except Exception:
        pass
    cand = _find_balanced_json(t)
    if cand:
        try:
            o = json.loads(cand)
            if isinstance(o, dict):
                return o
        except Exception:
            pass
    if "{" in t and "}" in t:
        try:
            prefix = t.index("{"); suffix = t.rindex("}")
            clipped = t[prefix:suffix+1]
            o = json.loads(clipped)
            if isinstance(o, dict):
                return o
        except Exception:
            pass
    return None
def _map_keys_to_columns(obj: dict) -> dict:
    mapped = {}
    for k, v in obj.items():
        nk = _norm_key(k)
        if nk in _EXPECTED_KEYS:
            mapped[_EXPECTED_KEYS[nk]] = v
    return mapped
def extract_value_or_object(raw: str):
    if not raw:
        return ("none", "")
    txt = _strip_fences(raw)
    obj = _decode_possible_object(txt)
    if obj is not None:
        if "value" in obj and len(obj.keys()) == 1:
            return ("single", str(obj["value"]))
        mapped = _map_keys_to_columns(obj)
        if not mapped and "value" in obj:
            return ("single", str(obj["value"]))
        if mapped:
            return ("object", mapped)
    m = re.search(r'"value"\s*:\s*"(?P<v>(?:[^"\\]|\\.)*)"', txt, re.S)
    if m:
        val = m.group("v")
        try:
            val = bytes(val, "utf-8").decode("unicode_escape")
        except Exception:
            pass
        return ("single", val.strip())
    if "{" not in txt and "}" not in txt:
        return ("single", txt.strip())
    return ("none", "")
def cleanup_by_column(col: str, val: str) -> str:
    if val is None:
        return ""
    sval = str(val).strip()
    if not sval:
        return ""
    if col == "Friendly Name":
        return sval.title()
    if col == "Nullable":
        return "Yes" if sval.lower().startswith("y") else "No"
    if col == "Analysis Date":
        try:
            d = str(sval)[:10]
            datetime.date.fromisoformat(d)
            return d
        except Exception:
            return datetime.date.today().isoformat()
    if col == "Regex Pattern":
        if not any(ch in sval for ch in "^$.[]()+*?|\\"):
            return ".*"
    if col in ("Data Classification", "Data Sensitivity"):
        t = (sval or "").strip().lower()
        if not t:
            return ""
        if "pii" in t or "personally" in t:
            return "PII"
        if "public" in t or "open" in t:
            return "Public"
        if "internal" in t:
            return "Internal"
        if "restrict" in t or "sensitive" in t:
            return "Restricted"
        if "confid" in t or "secret" in t:
            return "Confidential"
        return t.split("/")[0].split(",")[0].strip().title()
    return sval
def looks_like_json(s: str) -> bool:
    if not s:
        return False
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        return True
    if s.startswith("```"):
        return True
    if '"Friendly Name"' in s or '"Description"' in s or '"Data Type"' in s:
        return True
    return False
def write_cell_safe(df: pd.DataFrame, row_idx: int, col: str, candidate: str):
    if candidate is None:
        return
    text = str(candidate)
    if looks_like_json(text):
        obj = _decode_possible_object(text)
        if isinstance(obj, dict):
            mapped = _map_keys_to_columns(obj)
            if col in mapped:
                df.at[row_idx, col] = cleanup_by_column(col, mapped[col]); return
            if "value" in obj:
                df.at[row_idx, col] = cleanup_by_column(col, str(obj["value"])); return
        return
    else:
        df.at[row_idx, col] = cleanup_by_column(col, text)
def final_clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cols = [c for c in cleaned.columns if c != "Field"]
    for r in range(len(cleaned)):
        for col in cols:
            if col == "Field":
                continue
            current = str(cleaned.at[r, col]) if col in cleaned.columns else ""
            if not current:
                continue
            if looks_like_json(current):
                obj = _decode_possible_object(current)
                if isinstance(obj, dict):
                    mapped = _map_keys_to_columns(obj)
                    if col in mapped:
                        cleaned.at[r, col] = cleanup_by_column(col, mapped[col])
                    elif "value" in obj:
                        cleaned.at[r, col] = cleanup_by_column(col, str(obj["value"]))
            else:
                cleaned.at[r, col] = cleanup_by_column(col, current)
    return cleaned

# ------------------ deterministic defaults for blanks ------------------

def _defaults_by_field(field: str) -> Dict[str, str]:
    f = (field or "").strip().lower()
    if f == "email":
        return {
            "Friendly Name": "Email",
            "Description": "The email address used for contact and notifications.",
            "Data Type": "VARCHAR(255)",
            "Example": "john.doe@example.com",
            "Regex Pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        }
    if f == "address":
        return {
            "Friendly Name": "Address",
            "Description": "A detailed description of the address for the record.",
            "Data Type": "VARCHAR(255)",
            "Example": "123 Main St, Anytown, USA",
            "Regex Pattern": r".*",
        }
    if f in ("phone number", "phonenumber", "phone"):
        return {
            "Friendly Name": "Phone Number",
            "Description": "Primary telephone number including optional country code.",
            "Data Type": "VARCHAR(20)",
            "Example": "+1-555-123-4567",
            "Regex Pattern": r"^\+?[0-9\-\s\(\)]+$",
        }
    if f == "first name":
        return {
            "Friendly Name": "First Name",
            "Description": "The given name of an individual.",
            "Data Type": "VARCHAR(50)",
            "Example": "John",
            "Regex Pattern": r"^[A-Za-z\-\s']+$",
        }
    if f == "last name":
        return {
            "Friendly Name": "Last Name",
            "Description": "The family name of an individual.",
            "Data Type": "VARCHAR(50)",
            "Example": "Smith",
            "Regex Pattern": r"^[A-Za-z\-\s']+$",
        }
    if f == "middle name":
        return {
            "Friendly Name": "Middle Name",
            "Description": "The middle name or initial of an individual.",
            "Data Type": "VARCHAR(50)",
            "Example": "Anne",
            "Regex Pattern": r"^[A-Za-z\-\s']+$",
        }
    if f == "loan amount":
        return {
            "Friendly Name": "Loan Amount",
            "Description": "The total amount of money borrowed in a loan.",
            "Data Type": "DECIMAL(10,2)",
            "Example": "15000.00",
            "Regex Pattern": r"^\d+(\.\d{1,2})?$",
        }
    return {
        "Friendly Name": field.title() if field else "",
        "Description": f"The {field.lower()} of the record." if field else "",
        "Data Type": "VARCHAR(255)",
        "Example": "",
        "Regex Pattern": ".*",
    }

def fill_defaults_for_blanks(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    cols = set(out.columns)
    for i, row in out.iterrows():
        field = str(row.get("Field", "")).strip()
        dft = _defaults_by_field(field)
        for col in ["Friendly Name", "Description", "Data Type", "Example", "Regex Pattern"]:
            if col in cols and str(row.get(col, "")).strip() == "":
                out.at[i, col] = cleanup_by_column(col, dft.get(col, ""))
        if "Nullable" in cols and str(row.get("Nullable", "")).strip() == "":
            out.at[i, "Nullable"] = "No"
        if "Analysis Date" in cols and str(row.get("Analysis Date", "")).strip() == "":
            out.at[i, "Analysis Date"] = datetime.date.today().isoformat()
        if "Policy" in cols and str(row.get("Policy", "")).strip() == "":
            out.at[i, "Policy"] = "Standard"
    return out

# ------------------ Steward actions from Agent ------------------
def apply_steward_actions(self, actions: list) -> int:
    try:
        df = self._grid_to_df()
        applied = 0
        for act in actions:
            try:
                ridx = int(act.get("row", -1))
                col = str(act.get("column","")).strip()
                val = act.get("value","")
                if ridx < 0 or ridx >= len(df) or not col or col not in df.columns:
                    continue
                df.at[ridx, col] = str(val)
                applied += 1
            except Exception:
                continue
        if applied:
            df = final_clean_dataframe(df)
            self._df_to_grid(df)
        return applied
    except Exception:
        return 0

# ------------------ AI prompt ------------------

def build_prompt(field: str, col: str, context_lines: Dict[str, str]) -> str:
    lines = "\n".join(f"- {k}: {v}" for k, v in context_lines.items() if str(v).strip())
    classification_hint = ""
    lc = (col or "").strip().lower()
    if lc in {"data classification","dataclassification","data_classification","classification"}:
        classification_hint = """
For this column, return a short label from:
Public, Internal, Restricted, Confidential, PII
""".strip()
    return f"""
You are an expert data steward.

Return EXACTLY one line of JSON and nothing else:
{{"value":"<answer>"}}

Rules:
- Friendly Name: human readable, title case
- Description: 10–20 words
- Data Type: realistic DB type
- Nullable: Yes/No
- Example: simple value
- Policy: short label
- Regex Pattern: valid regex
- Analysis Date: YYYY-MM-DD
- If the column is unknown, still return a sensible single value for that column.
{classification_hint}
Field: {field}
Column: {col}

Existing values:
{lines}
""".strip()

# ------------------ Configure Catalog Dialog ------------------

class ConfigureCatalogDialog(wx.Dialog):
    # original body retained
    def __init__(self, parent, current_title: str, current_df: Optional[pd.DataFrame] = None):
        super().__init__(parent, title="Configure Catalog", size=(600, 560))
        self._df = (current_df.copy() if current_df is not None else pd.DataFrame(columns=CATALOG_COLUMNS))
        cur_cols = list(self._df.columns) if not self._df.empty else list(CATALOG_COLUMNS)
        if "Field" not in cur_cols:
            cur_cols = ["Field"] + cur_cols
        else:
            cur_cols = ["Field"] + [c for c in cur_cols if c != "Field"]
        self._columns = cur_cols[:]
        self._rename_map_cols: Dict[str, str] = {}
        panel = wx.Panel(self); root = wx.BoxSizer(wx.VERTICAL)
        root.Add(wx.StaticText(panel, label="Catalog Title:"), 0, wx.ALL, 6)
        self.txt_title = wx.TextCtrl(panel, value=current_title or "Catalog Overview")
        root.Add(self.txt_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        grid = wx.FlexGridSizer(4, 2, 8, 8); grid.AddGrowableCol(1, 1)
        grid.Add(wx.StaticText(panel, label="Default Policy:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_policy = wx.Choice(panel, choices=["Standard", "Restricted", "Confidential"]); self.choice_policy.SetSelection(0)
        grid.Add(self.choice_policy, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Default Nullable:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.choice_nullable = wx.Choice(panel, choices=["No", "Yes"]); self.choice_nullable.SetSelection(0)
        grid.Add(self.choice_nullable, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Default Analysis Date (YYYY-MM-DD):"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_date = wx.TextCtrl(panel, value=datetime.date.today().isoformat()); grid.Add(self.txt_date, 1, wx.EXPAND)
        grid.Add(wx.StaticText(panel, label="Default Regex Pattern:"), 0, wx.ALIGN_CENTER_VERTICAL)
        self.txt_regex = wx.TextCtrl(panel, value=".*"); grid.Add(self.txt_regex, 1, wx.EXPAND)
        root.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        self.chk_backfill = wx.CheckBox(panel, label="Backfill blanks across the catalog with these defaults"); self.chk_backfill.SetValue(True)
        root.Add(self.chk_backfill, 0, wx.ALL, 8)
        box = wx.StaticBox(panel, label="Columns (the first column 'Field' is required)")
        bs = wx.StaticBoxSizer(box, wx.VERTICAL)
        hs = wx.BoxSizer(wx.HORIZONTAL)
        self.lst_cols = wx.ListBox(panel, style=wx.LB_SINGLE)
        self._reload_cols_listbox(); hs.Add(self.lst_cols, 1, wx.EXPAND | wx.ALL, 4)
        btns = wx.BoxSizer(wx.VERTICAL)
        self.btn_add = wx.Button(panel, label="Add Column…")
        self.btn_remove = wx.Button(panel, label="Remove")
        self.btn_rename = wx.Button(panel, label="Rename…")
        self.btn_up = wx.Button(panel, label="Move Up")
        self.btn_down = wx.Button(panel, label="Move Down")
        for b in (self.btn_add, self.btn_remove, self.btn_rename, self.btn_up, self.btn_down):
            btns.Add(b, 0, wx.EXPAND | wx.ALL, 2)
        hs.Add(btns, 0, wx.TOP, 4)
        bs.Add(hs, 1, wx.EXPAND | wx.ALL, 4); root.Add(bs, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        btn_sizer = wx.StdDialogButtonSizer(); btn_ok = wx.Button(panel, wx.ID_OK); btn_cancel = wx.Button(panel, wx.ID_CANCEL)
        btn_sizer.AddButton(btn_ok); btn_sizer.AddButton(btn_cancel); btn_sizer.Realize()
        root.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 8)
        self.btn_add.Bind(wx.EVT_BUTTON, self._on_add_col)
        self.btn_remove.Bind(wx.EVT_BUTTON, self._on_remove_col)
        self.btn_rename.Bind(wx.EVT_BUTTON, self._on_rename_col)
        self.btn_up.Bind(wx.EVT_BUTTON, self._on_up_col)
        self.btn_down.Bind(wx.EVT_BUTTON, self._on_down_col)
        panel.SetSizer(root); self.Layout()
    def _cols_without_field(self) -> List[str]:
        return [c for c in self._columns if c != "Field"]
    def _reload_cols_listbox(self):
        self.lst_cols.Clear()
        for c in self._cols_without_field():
            self.lst_cols.Append(c)
        if self.lst_cols.GetCount() > 0:
            self.lst_cols.SetSelection(0)
    def _ensure_unique_col(self, name: str) -> bool:
        name_low = name.strip().lower()
        for c in self._columns:
            if c.strip().lower() == name_low:
                return False
        return True
    def _on_add_col(self, _evt):
        dlg = wx.TextEntryDialog(self, "New column name:", "Add Column")
        if dlg.ShowModal() != wx.ID_OK: return
        name = dlg.GetValue().strip()
        if not name: return
        if name == "Field":
            wx.MessageBox("The 'Field' column already exists and is required.", "Columns"); return
        if not self._ensure_unique_col(name):
            wx.MessageBox("A column with this name already exists.", "Columns"); return
        self._columns.append(name); self._reload_cols_listbox(); self.lst_cols.SetSelection(self.lst_cols.GetCount() - 1)
    def _on_remove_col(self, _evt):
        idx = self.lst_cols.GetSelection()
        if idx == wx.NOT_FOUND: return
        name = self.lst_cols.GetString(idx)
        if name == "Field": return
        self._columns = ["Field"] + [c for c in self._cols_without_field() if c != name]
        self._reload_cols_listbox()
    def _on_rename_col(self, _evt):
        idx = self.lst_cols.GetSelection()
        if idx == wx.NOT_FOUND: return
        old = self.lst_cols.GetString(idx)
        dlg = wx.TextEntryDialog(self, f"Rename column '{old}' to:", "Rename Column", value=old)
        if dlg.ShowModal() != wx.ID_OK: return
        new = dlg.GetValue().strip()
        if not new or new == old: return
        if new == "Field":
            wx.MessageBox("The 'Field' column name is reserved.", "Columns"); return
        if not self._ensure_unique_col(new):
            wx.MessageBox("Another column with this name already exists.", "Columns"); return
        cols_wo = self._cols_without_field(); cols_wo[idx] = new
        self._columns = ["Field"] + cols_wo; self._reload_cols_listbox(); self.lst_cols.SetSelection(idx)
    def _on_up_col(self, _evt):
        idx = self.lst_cols.GetSelection()
        if idx in (-1, 0): return
        cols_wo = self._cols_without_field(); val = cols_wo[idx]
        cols_wo.pop(idx); cols_wo.insert(idx - 1, val)
        self._columns = ["Field"] + cols_wo; self._reload_cols_listbox(); self.lst_cols.SetSelection(idx - 1)
    def _on_down_col(self, _evt):
        idx = self.lst_cols.GetSelection()
        cols_wo = self._cols_without_field()
        if idx == wx.NOT_FOUND or idx >= len(cols_wo) - 1: return
        val = cols_wo[idx]; cols_wo.pop(idx); cols_wo.insert(idx + 1, val)
        self._columns = ["Field"] + cols_wo; self._reload_cols_listbox(); self.lst_cols.SetSelection(idx + 1)
    def get_config(self) -> dict:
        return {
            "title": self.txt_title.GetValue().strip(),
            "policy": self.choice_policy.GetStringSelection(),
            "nullable": self.choice_nullable.GetStringSelection(),
            "analysis_date": self.txt_date.GetValue().strip(),
            "regex": self.txt_regex.GetValue(),
            "backfill": self.chk_backfill.GetValue(),
            "ordered_columns": self._columns[:],
            "rename_map_columns": {},
        }

# ------------------ S3 helpers ------------------

def _is_s3(path: str) -> bool:
    return isinstance(path, str) and path.lower().startswith("s3://")

def _open_s3(path: str, mode: str) -> IO[bytes]:
    try:
        import s3fs  # pulls in fsspec
    except Exception:
        raise ModuleNotFoundError(
            "s3fs is not installed. Install with:\n\npip install s3fs\n"
            "(This also installs fsspec, which pandas uses for s3:// URLs.)"
        )
    fs = s3fs.S3FileSystem(anon=False)
    return fs.open(path, mode)

# ------------------ Fallback Connections Dialog ------------------

class FallbackConnectionsDialog(wx.Dialog):
    """Minimal built-in Connections dialog used when external module is missing."""
    def __init__(self, parent, callback):
        super().__init__(parent, title="Connections", size=(700, 420))
        self._callback = callback
        p = wx.Panel(self); root = wx.BoxSizer(wx.VERTICAL)

        self.nb = wx.Notebook(p)

        # --- S3/URI tab ---
        tab_file = wx.Panel(self.nb); s1 = wx.BoxSizer(wx.VERTICAL)
        self.file_target = wx.Choice(tab_file, choices=["Current Catalog","Business Glossary","Data Dictionary","Primary Catalog"])
        self.file_target.SetSelection(0)
        self.file_action = wx.Choice(tab_file, choices=["import","export"])
        self.file_action.SetSelection(0)
        self.txt_path = wx.TextCtrl(tab_file, value="s3://bucket/key.csv (or local path)")
        s1.Add(wx.StaticText(tab_file, label="Target:"), 0, wx.TOP|wx.LEFT, 6); s1.Add(self.file_target, 0, wx.EXPAND|wx.ALL, 6)
        s1.Add(wx.StaticText(tab_file, label="Action:"), 0, wx.LEFT, 6); s1.Add(self.file_action, 0, wx.EXPAND|wx.ALL, 6)
        s1.Add(wx.StaticText(tab_file, label="S3 URI or local path:"), 0, wx.LEFT, 6); s1.Add(self.txt_path, 0, wx.EXPAND|wx.ALL, 6)
        tab_file.SetSizer(s1)
        self.nb.AddPage(tab_file, "S3 / URI")

        # --- API tab ---
        tab_api = wx.Panel(self.nb); s2 = wx.BoxSizer(wx.VERTICAL)
        self.api_target = wx.Choice(tab_api, choices=["Current Catalog","Business Glossary","Data Dictionary","Primary Catalog"])
        self.api_target.SetSelection(0)
        self.api_action = wx.Choice(tab_api, choices=["import_api","export_api"])
        self.api_action.SetSelection(0)
        self.txt_api = wx.TextCtrl(tab_api, value="https://example.com/catalog")
        s2.Add(wx.StaticText(tab_api, label="Target:"), 0, wx.TOP|wx.LEFT, 6); s2.Add(self.api_target, 0, wx.EXPAND|wx.ALL, 6)
        s2.Add(wx.StaticText(tab_api, label="Action:"), 0, wx.LEFT, 6); s2.Add(self.api_action, 0, wx.EXPAND|wx.ALL, 6)
        s2.Add(wx.StaticText(tab_api, label="URL:"), 0, wx.LEFT, 6); s2.Add(self.txt_api, 0, wx.EXPAND|wx.ALL, 6)
        tab_api.SetSizer(s2)
        self.nb.AddPage(tab_api, "API")

        # --- SQL Server tab ---
        tab_sql = wx.Panel(self.nb); s3 = wx.BoxSizer(wx.VERTICAL)
        self.sql_target = wx.Choice(tab_sql, choices=["Current Catalog","Business Glossary","Data Dictionary","Primary Catalog"])
        self.sql_target.SetSelection(0)
        self.sql_action = wx.Choice(tab_sql, choices=["import_sql","export_sql"])
        self.sql_action.SetSelection(0)
        self.txt_conn = wx.TextCtrl(tab_sql, value="Driver={ODBC Driver 18 for SQL Server};Server=host;Database=db;UID=user;PWD=pass;Encrypt=yes;TrustServerCertificate=yes;")
        self.txt_table = wx.TextCtrl(tab_sql, value="CatalogPayloads")
        s3.Add(wx.StaticText(tab_sql, label="Target:"), 0, wx.TOP|wx.LEFT, 6); s3.Add(self.sql_target, 0, wx.EXPAND|wx.ALL, 6)
        s3.Add(wx.StaticText(tab_sql, label="Action:"), 0, wx.LEFT, 6); s3.Add(self.sql_action, 0, wx.EXPAND|wx.ALL, 6)
        s3.Add(wx.StaticText(tab_sql, label="Connection string:"), 0, wx.LEFT, 6); s3.Add(self.txt_conn, 0, wx.EXPAND|wx.ALL, 6)
        s3.Add(wx.StaticText(tab_sql, label="Table name:"), 0, wx.LEFT, 6); s3.Add(self.txt_table, 0, wx.EXPAND|wx.ALL, 6)
        tab_sql.SetSizer(s3)
        self.nb.AddPage(tab_sql, "SQL Server DB")

        # --- Fabric / Purview tab ---
        tab_fab = wx.Panel(self.nb); s4 = wx.BoxSizer(wx.VERTICAL)
        self.fab_target = wx.Choice(tab_fab, choices=["Current Catalog","Business Glossary","Data Dictionary","Primary Catalog"])
        self.fab_target.SetSelection(0)
        self.fab_action = wx.Choice(tab_fab, choices=["import_fabric","export_fabric"])
        self.fab_action.SetSelection(0)
        self.fab_url   = wx.TextCtrl(tab_fab, value="https://fabric.microsoft.com")  # base
        self.fab_api   = wx.TextCtrl(tab_fab, value="/api/purview/catalog")          # path returning/accepting {columns,rows}
        self.fab_token = wx.TextCtrl(tab_fab, value="Bearer-Token-Here")
        s4.Add(wx.StaticText(tab_fab, label="Target:"), 0, wx.TOP|wx.LEFT, 6); s4.Add(self.fab_target, 0, wx.EXPAND|wx.ALL, 6)
        s4.Add(wx.StaticText(tab_fab, label="Action:"), 0, wx.LEFT, 6); s4.Add(self.fab_action, 0, wx.EXPAND|wx.ALL, 6)
        s4.Add(wx.StaticText(tab_fab, label="Base URL:"), 0, wx.LEFT, 6); s4.Add(self.fab_url, 0, wx.EXPAND|wx.ALL, 6)
        s4.Add(wx.StaticText(tab_fab, label="API Path:"), 0, wx.LEFT, 6); s4.Add(self.fab_api, 0, wx.EXPAND|wx.ALL, 6)
        s4.Add(wx.StaticText(tab_fab, label="Access Token (Bearer):"), 0, wx.LEFT, 6); s4.Add(self.fab_token, 0, wx.EXPAND|wx.ALL, 6)
        tab_fab.SetSizer(s4)
        self.nb.AddPage(tab_fab, "Fabric / Purview")

        root.Add(self.nb, 1, wx.EXPAND|wx.ALL, 8)

        btns = wx.StdDialogButtonSizer()
        ok = wx.Button(p, wx.ID_OK); cancel = wx.Button(p, wx.ID_CANCEL)
        btns.AddButton(ok); btns.AddButton(cancel); btns.Realize()
        root.Add(btns, 0, wx.EXPAND | wx.ALL, 6)

        p.SetSizer(root)

        ok.Bind(wx.EVT_BUTTON, self._on_ok)

    def _on_ok(self, _evt):
        page = self.nb.GetSelection()
        if page == 0:
            section = self.file_target.GetStringSelection()
            action = self.file_action.GetStringSelection()
            path = self.txt_path.GetValue().strip()
            self._callback(section, action, path)
        elif page == 1:
            section = self.api_target.GetStringSelection()
            action = self.api_action.GetStringSelection()
            url = self.txt_api.GetValue().strip()
            self._callback(section, action, url)
        elif page == 2:
            section = self.sql_target.GetStringSelection()
            action = self.sql_action.GetStringSelection()
            info = (self.txt_conn.GetValue().strip(), self.txt_table.GetValue().strip())
            self._callback(section, action, info)
        else:
            section = self.fab_target.GetStringSelection()
            action = self.fab_action.GetStringSelection()
            info = {
                "base_url": self.fab_url.GetValue().strip(),
                "api_path": self.fab_api.GetValue().strip(),
                "token": self.fab_token.GetValue().strip(),
            }
            self._callback(section, action, info)
        self.EndModal(wx.ID_OK)

# ------------------ Main Window ------------------

class MainWindow(wx.Frame):
    def __init__(self):
        super().__init__(
            None, title=f"{APP_NAME} — Data Catalog", size=(1600, 900),
            style=wx.DEFAULT_FRAME_STYLE
        )
        self.SetBackgroundColour("#FFFFFF")
        self.catalog_name = ""
        _ensure_dirs()

        self.kernel = _load_kernel()
        self._current_df: pd.DataFrame = pd.DataFrame(columns=CATALOG_COLUMNS)
        self.current_view = "current"

        self._create_status_bar()
        self._build_ui()
        self._finalize_ui()
        self.Show()

    # ---------- UI build ----------

    def _build_ui(self):
        base = wx.BoxSizer(wx.HORIZONTAL)

        sidebar = wx.Panel(self)
        sidebar.SetBackgroundColour("#0F1624")
        sidebar.SetMinSize((300, -1))  # Wider to avoid truncation
        sb = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(sidebar, label="CatalogIQ")
        title.SetForegroundColour("#4CB3FF")
        title.SetFont(wx.Font(24, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        sb.Add(title, 0, wx.ALL, 20)

        def sb_btn(label: str):
            # Centered text (ensure no BU_LEFT; give generous min size)
            b = wx.Button(sidebar, label=label)
            try:
                # Strip any inherited left-align bit if present on some themes
                b.SetWindowStyleFlag(b.GetWindowStyleFlag() & ~wx.BU_LEFT)
            except Exception:
                pass
            b.SetMinSize((280, 46))
            b.SetForegroundColour("#000000")
            return b

        self.btn_upload       = sb_btn("📂 Upload CSV")
        self.btn_config       = sb_btn("⚙ Configure Catalog")
        self.btn_edit         = sb_btn("✏ Edit Mode")
        self.btn_save         = sb_btn("💾 Save Catalog")
        self.btn_ai           = sb_btn("🤖 AI Assist")
        self.btn_publish      = sb_btn("📣 Publish")
        self.btn_connections  = sb_btn("🔌 Connections")
        self.btn_knowledge    = sb_btn("📘 Knowledge")
        self.btn_iq           = sb_btn("💬 IQ Assistant")
        self.btn_settings     = sb_btn("⚙ Settings")

        for b in [self.btn_upload,self.btn_config,self.btn_edit,self.btn_save,
                  self.btn_ai,self.btn_publish,self.btn_connections,
                  self.btn_knowledge,self.btn_iq,self.btn_settings]:
            sb.Add(b, 0, wx.EXPAND | wx.ALL, 6)

        sidebar.SetSizer(sb)
        base.Add(sidebar, 0, wx.EXPAND)

        content = wx.Panel(self); content.SetBackgroundColour("#FFFFFF")
        cs = wx.BoxSizer(wx.VERTICAL)

        self.catalog_title = wx.StaticText(content, label="Catalog Overview")
        self.catalog_title.SetFont(wx.Font(20, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        top = wx.BoxSizer(wx.HORIZONTAL)
        top.AddStretchSpacer(); top.Add(self.catalog_title, 0, wx.ALIGN_CENTER | wx.RIGHT, 12)
        self.search = wx.SearchCtrl(content, style=wx.TE_PROCESS_ENTER, size=(420, -1))
        self.search.SetHint("Search glossary, dictionary, or catalogs…")
        top.Add(self.search, 0, wx.ALIGN_CENTER); top.AddStretchSpacer()
        cs.Add(top, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 8)

        self.search_list = wx.ListCtrl(content, style=wx.LC_REPORT | wx.BORDER_SUNKEN, size=(-1, 120))
        for i, h in enumerate(["Section", "Column", "Row", "Value"]):
            self.search_list.InsertColumn(i, h)
            self.search_list.SetColumnWidth(i, 200 if i in (0,1,3) else 70)
        cs.Add(self.search_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        grid_panel = wx.Panel(content); grid_panel.SetBackgroundColour("#FFFFFF")
        gs = wx.BoxSizer(wx.VERTICAL)
        self.grid = gridlib.Grid(grid_panel); self.grid.CreateGrid(0, 0)
        self.grid.SetGridLineColour("#CCCCCC"); self.grid.SetLabelBackgroundColour("#E6E6E6")
        gs.Add(self.grid, 1, wx.EXPAND); grid_panel.SetSizer(gs)
        cs.Add(grid_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        self.tabbar = wx.Notebook(content, style=wx.NB_BOTTOM)
        self._tab_current = wx.Panel(self.tabbar)
        self._tab_bg = wx.Panel(self.tabbar)
        self._tab_dd = wx.Panel(self.tabbar)
        self._tab_primary = wx.Panel(self.tabbar)

        self.tabbar.AddPage(self._tab_current, "Current Catalog")
        self.tabbar.AddPage(self._tab_bg, "Business Glossary")
        self.tabbar.AddPage(self._tab_dd, "Data Dictionary")
        self.tabbar.AddPage(self._tab_primary, "Primary Catalog")

        cs.Add(self.tabbar, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        footer = wx.Panel(content); footer.SetBackgroundColour("#1B1F2A")
        fs = wx.BoxSizer(wx.VERTICAL)
        st = wx.StaticText(footer, label="Catalog Summary")
        st.SetForegroundColour("#FFFFFF"); st.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        fs.Add(st, 0, wx.ALL, 8)
        self.summary_text = wx.StaticText(footer, label="", style=wx.ALIGN_LEFT)
        self.summary_text.SetForegroundColour("#FFFFFF")
        fs.Add(self.summary_text, 0, wx.LEFT | wx.BOTTOM, 10)
        footer.SetSizer(fs)
        cs.Add(footer, 0, wx.EXPAND | wx.ALL, 5)

        content.SetSizer(cs)
        base.Add(content, 1, wx.EXPAND)
        self.SetSizer(base)

        self._load_dataframe(self._current_df)
        self._refresh_publish_visibility()

        self.tabbar.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)
        self.search.Bind(wx.EVT_TEXT, self._on_search)
        self.search_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_jump_to_result)

    def _create_status_bar(self):
        self.status_bar = self.CreateStatusBar(2)
        self.status_bar.SetStatusWidths([-2, -1])
        self.status_bar.SetStatusText("Ready", 0)
        self.status_bar.SetStatusText("", 1)

    def _set_status(self, text): wx.CallAfter(self.status_bar.SetStatusText, text, 0)
    def _set_progress(self, text): wx.CallAfter(self.status_bar.SetStatusText, text, 1)

    # ---------- Tabs / Kernel helpers ----------

    def _df_to_kernel_section(self, key: str, df: pd.DataFrame, *, append=False):
        if append and key in self.kernel and self.kernel[key].get("rows"):
            existing_cols = self.kernel[key].get("columns") or list(df.columns)
            try:
                existing = pd.DataFrame(self.kernel[key]["rows"], columns=existing_cols)
            except Exception:
                existing = pd.DataFrame(columns=existing_cols)
            all_cols = list(dict.fromkeys(list(existing_cols) + list(df.columns)))
            for c in all_cols:
                if c not in existing.columns: existing[c] = ""
                if c not in df.columns: df[c] = ""
            combined = pd.concat([existing[all_cols], df[all_cols]], ignore_index=True)
            self.kernel[key] = {"columns": all_cols, "rows": combined.fillna("").astype(str).to_dict(orient="records")}
        else:
            self.kernel[key] = {"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")}
        _save_kernel(self.kernel)

    def _kernel_section_to_df(self, key: str, fallback_cols: List[str]) -> pd.DataFrame:
        sec = self.kernel.get(key) or {}
        cols = sec.get("columns") or fallback_cols
        rows = sec.get("rows") or []
        try:
            df = pd.DataFrame(rows, columns=cols)
        except Exception:
            df = pd.DataFrame(columns=fallback_cols)
        return df

    def _refresh_publish_visibility(self):
        is_current = (self.current_view == "current")
        self.btn_publish.Enable(is_current)
        self.btn_publish.Show(is_current)
        self.Layout()

    def _persist_current_view(self):
        df = self._grid_to_df()
        if self.current_view == "bg":
            self._df_to_kernel_section("business_glossary", df)
        elif self.current_view == "dd":
            self._df_to_kernel_section("data_dictionary", df)
        elif self.current_view == "primary":
            self._df_to_kernel_section("primary_catalog", df)
        elif self.current_view == "current":
            self._current_df = df

    def _on_tab_changed(self, evt):
        self._persist_current_view()
        idx = self.tabbar.GetSelection()
        page_label = self.tabbar.GetPageText(idx)

        if page_label == "Current Catalog":
            self.current_view = "current"
            if self._current_df is None or self._current_df.empty:
                self._current_df = pd.DataFrame(columns=CATALOG_COLUMNS)
            self._load_dataframe(self._current_df)
        elif page_label == "Business Glossary":
            self.current_view = "bg"
            df = self._kernel_section_to_df("business_glossary", GLOSSARY_COLUMNS)
            for c in GLOSSARY_COLUMNS:
                if c not in df.columns: df[c] = ""
            self._load_dataframe(df[GLOSSARY_COLUMNS])
        elif page_label == "Data Dictionary":
            self.current_view = "dd"
            df = self._kernel_section_to_df("data_dictionary", DICTIONARY_COLUMNS)
            for c in DICTIONARY_COLUMNS:
                if c not in df.columns: df[c] = ""
            self._load_dataframe(df[DICTIONARY_COLUMNS])
        else:
            self.current_view = "primary"
            sec = self.kernel.get("primary_catalog") or {}
            cols = sec.get("columns") or CATALOG_COLUMNS
            df = self._kernel_section_to_df("primary_catalog", cols)
            for c in cols:
                if c not in df.columns: df[c] = ""
            self._load_dataframe(df[cols])

        self._refresh_publish_visibility()
        if evt: evt.Skip()

    # ---------- Publish (append) ----------

    def _publish_current(self, _evt):
        cur_df = self._grid_to_df()
        self._current_df = cur_df.copy()
        self._df_to_kernel_section("primary_catalog", cur_df, append=True)

        bg_rows = []
        if "Field" in cur_df.columns:
            for _, r in cur_df.iterrows():
                term = str(r.get("Field","")).strip()
                if term:
                    bg_rows.append([term, "", "", "", "", "Proposed", "", "", "", datetime.date.today().isoformat()])
        bg_df = pd.DataFrame(bg_rows, columns=GLOSSARY_COLUMNS) if bg_rows else pd.DataFrame(columns=GLOSSARY_COLUMNS)
        self._df_to_kernel_section("business_glossary", bg_df, append=True)

        dd_rows = []
        if "Field" in cur_df.columns:
            for _, r in cur_df.iterrows():
                coln = str(r.get("Field","")).strip()
                if not coln: continue
                dtype = str(r.get("Data Type","")).strip()
                nullable = str(r.get("Nullable","")).strip() or "No"
                dd_rows.append(["", coln, dtype, "", nullable, "", "FALSE", "", "", "", "", datetime.date.today().isoformat(), ""])
        dd_df = pd.DataFrame(dd_rows, columns=DICTIONARY_COLUMNS) if dd_rows else pd.DataFrame(columns=DICTIONARY_COLUMNS)
        self._df_to_kernel_section("data_dictionary", dd_df, append=True)

        wx.MessageBox("Published: appended Current Catalog to Glossary, Dictionary, and Primary.", "Publish")
        self.tabbar.ChangeSelection(3)
        self._on_tab_changed(wx.CommandEvent())

    # ---------- AI Assist ----------

    def _ai_assist(self, _evt):
        cfg = preflight_check(self)
        if not cfg: return
        df = self._grid_to_df()
        if df.empty:
            wx.MessageBox("No catalog loaded.", "AI Assist"); return
        self._set_status("Running AI Assist…"); self._set_progress("0%")
        threading.Thread(target=self._ai_worker, args=(df, cfg), daemon=True).start()

    def _choose_field_for_row(self, row: pd.Series) -> str:
        if self.current_view == "bg":
            return str(row.get("Term Name", "")).strip()
        if self.current_view == "dd":
            coln = str(row.get("Column Name", "")).strip()
            return coln or str(row.get("Table Name", "")).strip()
        return str(row.get("Field", "")).strip()

    def _ai_worker(self, df: pd.DataFrame, cfg: Dict[str, str]):
        headers = {"Authorization": f"Bearer {cfg['api_key']}"}
        if cfg.get("org"): headers["OpenAI-Organization"] = cfg["org"]
        updated = df.copy(); total = len(df); ai_cols = [c for c in df.columns if c != "Field"]

        for i, row in df.iterrows():
            field = self._choose_field_for_row(row)
            context = {col: str(val) for col, val in row.items() if str(val).strip()}

            for col in ai_cols:
                existing = str(updated.at[i, col]) if col in updated.columns else ""
                if looks_like_json(existing):
                    obj = _decode_possible_object(existing)
                    if isinstance(obj, dict):
                        mapped = _map_keys_to_columns(obj)
                        if col in mapped: write_cell_safe(updated, i, col, mapped[col])
                        elif "value" in obj: write_cell_safe(updated, i, col, str(obj["value"]))

            for col in ai_cols:
                if str(updated.at[i, col]).strip(): continue
                prompt = build_prompt(field, col, context)
                body = {"model": cfg["model"], "messages":[{"role":"user","content":prompt}],
                        "temperature": cfg.get("temperature", 0.2), "max_tokens":160}
                try:
                    r = requests.post(cfg['url'], json=body, headers=headers, timeout=45, verify=True)
                    if r.status_code != 200: continue
                    raw = r.json()["choices"][0]["message"]["content"]
                except Exception:
                    continue
                kind, payload = extract_value_or_object(raw)
                if kind == "single": write_cell_safe(updated, i, col, payload)
                elif kind == "object" and isinstance(payload, dict):
                    if col in payload: write_cell_safe(updated, i, col, str(payload[col]))
                    else: write_cell_safe(updated, i, col, str(payload.get("value","")))
            pct = int(((i + 1) / max(total, 1)) * 100)
            self._set_progress(f"{pct}%")

        if self.current_view in ("current","primary"):
            updated = fill_defaults_for_blanks(updated)
        cleaned = final_clean_dataframe(updated)

        if self.current_view == "bg": self._df_to_kernel_section("business_glossary", cleaned)
        elif self.current_view == "dd": self._df_to_kernel_section("data_dictionary", cleaned)
        elif self.current_view == "primary": self._df_to_kernel_section("primary_catalog", cleaned)
        elif self.current_view == "current": self._current_df = cleaned.copy()

        wx.CallAfter(self._load_dataframe, cleaned); wx.CallAfter(self._update_summary, cleaned)
        self._set_status("AI Assist Complete"); self._set_progress("")

    # ---------- CSV / Grid ----------

    def _upload_csv(self, _evt):
        dlg = wx.FileDialog(self, "Select dataset", wildcard="CSV files (*.csv)|*.csv",
                            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK: return
        path = dlg.GetPath(); filename = os.path.basename(path); self.catalog_name = filename.replace(".csv", "")
        try:
            df_raw = pd.read_csv(path, sep=None, engine='python')
            if set(CATALOG_COLUMNS).issubset(df_raw.columns):
                df = df_raw[CATALOG_COLUMNS]
            else:
                fields = df_raw.columns.tolist()
                df = pd.DataFrame(columns=CATALOG_COLUMNS)
                for f in fields:
                    df.loc[len(df)] = [f, "", "", "", "No", "", datetime.date.today().isoformat(), "Standard", ".*"]
            self._current_df = df.copy()
            self._load_dataframe(self._current_df)
            self.current_view = "current"; self.tabbar.ChangeSelection(0); self._refresh_publish_visibility()
            wx.MessageBox(f"Loaded dataset:\n{filename}", "Success")
        except Exception as e:
            wx.MessageBox(f"Failed to load CSV:\n{e}", "Error")

    def _load_dataframe(self, df: pd.DataFrame):
        if self.grid.GetNumberRows() > 0: self.grid.DeleteRows(0, self.grid.GetNumberRows())
        if self.grid.GetNumberCols() > 0: self.grid.DeleteCols(0, self.grid.GetNumberCols())
        self.grid.AppendCols(len(df.columns)); self.grid.AppendRows(len(df))
        for i, col in enumerate(df.columns): self.grid.SetColLabelValue(i, col)
        for r in range(len(df)):
            for c in range(len(df.columns)):
                v = df.iloc[r, c]; self.grid.SetCellValue(r, c, "" if pd.isna(v) else str(v))
        for c in range(self.grid.GetNumberCols()):  # wider columns for readability
            self.grid.SetColSize(c, 170)
        self._update_summary(df)
        self.catalog_title.SetLabel(self.catalog_name or "Catalog Overview")

    def _df_to_grid(self, df: pd.DataFrame): self._load_dataframe(df)

    def _grid_to_df(self) -> pd.DataFrame:
        rows = self.grid.GetNumberRows(); cols = self.grid.GetNumberCols()
        headers = [self.grid.GetColLabelValue(i) for i in range(cols)]
        data = []
        for r in range(rows):
            row = []
            for c in range(cols): row.append(self.grid.GetCellValue(r, c))
            data.append(row)
        return pd.DataFrame(data, columns=headers)

    def _update_summary(self, df: pd.DataFrame):
        total_fields = len(df)
        missing_desc = df["Description"].eq("").sum() if "Description" in df.columns else 0
        missing_policy = df["Policy"].eq("").sum() if "Policy" in df.columns else 0
        missing_regex = df["Regex Pattern"].eq("").sum() if "Regex Pattern" in df.columns else 0
        summary = f"• Total Fields: {total_fields}\n• Missing Descriptions: {missing_desc}\n• Missing Policies: {missing_policy}\n• Missing Regex Patterns: {missing_regex}"
        self.summary_text.SetLabel(summary)

    def _save_catalog(self, _evt):
        df = self._grid_to_df()
        if self.current_view == "current":
            self._current_df = df.copy()
        dlg = wx.FileDialog(self, "Save catalog as CSV", wildcard="CSV files (*.csv)|*.csv",
                            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        if dlg.ShowModal() != wx.ID_OK: return
        try:
            df.to_csv(dlg.GetPath(), index=False); wx.MessageBox(f"Catalog saved:\n{dlg.GetPath()}", "Saved")
        except Exception as e:
            wx.MessageBox(f"Save failed:\n{e}", "Error")

    def _toggle_edit_mode(self, _evt):
        if self.grid.IsEditable():
            self.grid.EnableEditing(False); wx.MessageBox("Edit Mode OFF", "Edit Mode")
        else:
            self.grid.EnableEditing(True); wx.MessageBox("Edit Mode ON — You may now edit the catalog.", "Edit Mode")

    # ---------- settings / IQ / connections ----------

    def _open_settings(self, _evt):
        dlg = SettingsWindow(self); dlg.ShowModal()

    def _open_iq(self, _evt):
        try:
            from .iq_assistant_dialog import IQAssistantDialog
            IQAssistantDialog(self).ShowModal()
        except Exception as e:
            wx.MessageBox(f"IQ Assistant failed to open:\n{e}", "IQ Assistant")

    def _open_connections(self, _evt):
        DialogClass = ConnectionsDialog or FallbackConnectionsDialog
        def _callback(section_label: str, action: str, payload):
            key = {
                "Current Catalog": "__current__",
                "Business Glossary": "business_glossary",
                "Data Dictionary": "data_dictionary",
                "Primary Catalog": "primary_catalog",
            }[section_label]
            if action in ("import", "export"):
                self._io_file(key, action, payload)
            elif action in ("import_api", "export_api"):
                self._io_api(key, action, payload)
            elif action in ("import_sql", "export_sql"):
                self._io_sqlserver(key, action, payload)
            elif action in ("import_fabric", "export_fabric"):
                self._io_fabric(key, action, payload)
        DialogClass(self, _callback).ShowModal()

    def _io_file(self, key: str, action: str, path: str):
        if not path:
            wx.MessageBox("Please specify a file path.", "Connections"); return
        try:
            if action == "import":
                if _is_s3(path):
                    if path.lower().endswith(".csv"):
                        try:
                            with _open_s3(path, "rb") as f: df = pd.read_csv(f)
                        except ModuleNotFoundError as e:
                            wx.MessageBox(str(e), "Connections", wx.OK | wx.ICON_ERROR); return
                    else:
                        try:
                            with _open_s3(path, "rb") as f: data = json.load(f)
                        except ModuleNotFoundError as e:
                            wx.MessageBox(str(e), "Connections", wx.OK | wx.ICON_ERROR); return
                        if not data: raise ValueError("Invalid or empty JSON.")
                        cols = data.get("columns") or []; rows = data.get("rows") or []
                        df = pd.DataFrame(rows, columns=cols)
                else:
                    if path.lower().endswith(".csv"):
                        df = pd.read_csv(path)
                    else:
                        data = _read_json(path)
                        if not data: raise ValueError("Invalid or empty JSON.")
                        cols = data.get("columns") or []; rows = data.get("rows") or []
                        df = pd.DataFrame(rows, columns=cols)
                if key == "__current__":
                    self._current_df = df.copy(); self._load_dataframe(self._current_df)
                    self.current_view = "current"; self.tabbar.ChangeSelection(0); self._refresh_publish_visibility()
                else:
                    self._df_to_kernel_section(key, df, append=True)
                    wx.MessageBox("Imported (appended) into selected section.", "Connections")
            else:  # export
                if key == "__current__":
                    df = self._current_df.copy()
                else:
                    section = self.kernel.get(key) or {}
                    df = pd.DataFrame(section.get("rows") or [], columns=section.get("columns") or [])
                if _is_s3(path):
                    try:
                        if path.lower().endswith(".csv"):
                            with _open_s3(path, "wb") as f: df.to_csv(f, index=False)
                        else:
                            payload = {"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")}
                            with _open_s3(path, "wb") as f: f.write(json.dumps(payload, indent=2).encode("utf-8"))
                    except ModuleNotFoundError as e:
                        wx.MessageBox(str(e), "Connections", wx.OK | wx.ICON_ERROR); return
                else:
                    if path.lower().endswith(".csv"):
                        df.to_csv(path, index=False)
                    else:
                        payload = {"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")}
                        _write_json(path, payload)
                wx.MessageBox("Export complete.", "Connections")
        except Exception as e:
            wx.MessageBox(f"{action.title()} failed: {e}", "Connections", wx.OK | wx.ICON_ERROR)

    def _io_api(self, key: str, action: str, url: str):
        if not url:
            wx.MessageBox("Please provide an API URL.", "Connections"); return
        try:
            if action == "import_api":
                r = requests.get(url, timeout=30); r.raise_for_status()
                data = r.json(); cols = data.get("columns") or []; rows = data.get("rows") or []
                df = pd.DataFrame(rows, columns=cols)
                if key == "__current__": self._current_df = df.copy(); self._load_dataframe(self._current_df)
                else: self._df_to_kernel_section(key, df, append=True)
                wx.MessageBox("Imported from API.", "Connections")
            else:
                if key == "__current__": df = self._current_df.copy()
                else:
                    sec = self.kernel.get(key) or {}
                    df = pd.DataFrame(sec.get("rows") or [], columns=sec.get("columns") or [])
                payload = {"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")}
                r = requests.post(url, json=payload, timeout=30); r.raise_for_status()
                wx.MessageBox("Exported to API.", "Connections")
        except Exception as e:
            wx.MessageBox(f"API {action.split('_')[-1]} failed: {e}", "Connections", wx.OK | wx.ICON_ERROR)

    def _io_sqlserver(self, key: str, action: str, info):
        conn_str, table = info
        try:
            import pyodbc
        except Exception:
            wx.MessageBox("pyodbc not installed. Install it to use SQL Server connections.", "Connections"); return
        if not conn_str or not table:
            wx.MessageBox("Provide a connection string and table name.", "Connections"); return
        try:
            cn = pyodbc.connect(conn_str, timeout=10); cur = cn.cursor()
            if action == "import_sql":
                cur.execute(f"SELECT TOP 1 Payload FROM {table} ORDER BY Id DESC"); row = cur.fetchone()
                if not row: raise ValueError("No rows in table.")
                data = json.loads(row[0])
                df = pd.DataFrame(data.get("rows") or [], columns=data.get("columns") or [])
                if key == "__current__": self._current_df = df.copy(); self._load_dataframe(self._current_df)
                else: self._df_to_kernel_section(key, df, append=True)
                wx.MessageBox("Imported from SQL Server.", "Connections")
            else:
                if key == "__current__": df = self._current_df.copy()
                else:
                    sec = self.kernel.get(key) or {}
                    df = pd.DataFrame(sec.get("rows") or [], columns=sec.get("columns") or [])
                payload = json.dumps({"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")})
                cur.execute(f"INSERT INTO {table} (Payload, CreatedAt) VALUES (?, GETDATE())", payload)
                cn.commit(); wx.MessageBox("Exported to SQL Server.", "Connections")
            cur.close(); cn.close()
        except Exception as e:
            wx.MessageBox(f"SQL operation failed: {e}", "Connections", wx.OK | wx.ICON_ERROR)

    def _io_fabric(self, key: str, action: str, info: Dict[str, str]):
        """Simple Fabric/Purview REST import/export using bearer token."""
        base = (info.get("base_url") or "").rstrip("/")
        path = "/" + (info.get("api_path") or "").lstrip("/")
        token = info.get("token") or ""
        if not base or not path or not token:
            wx.MessageBox("Provide Base URL, API Path, and Access Token.", "Connections"); return
        url = f"{base}{path}"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            if action == "import_fabric":
                r = requests.get(url, headers=headers, timeout=45, verify=True); r.raise_for_status()
                data = r.json()
                cols = data.get("columns") or []; rows = data.get("rows") or []
                df = pd.DataFrame(rows, columns=cols)
                if key == "__current__": self._current_df = df.copy(); self._load_dataframe(self._current_df)
                else: self._df_to_kernel_section(key, df, append=True)
                wx.MessageBox("Imported from Fabric / Purview.", "Connections")
            else:
                if key == "__current__": df = self._current_df.copy()
                else:
                    sec = self.kernel.get(key) or {}
                    df = pd.DataFrame(sec.get("rows") or [], columns=sec.get("columns") or [])
                payload = {"columns": list(df.columns), "rows": df.fillna("").astype(str).to_dict(orient="records")}
                r = requests.post(url, headers=headers, json=payload, timeout=45, verify=True); r.raise_for_status()
                wx.MessageBox("Exported to Fabric / Purview.", "Connections")
        except Exception as e:
            wx.MessageBox(f"Fabric/Purview operation failed: {e}", "Connections", wx.OK | wx.ICON_ERROR)

    # ---------- Search ----------

    def _on_search(self, evt):
        q = self.search.GetValue().strip().lower()
        self.search_list.DeleteAllItems()
        if not q: return
        def add_hits(section_name: str, df: pd.DataFrame):
            if df is None or df.empty: return
            for idx, row in df.iterrows():
                for col, val in row.items():
                    sv = str(val)
                    if q in sv.lower():
                        i = self.search_list.InsertItem(self.search_list.GetItemCount(), section_name)
                        self.search_list.SetItem(i, 1, col); self.search_list.SetItem(i, 2, str(idx + 1))
                        self.search_list.SetItem(i, 3, sv[:140])
        add_hits("Current Catalog", self._current_df)
        for name, key in [("Business Glossary","business_glossary"),("Data Dictionary","data_dictionary"),("Primary Catalog","primary_catalog")]:
            sec = self.kernel.get(key) or {}
            df = pd.DataFrame(sec.get("rows") or [], columns=sec.get("columns") or [])
            add_hits(name, df)

    def _on_jump_to_result(self, evt):
        i = evt.GetIndex(); section = self.search_list.GetItemText(i, 0)
        col = self.search_list.GetItemText(i, 1); row_num = int(self.search_list.GetItemText(i, 2)) - 1
        page_idx = {"Current Catalog":0, "Business Glossary":1, "Data Dictionary":2, "Primary Catalog":3}[section]
        self.tabbar.ChangeSelection(page_idx); self._on_tab_changed(wx.CommandEvent())
        try:
            col_idx = [self.grid.GetColLabelValue(c) for c in range(self.grid.GetNumberCols())].index(col)
            self.grid.SetGridCursor(max(0,row_num), col_idx); self.grid.MakeCellVisible(max(0,row_num), col_idx)
        except Exception:
            pass

    # ---------- Configure Catalog ----------

    def _open_config(self, _evt):
        current = self.catalog_title.GetLabel() or "Catalog Overview"
        df_before = self._grid_to_df()
        dlg = ConfigureCatalogDialog(self, current, df_before)
        if dlg.ShowModal() != wx.ID_OK: return
        cfg = dlg.get_config()

        self.catalog_title.SetLabel(cfg["title"] or "Catalog Overview")
        self.catalog_name = cfg["title"] or self.catalog_name

        ordered_columns: List[str] = cfg.get("ordered_columns", [])
        df = df_before.copy()

        if "Field" not in df.columns: df.insert(0, "Field", "")
        if ordered_columns and ordered_columns[0] != "Field":
            ordered_columns = ["Field"] + [c for c in ordered_columns if c != "Field"]
        for col in ordered_columns:
            if col not in df.columns: df[col] = ""
        keep_cols = [c for c in ordered_columns if c in df.columns]
        df = df[keep_cols]

        if cfg.get("backfill"):
            try:
                _ = datetime.date.fromisoformat((cfg["analysis_date"] or "")[:10]); date_ok = True
            except Exception:
                date_ok = False
            default_date = (cfg["analysis_date"][:10] if date_ok else datetime.date.today().isoformat())
            if "Policy" in df.columns:
                df.loc[df["Policy"].astype(str).str.strip() == "", "Policy"] = cfg["policy"]
            if "Nullable" in df.columns:
                df.loc[df["Nullable"].astype(str).str.strip() == "", "Nullable"] = cfg["nullable"]
            if "Analysis Date" in df.columns:
                df.loc[df["Analysis Date"].astype(str).str.strip() == "", "Analysis Date"] = default_date
            if "Regex Pattern" in df.columns:
                df.loc[df["Regex Pattern"].astype(str).str.strip() == "", "Regex Pattern"] = cfg["regex"]
            df = fill_defaults_for_blanks(df)

        if self.current_view == "current":
            self._current_df = df.copy()
        self._load_dataframe(df); self._update_summary(df)
        wx.MessageBox("Catalog configuration applied to Current Catalog.", "Config")

    # ---------- bindings / finalize ----------

    def _bind_events(self):
        self.btn_upload.Bind(wx.EVT_BUTTON, self._upload_csv)
        self.btn_save.Bind(wx.EVT_BUTTON, self._save_catalog)
        self.btn_edit.Bind(wx.EVT_BUTTON, self._toggle_edit_mode)
        self.btn_config.Bind(wx.EVT_BUTTON, self._open_config)
        self.btn_ai.Bind(wx.EVT_BUTTON, self._ai_assist)
        self.btn_publish.Bind(wx.EVT_BUTTON, self._publish_current)
        self.btn_connections.Bind(wx.EVT_BUTTON, self._open_connections)
        self.btn_knowledge.Bind(wx.EVT_BUTTON, lambda e:
            KnowledgeDialog(self).ShowModal() if KnowledgeDialog else wx.MessageBox(
                "Knowledge module coming soon.", "Knowledge"))
        self.btn_iq.Bind(wx.EVT_BUTTON, self._open_iq)
        self.btn_settings.Bind(wx.EVT_BUTTON, self._open_settings)

    def _finalize_ui(self):
        self._bind_events()
        self.Layout(); self.Refresh(); self.Update()
        self._set_status("Ready")


class CatalogIQ(wx.App):
    def OnInit(self):
        frame = MainWindow(); frame.Show(); return True


if __name__ == "__main__":
    app = CatalogIQ(False); app.MainLoop()
