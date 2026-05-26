import os
import json
import wx

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Defaults & persistence
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DEFAULTS_FILE = "defaults.json"

# The master defaults dictionary
defaults = {
    "provider": "custom",

    "url": "http://127.0.0.1:8000/v1/chat/completions",
    "api_key": "sk-aldin-local-123",
    "default_model": "aldin-mini",
    "fast_model": "aldin-mini",

    "custom_url": "http://127.0.0.1:8000/v1/chat/completions",
    "custom_api_key": "sk-aldin-local-123",
    "custom_model": "aldin-mini",

    "openai_url": "https://api.openai.com/v1/chat/completions",
    "openai_api_key": "YOUR_OPENAI_API_KEY_HERE",
    "openai_org": "",
    "openai_default_model": "gpt-4o",
    "openai_fast_model": "gpt-4o-mini",

    "gemini_text_url": "https://generativelanguage.googleapis.com/v1beta/models",
    "gemini_api_key": "",
    "gemini_default_model": "gemini-1.5-pro",
    "gemini_fast_model": "gemini-1.5-flash",

    "max_tokens": "800",
    "temperature": "0.6",
    "top_p": "1.0",
    "frequency_penalty": "0.0",
    "presence_penalty": "0.0",

    "image_provider": "auto",
    "image_model": "gpt-image-1",
    "image_generation_url": "https://api.openai.com/v1/images/generations",
    "stability_api_key": "",

    "azure_ttts_key": "",
    "azure_tts_region": "",

    "aws_access_key_id": "",
    "aws_secret_access_key": "",
    "aws_session_token": "",
    "aws_s3_region": "us-east-1",

    "smtp_server": "",
    "smtp_port": "",
    "email_username": "",
    "email_password": "",
    "from_email": "",
    "to_email": "",

    "filepath": os.path.expanduser("~"),
}

# Load saved defaults
if os.path.exists(DEFAULTS_FILE):
    try:
        file_defaults = json.load(open(DEFAULTS_FILE, "r", encoding="utf-8"))
        defaults.update(file_defaults)
    except Exception:
        pass


def save_defaults() -> None:
    json.dump(defaults, open(DEFAULTS_FILE, "w", encoding="utf-8"), indent=2)
    wx.MessageBox("Settings saved.", "Settings", wx.OK | wx.ICON_INFORMATION)


# ----------------------------------------------------------------------
# âœ… BACKWARD COMPATIBILITY: Alias used by main_window.py
# ----------------------------------------------------------------------
# main_window.py expects:
#   from .settings import settings_defaults
#
# We map that name to your "defaults" dict so nothing breaks.
# ----------------------------------------------------------------------

settings_defaults = defaults   # <âœ… REQUIRED FIX â€” now main_window.py will work>


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Model lists
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

OPENAI_MAIN = ["gpt-4o", "o4-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4o-mini"]
OPENAI_FAST = ["gpt-4o-mini", "gpt-4.1-mini", "o4-mini"]
OPENAI_IMAGE = ["gpt-image-1"]

GEMINI_MAIN = ["gemini-1.5-pro", "gemini-1.5-flash"]
GEMINI_FAST = ["gemini-1.5-flash", "gemini-1.5-flash-8b"]
GEMINI_IMAGE = ["gemini-1.5-flash", "gemini-1.5-pro"]

STABILITY_IMAGE = ["sdxl", "sd3-medium"]

CUSTOM_MAIN = ["aldin-mini"]
CUSTOM_FAST = ["aldin-mini"]

IMAGE_PROVIDERS = ["auto", "openai", "gemini", "stability", "none"]
PROVIDERS = ["custom", "openai", "gemini", "auto"]

PROFILE_KEYS = {
    "custom": {
        "url": "custom_url",
        "api_key": "custom_api_key",
        "default_model": "custom_model",
        "fast_model": "custom_model",
    },
    "openai": {
        "url": "openai_url",
        "api_key": "openai_api_key",
        "org": "openai_org",
        "default_model": "openai_default_model",
        "fast_model": "openai_fast_model",
    },
    "gemini": {
        "url": "gemini_text_url",
        "api_key": "gemini_api_key",
        "default_model": "gemini_default_model",
        "fast_model": "gemini_fast_model",
    },
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SettingsWindow
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SettingsWindow(wx.Dialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            title="Settings",
            size=(640, 880),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        panel = wx.Panel(self)
        s = wx.GridBagSizer(6, 6)
        row = 0

        def add_field(label, value):
            nonlocal row
            s.Add(wx.StaticText(panel, label=label),
                  (row, 0), flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            ctrl = wx.TextCtrl(panel, value=value)
            s.Add(ctrl, (row, 1), span=(1, 3), flag=wx.EXPAND)
            row += 1
            return ctrl

        # Provider
        s.Add(wx.StaticText(panel, label="Provider:"), (row, 0),
              flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.provider = wx.Choice(panel, choices=PROVIDERS)
        selected = defaults.get("provider", "custom")
        self.provider.SetSelection(PROVIDERS.index(selected))
        self.provider.Bind(wx.EVT_CHOICE, self._on_provider_change)
        s.Add(self.provider, (row, 1), span=(1, 3), flag=wx.EXPAND)
        row += 1

        # URL and API-Key
        self.api_key = add_field("API Key:", defaults.get("api_key", ""))
        self.org = add_field("OpenAI Org (optional):", defaults.get("openai_org", ""))
        self.chat_url = add_field("Chat URL:", defaults.get("url", ""))

        # Models
        s.Add(wx.StaticText(panel, label="Default Model:"), (row, 0),
              flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.default_model = wx.Choice(panel)
        s.Add(self.default_model, (row, 1))

        s.Add(wx.StaticText(panel, label="Fast Model:"), (row, 2),
              flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.fast_model = wx.Choice(panel)
        s.Add(self.fast_model, (row, 3))
        row += 1

        # Token settings
        self.max_tokens = add_field("Max Tokens:", defaults.get("max_tokens", "800"))
        self.temperature = add_field("Temperature:", defaults.get("temperature", "0.6"))
        self.top_p = add_field("Top P:", defaults.get("top_p", "1.0"))
        self.freq_pen = add_field("Frequency Penalty:", defaults.get("frequency_penalty", "0.0"))
        self.pres_pen = add_field("Presence Penalty:", defaults.get("presence_penalty", "0.0"))

        # Image provider/models
        s.Add(wx.StaticText(panel, label="Image Provider:"), (row, 0),
              flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.image_provider = wx.Choice(panel, choices=IMAGE_PROVIDERS)
        self.image_provider.SetSelection(IMAGE_PROVIDERS.index(defaults.get("image_provider", "auto")))
        self.image_provider.Bind(wx.EVT_CHOICE, self._on_image_provider_change)
        s.Add(self.image_provider, (row, 1))

        s.Add(wx.StaticText(panel, label="Image Model:"), (row, 2),
              flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        self.image_model = wx.Choice(panel)
        s.Add(self.image_model, (row, 3))
        row += 1

        self.image_url = add_field("Image URL (OpenAI):",
                                   defaults.get("image_generation_url", "https://api.openai.com/v1/images/generations"))
        self.stability = add_field("Stability API Key:", defaults.get("stability_api_key", ""))

        # Azure
        self.azure_key = add_field("Azure TTS Key:", defaults.get("azure_ttts_key", ""))
        self.azure_region = add_field("Azure TTS Region:", defaults.get("azure_tts_region", ""))

        # AWS
        self.aws_key = add_field("AWS Access Key:", defaults.get("aws_access_key_id", ""))
        self.aws_secret = add_field("AWS Secret Key:", defaults.get("aws_secret_access_key", ""))
        self.aws_token = add_field("AWS Session Token:", defaults.get("aws_session_token", ""))
        self.aws_region = add_field("AWS Region:", defaults.get("aws_s3_region", "us-east-1"))

        # Email
        self.smtp_server = add_field("SMTP Server:", defaults.get("smtp_server", ""))
        self.smtp_port = add_field("SMTP Port:", defaults.get("smtp_port", ""))
        self.email_user = add_field("Email Username:", defaults.get("email_username", ""))
        self.email_pass = add_field("Email Password:", defaults.get("email_password", ""))
        self.from_email = add_field("From Email:", defaults.get("from_email", ""))
        self.to_email = add_field("To Email:", defaults.get("to_email", ""))

        # Save button
        save_btn = wx.Button(panel, label="Save Settings")
        save_btn.Bind(wx.EVT_BUTTON, self.on_save)
        s.Add(save_btn, (row, 0), span=(1, 4),
              flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        panel.SetSizerAndFit(s)
        self.Layout()

        # Init dropdowns
        self._refresh_model_choices()
        self._refresh_image_models()
        self._apply_provider_profile(defaults.get("provider", "custom"))

    # Dropdown logic
    def _select_choice(self, ctrl, value):
        if not value:
            return
        options = [ctrl.GetString(i) for i in range(ctrl.GetCount())]
        if value in options:
            ctrl.SetSelection(options.index(value))

    def _on_provider_change(self, _):
        provider = PROVIDERS[self.provider.GetSelection()]
        self._refresh_model_choices()
        self._apply_provider_profile(provider)

    def _on_image_provider_change(self, _):
        self._refresh_image_models()

    def _refresh_model_choices(self):
        provider = PROVIDERS[self.provider.GetSelection()]
        self.default_model.Clear()
        self.fast_model.Clear()

        if provider in ("custom", "auto"):
            [self.default_model.Append(m) for m in CUSTOM_MAIN]
            [self.fast_model.Append(m) for m in CUSTOM_FAST]

        elif provider == "openai":
            [self.default_model.Append(m) for m in OPENAI_MAIN]
            [self.fast_model.Append(m) for m in OPENAI_FAST]

        elif provider == "gemini":
            [self.default_model.Append(m) for m in GEMINI_MAIN]
            [self.fast_model.Append(m) for m in GEMINI_FAST]

        if self.default_model.GetCount() == 0:
            self.default_model.Append(defaults.get("default_model", "aldin-mini"))
        if self.fast_model.GetCount() == 0:
            self.fast_model.Append(defaults.get("fast_model", "aldin-mini"))

    def _refresh_image_models(self):
        provider = IMAGE_PROVIDERS[self.image_provider.GetSelection()]
        self.image_model.Clear()

        if provider in ("auto", "openai"):
            [self.image_model.Append(m) for m in OPENAI_IMAGE]
        elif provider == "gemini":
            [self.image_model.Append(m) for m in GEMINI_IMAGE]
        elif provider == "stability":
            [self.image_model.Append(m) for m in STABILITY_IMAGE]
        else:
            self.image_model.Append(defaults.get("image_model", "gpt-image-1"))

        self._select_choice(self.image_model, defaults.get("image_model"))

    def _apply_provider_profile(self, provider):
        keys = PROFILE_KEYS.get(provider, {})

        # URL
        url_key = keys.get("url")
        self.chat_url.SetValue(defaults.get(url_key, defaults.get("url", "")))

        # API key
        key_key = keys.get("api_key")
        self.api_key.SetValue(defaults.get(key_key, defaults.get("api_key", "")))

        # OpenAI Org activation
        if provider == "openai":
            self.org.Enable(True)
            self.org.SetValue(defaults.get("openai_org", ""))
        else:
            self.org.Enable(False)

        # Models
        default_m = defaults.get(keys.get("default_model", ""), defaults.get("default_model"))
        fast_m = defaults.get(keys.get("fast_model", ""), defaults.get("fast_model"))

        self._select_choice(self.default_model, default_m)
        self._select_choice(self.fast_model, fast_m)

    # Save settings
    def on_save(self, _):
        provider = PROVIDERS[self.provider.GetSelection()]

        # Basic
        defaults["provider"] = provider
        defaults["url"] = self.chat_url.GetValue().strip()
        defaults["api_key"] = self.api_key.GetValue().strip()
        defaults["openai_org"] = self.org.GetValue().strip()
        defaults["default_model"] = self.default_model.GetStringSelection()
        defaults["fast_model"] = self.fast_model.GetStringSelection()
        defaults["max_tokens"] = self.max_tokens.GetValue().strip()
        defaults["temperature"] = self.temperature.GetValue().strip()
        defaults["top_p"] = self.top_p.GetValue().strip()
        defaults["frequency_penalty"] = self.freq_pen.GetValue().strip()
        defaults["presence_penalty"] = self.pres_pen.GetValue().strip()

        # Provider profiles
        keys = PROFILE_KEYS.get(provider, {})
        if "url" in keys:
            defaults[keys["url"]] = defaults["url"]
        if "api_key" in keys:
            defaults[keys["api_key"]] = defaults["api_key"]
        if "default_model" in keys:
            defaults[keys["default_model"]] = defaults["default_model"]
        if "fast_model" in keys:
            defaults[keys["fast_model"]] = defaults["fast_model"]

        # Image
        defaults["image_provider"] = IMAGE_PROVIDERS[self.image_provider.GetSelection()]
        defaults["image_model"] = self.image_model.GetStringSelection()
        defaults["image_generation_url"] = self.image_url.GetValue().strip()
        defaults["stability_api_key"] = self.stability.GetValue().strip()

        # Azure
        defaults["azure_ttts_key"] = self.azure_key.GetValue().strip()
        defaults["azure_tts_region"] = self.azure_region.GetValue().strip()

        # AWS
        defaults["aws_access_key_id"] = self.aws_key.GetValue().strip()
        defaults["aws_secret_access_key"] = self.aws_secret.GetValue().strip()
        defaults["aws_session_token"] = self.aws_token.GetValue().strip()
        defaults["aws_s3_region"] = self.aws_region.GetValue().strip()

        # Email
        defaults["smtp_server"] = self.smtp_server.GetValue().strip()
        defaults["smtp_port"] = self.smtp_port.GetValue().strip()
        defaults["email_username"] = self.email_user.GetValue().strip()
        defaults["email_password"] = self.email_pass.GetValue().strip()
        defaults["from_email"] = self.from_email.GetValue().strip()
        defaults["to_email"] = self.to_email.GetValue().strip()

        save_defaults()
        self.EndModal(wx.ID_OK)

