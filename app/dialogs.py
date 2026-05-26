import wx
import wx.richtext as rt
import requests
from .settings import defaults

# -----------------------------------------------------------
# Font compatibility (supports wxPython 4.0–4.2+)
# -----------------------------------------------------------
try:
    FONT_STYLE_NORMAL = wx.FontStyle.NORMAL
    FONT_WEIGHT_NORMAL = wx.FontWeight.NORMAL
    FONT_WEIGHT_BOLD = wx.FontWeight.BOLD
except AttributeError:
    FONT_STYLE_NORMAL = wx.FONTSTYLE_NORMAL
    FONT_WEIGHT_NORMAL = wx.FONTWEIGHT_NORMAL
    FONT_WEIGHT_BOLD = wx.FONTWEIGHT_BOLD


# -----------------------------------------------------------
# IQ Chat Dialog (DataBuddyDialog)
# -----------------------------------------------------------
class DataBuddyDialog(wx.Dialog):
    """
    Interactive chat dialog (IQ Chat) — matches main_window.py
    No UI changes, just fixes and enhancements.
    """

    def __init__(self, parent, _, __):
        super().__init__(
            parent,
            title="IQ Chat",
            size=(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        panel = wx.Panel(self)
        main = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(panel, label="IQ Chat Assistant")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_SWISS, FONT_STYLE_NORMAL, FONT_WEIGHT_BOLD))
        main.Add(title, 0, wx.ALL, 10)

        # Chat history area
        self.chat_box = rt.RichTextCtrl(
            panel,
            style=wx.VSCROLL | wx.HSCROLL | wx.TE_MULTILINE |
                  wx.TE_READONLY | wx.BORDER_THEME
        )
        self.chat_box.SetFont(wx.Font(11, wx.FONTFAMILY_SWISS, FONT_STYLE_NORMAL, FONT_WEIGHT_NORMAL))
        main.Add(self.chat_box, 1, wx.EXPAND | wx.ALL, 10)

        # Input + send row
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.input.SetFont(wx.Font(11, wx.FONTFAMILY_SWISS, FONT_STYLE_NORMAL, FONT_WEIGHT_NORMAL))
        self.input.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        row.Add(self.input, 1, wx.EXPAND | wx.ALL, 5)

        send_btn = wx.Button(panel, label="Send")
        send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        row.Add(send_btn, 0, wx.ALL, 5)
        main.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Footer
        footer = wx.BoxSizer(wx.HORIZONTAL)
        footer.AddStretchSpacer()
        close_btn = wx.Button(panel, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())
        footer.Add(close_btn, 0, wx.ALL, 10)
        main.Add(footer, 0, wx.EXPAND)

        panel.SetSizer(main)
        self.Layout()

    # -----------------------------------------------------------
    # Chat rendering helpers
    # -----------------------------------------------------------
    def _append(self, who: str, msg: str, color="#ffffff"):
        """Append colored message line."""
        self.chat_box.BeginTextColour(color)
        self.chat_box.WriteText(f"{who}: ")
        self.chat_box.EndTextColour()
        self.chat_box.WriteText(msg.strip() + "\n\n")
        self.chat_box.ShowPosition(self.chat_box.GetLastPosition())

    # -----------------------------------------------------------
    # Message sending
    # -----------------------------------------------------------
    def on_send(self, _):
        msg = self.input.GetValue().strip()
        if not msg:
            return
        self._append("You", msg, "#6ab0f3")
        self.input.SetValue("")
        wx.CallAfter(self._ask_llm, msg)

    # -----------------------------------------------------------
    # LLM Call
    # -----------------------------------------------------------
    def _ask_llm(self, prompt: str):
        provider = defaults.get("provider", "custom")
        api_key = defaults.get("api_key", "")
        model = defaults.get("default_model", "gpt-4o-mini")
        api_url = defaults.get("url", "")

        # Provider-specific overrides
        if provider == "openai":
            api_key = defaults.get("openai_api_key", api_key)
            model = defaults.get("openai_default_model", model)
            api_url = defaults.get("openai_url", api_url)
        elif provider == "gemini":
            api_key = defaults.get("gemini_api_key", api_key)
            model = defaults.get("gemini_default_model", model)
            api_url = f"{defaults.get('gemini_text_url')}/{model}:generateContent?key={api_key}"

        if not api_key:
            self._append("System", "⚠ No API Key set. Open Settings.", "#ff7070")
            return

        # Send and display
        try:
            if provider in ("custom", "openai"):
                payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
                r = requests.post(
                    api_url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                    timeout=45,
                    verify=False,
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
            elif provider == "gemini":
                r = requests.post(
                    api_url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    timeout=45,
                    verify=False,
                )
                r.raise_for_status()
                parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
                text = "".join([p.get("text", "") for p in parts])
            else:
                text = "⚠ Unsupported provider."
        except Exception as e:
            text = f"⚠ Error: {e}"

        clean = self._sanitize_output(text)
        self._append("AI", clean, "#9dfc8f")

    # -----------------------------------------------------------
    # Clean LLM text before display
    # -----------------------------------------------------------
    def _sanitize_output(self, text: str) -> str:
        if not text:
            return ""
        cleaned = text.replace("```", "").replace("**", "").replace("#", "").strip()
        # limit very long outputs
        if len(cleaned) > 2000:
            cleaned = cleaned[:2000] + " ..."
        return cleaned
