import wx
import wx.richtext as rt
import json
import datetime
import threading
import requests
from typing import List, Dict, Any, Optional

# We import helpers lazily inside methods to avoid circular imports with main_window.py
# from .main_window import load_ai_settings, build_prompt, extract_value_or_object, write_cell_safe, final_clean_dataframe

AGENT_SYSTEM_PROMPT = """
You are CatalogIQ's Data Stewardship Agent.

Your job has TWO modes:

1) Q&A mode: If the user is just asking a question, answer concisely.

2) ACTION mode: If the user wants changes performed (they will say "task:", "do:", or "perform", or a button-driven task),
   RETURN EXACTLY one JSON object with this shape and NO other text:

{
  "actions": [
    {"row": <int zero-based>, "column": "<exact grid column name>", "value": "<string>"},
    ...
  ],
  "message": "<short human readable summary of what was changed>"
}

Rules:
- Use zero-based row indices as shown (0 is first row).
- Only set columns that actually exist in the current grid schema.
- Never remove rows.
- If you need to assign Data Sensitivity or Data Classification, use one of:
  Public, Internal, Restricted, Confidential, PII.
- If you are unsure of a column's exact name, infer from context but keep it exactly as shown in the schema.
- If you cannot find valid actions, return an empty actions list with a message that explains why.
"""

DEFAULT_TASKS = [
    ("Assign Sensitivity (PII heuristic)", "Assign PII/Internal/Confidential based on field names (email, first name, etc.)."),
    ("Fill Missing Policies (Standard)", "Set empty Policy cells to 'Standard'."),
    ("Set Nullable Defaults", "Set empty Nullable cells to 'No'."),
    ("Normalize Dates", "Ensure Analysis Date is ISO YYYY-MM-DD for all rows."),
]

class IQAssistantDialog(wx.Dialog):
    """
    Agentic Steward dialog with Chat and Common Tasks.
    When 'Perform changes' is enabled, the agent's JSON 'actions' will be applied directly to the parent grid.
    """
    def __init__(self, parent):
        super().__init__(parent, title="IQ Assistant — Data Steward", size=(900, 720))
        self.parent = parent
        self.cfg = None  # AI settings loaded on open
        self._build_ui()
        self._bind_events()
        self._preflight()

    # ---------- UI ----------

    def _build_ui(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        # Tabs: Chat | Tasks
        self.nb = wx.Notebook(panel)
        self.pg_chat = wx.Panel(self.nb)
        self.pg_tasks = wx.Panel(self.nb)
        self.nb.AddPage(self.pg_chat, "Chat")
        self.nb.AddPage(self.pg_tasks, "Common Tasks")
        root.Add(self.nb, 1, wx.EXPAND | wx.ALL, 6)

        # Chat page
        cs = wx.BoxSizer(wx.VERTICAL)

        self.history = rt.RichTextCtrl(self.pg_chat, style=wx.TE_READONLY | wx.VSCROLL | wx.HSCROLL | wx.BORDER_SIMPLE)
        cs.Add(self.history, 1, wx.EXPAND | wx.ALL, 6)

        in_row = wx.BoxSizer(wx.HORIZONTAL)
        self.txt_input = wx.TextCtrl(self.pg_chat, style=wx.TE_PROCESS_ENTER)
        self.btn_send = wx.Button(self.pg_chat, label="Send")
        in_row.Add(self.txt_input, 1, wx.EXPAND | wx.RIGHT, 6)
        in_row.Add(self.btn_send, 0)
        cs.Add(in_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        options = wx.BoxSizer(wx.HORIZONTAL)
        self.chk_perform = wx.CheckBox(self.pg_chat, label="Perform changes (apply actions JSON to catalog)")
        self.chk_perform.SetValue(True)
        options.Add(self.chk_perform, 0, wx.RIGHT, 10)
        self.btn_use_selection = wx.Button(self.pg_chat, label="Use Selected Rows Context")
        options.Add(self.btn_use_selection, 0)
        cs.Add(options, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.pg_chat.SetSizer(cs)

        # Tasks page
        ts = wx.BoxSizer(wx.VERTICAL)
        ts.Add(wx.StaticText(self.pg_tasks, label="One-click Steward Tasks"), 0, wx.ALL, 8)

        self.lst_tasks = wx.ListCtrl(self.pg_tasks, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.lst_tasks.InsertColumn(0, "Task")
        self.lst_tasks.InsertColumn(1, "Description")
        for i, (name, desc) in enumerate(DEFAULT_TASKS):
            idx = self.lst_tasks.InsertItem(i, name)
            self.lst_tasks.SetItem(idx, 1, desc)
        self.lst_tasks.SetColumnWidth(0, 260)
        self.lst_tasks.SetColumnWidth(1, 560)
        ts.Add(self.lst_tasks, 1, wx.EXPAND | wx.ALL, 6)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_run_task = wx.Button(self.pg_tasks, label="Run Selected Task")
        self.btn_close = wx.Button(self.pg_tasks, label="Close")
        btn_row.Add(self.btn_run_task, 0, wx.RIGHT, 8)
        btn_row.AddStretchSpacer()
        btn_row.Add(self.btn_close, 0)
        ts.Add(btn_row, 0, wx.EXPAND | wx.ALL, 6)

        self.pg_tasks.SetSizer(ts)

        panel.SetSizer(root)
        self.Layout()

    def _bind_events(self):
        self.btn_send.Bind(wx.EVT_BUTTON, self._on_send)
        self.txt_input.Bind(wx.EVT_TEXT_ENTER, self._on_send)
        self.btn_use_selection.Bind(wx.EVT_BUTTON, self._insert_selection_context)
        self.btn_run_task.Bind(wx.EVT_BUTTON, self._on_run_task)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    # ---------- Preflight ----------

    def _preflight(self):
        try:
            # Lazy import to avoid circulars at module import time
            from .main_window import load_ai_settings
            cfg, warn = load_ai_settings()
            if warn and not cfg.get("api_key"):
                self._append("system", "⚠ AI key not configured. Open Settings to configure.")
            else:
                self.cfg = cfg
                self._append("system", f"✅ AI ready (model: {cfg.get('model')})")
        except Exception as e:
            self._append("system", f"⚠ AI settings load error: {e}")

    # ---------- Helpers ----------

    def _append(self, role: str, text: str):
        self.history.BeginSuppressUndo()
        try:
            if role == "user":
                self.history.BeginBold()
                self.history.WriteText("You: ")
                self.history.EndBold()
            elif role == "agent":
                self.history.BeginBold()
                self.history.WriteText("Steward: ")
                self.history.EndBold()
            else:
                self.history.BeginBold()
                self.history.WriteText("• ")
                self.history.EndBold()
            self.history.WriteText(text + "\n")
        finally:
            self.history.EndSuppressUndo()
            self.history.ShowPosition(self.history.GetLastPosition())

    def _grid_snapshot(self) -> Dict[str, Any]:
        """Grab a lightweight snapshot of current grid state."""
        try:
            df = self.parent._grid_to_df()
            cols = list(df.columns)
            rows = df.fillna("").astype(str).to_dict(orient="records")
            return {"columns": cols, "rows": rows}
        except Exception:
            return {"columns": [], "rows": []}

    def _actions_apply(self, actions: List[Dict[str, Any]]) -> int:
        """Apply actions (row/column/value) to parent grid safely."""
        applied = 0
        try:
            # Preferred: a bound method on parent (if present)
            if hasattr(self.parent, "apply_steward_actions"):
                applied = self.parent.apply_steward_actions(actions)  # type: ignore[attr-defined]
                return applied
        except Exception:
            pass

        # Fallback: import helper function from main_window and pass parent explicitly
        try:
            from .main_window import apply_steward_actions as _apply
            applied = _apply(self.parent, actions)
            return applied
        except Exception:
            return 0

    def _insert_selection_context(self, _evt):
        """Insert selected rows as JSON context into the input box."""
        try:
            grid = self.parent.grid
            rows = sorted(grid.GetSelectedRows())
            if not rows:
                self._append("system", "No selected rows; using entire grid first 5 rows instead.")
                df = self.parent._grid_to_df()
                snippet = df.head(5).fillna("").astype(str).to_dict(orient="records")
            else:
                headers = [grid.GetColLabelValue(i) for i in range(grid.GetNumberCols())]
                records = []
                for r in rows:
                    rec = {}
                    for c in range(grid.GetNumberCols()):
                        rec[headers[c]] = grid.GetCellValue(r, c)
                    records.append(rec)
                snippet = records
            old = self.txt_input.GetValue().strip()
            ctx = json.dumps({"selection": snippet}, ensure_ascii=False)
            self.txt_input.SetValue((old + "\n" if old else "") + ctx)
            self.txt_input.SetInsertionPointEnd()
        except Exception as e:
            self._append("system", f"Could not capture selection: {e}")

    # ---------- Events ----------

    def _on_send(self, _evt):
        msg = self.txt_input.GetValue().strip()
        if not msg:
            return
        self._append("user", msg)
        self.txt_input.SetValue("")

        # If message indicates action, enforce JSON action mode
        wants_action = self.chk_perform.GetValue() and any(
            prefix in msg.lower() for prefix in ("task:", "perform", "do:", "action:", "apply:")
        )

        threading.Thread(target=self._chat_worker, args=(msg, wants_action), daemon=True).start()

    def _on_run_task(self, _evt):
        idx = self.lst_tasks.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a task first.", "IQ Assistant")
            return
        name = self.lst_tasks.GetItemText(idx)
        self._append("user", f"task: {name}")
        threading.Thread(target=self._task_worker, args=(name,), daemon=True).start()

    # ---------- Workers ----------

    def _task_worker(self, task_name: str):
        """
        Build deterministic actions for a few common tasks without calling the model,
        so the steward can always act instantly.
        """
        try:
            df = self.parent._grid_to_df()
            cols = list(df.columns)
            actions: List[Dict[str, Any]] = []

            if task_name.startswith("Assign Sensitivity"):
                # Heuristic: mark PII-like fields
                sens_col = None
                for cand in ("Data Sensitivity", "Sensitivity", "Data Classification", "Policy"):
                    if cand in cols:
                        sens_col = cand
                        break
                if sens_col:
                    for i, row in df.iterrows():
                        f = str(row.get("Field", "") or row.get("Column Name", "")).lower()
                        if any(k in f for k in ("email", "first name", "last name", "phone", "ssn", "address")):
                            actions.append({"row": i, "column": sens_col, "value": "PII"})
                else:
                    self._append("agent", "No sensitivity or classification column found for this tab.")
            elif task_name.startswith("Fill Missing Policies"):
                if "Policy" in cols:
                    for i, row in df.iterrows():
                        if not str(row.get("Policy", "")).strip():
                            actions.append({"row": i, "column": "Policy", "value": "Standard"})
                else:
                    self._append("agent", "No 'Policy' column found in this tab.")
            elif task_name.startswith("Set Nullable Defaults"):
                if "Nullable" in cols:
                    for i, row in df.iterrows():
                        if not str(row.get("Nullable", "")).strip():
                            actions.append({"row": i, "column": "Nullable", "value": "No"})
                else:
                    self._append("agent", "No 'Nullable' column found in this tab.")
            elif task_name.startswith("Normalize Dates"):
                target_cols = [c for c in cols if "date" in c.lower()]
                if target_cols:
                    today = datetime.date.today().isoformat()
                    for i, row in df.iterrows():
                        for c in target_cols:
                            v = str(row.get(c, "")).strip()
                            if not v:
                                actions.append({"row": i, "column": c, "value": today})
                            else:
                                try:
                                    d = str(v)[:10]
                                    datetime.date.fromisoformat(d)
                                except Exception:
                                    actions.append({"row": i, "column": c, "value": today})
                else:
                    self._append("agent", "No date-like columns found in this tab.")
            else:
                self._append("agent", f"Task '{task_name}' not recognized.")
                return

            count = self._actions_apply(actions) if actions else 0
            if count:
                self._append("agent", f"Applied {count} change(s) to the catalog.")
            else:
                self._append("agent", "No changes were necessary or applicable.")
        except Exception as e:
            self._append("agent", f"Task failed: {e}")

    def _chat_worker(self, user_msg: str, wants_action: bool):
        """
        Chat with the agent. If wants_action or the agent returns an actions JSON,
        apply changes directly to the catalog.
        """
        try:
            if not self.cfg:
                # try one more time if settings were available after opening dialog
                from .main_window import load_ai_settings
                cfg, warn = load_ai_settings()
                if warn and not cfg.get("api_key"):
                    self._append("agent", "AI not configured. Open Settings to add API key.")
                    return
                self.cfg = cfg

            cfg = self.cfg
            headers = {"Authorization": f"Bearer {cfg['api_key']}"}
            if cfg.get("org"):
                headers["OpenAI-Organization"] = cfg["org"]

            snapshot = self._grid_snapshot()
            payload = {
                "model": cfg.get("model", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Current tab schema: {snapshot['columns']}\n"
                            f"First 8 rows: {json.dumps(snapshot['rows'][:8], ensure_ascii=False)}\n\n"
                            f"User: {user_msg}\n"
                            + ("Return ONLY the actions JSON object, no prose." if wants_action else
                               "If the user is asking for action, return the JSON actions; else answer briefly.")
                        )
                    }
                ],
                "temperature": cfg.get("temperature", 0.2),
                "max_tokens": 600,
            }

            r = requests.post(cfg["url"], json=payload, headers=headers, timeout=60, verify=True)
            if r.status_code != 200:
                self._append("agent", f"API error {r.status_code}: {r.text[:300]}")
                return

            content = r.json()["choices"][0]["message"]["content"]

            # Try to parse a JSON object for actions
            parsed = self._maybe_parse_actions(content)
            if parsed is not None:
                actions = parsed.get("actions", [])
                message = parsed.get("message", "")
                count = self._actions_apply(actions) if (self.chk_perform.GetValue() and actions) else 0
                self._append("agent", f"{message or 'Action response received.'} Applied: {count}")
            else:
                # Plain answer
                self._append("agent", content.strip())

        except Exception as e:
            self._append("agent", f"Chat failed: {e}")

    # ---------- JSON extraction for actions ----------

    def _maybe_parse_actions(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract a single JSON object with 'actions' list if present.
        We do permissive parsing to survive fenced blocks or extra prose.
        """
        if not text:
            return None
        s = text.strip()

        # quick path: pure JSON
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and "actions" in obj:
                return obj
        except Exception:
            pass

        # strip ``` fences if present
        if s.startswith("```"):
            s = s.lstrip("`")
            if s.startswith("json"):
                s = s[4:]
            s = s.rstrip("`").strip()
            try:
                obj = json.loads(s)
                if isinstance(obj, dict) and "actions" in obj:
                    return obj
            except Exception:
                pass

        # scan for the first balanced { ... }
        start = None
        depth = 0
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start is not None:
                        candidate = text[start:i+1]
                        try:
                            obj = json.loads(candidate)
                            if isinstance(obj, dict) and "actions" in obj:
                                return obj
                        except Exception:
                            pass
                        break
        return None
