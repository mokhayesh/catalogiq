import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple

APP_NAME = "CatalogIQ"
FILENAME = "catalog_config.json"

def _appdata_dir() -> str:
    # %APPDATA%\CatalogIQ on Windows; falls back to ~/.catalogiq if APPDATA missing
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), f".{APP_NAME.lower()}")
    path = os.path.join(base, APP_NAME)
    # If %APPDATA%\CatalogIQ is double-nested (…\CatalogIQ\CatalogIQ) avoid it:
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    return path

def config_path_candidates() -> Tuple[str, str]:
    # Preferred (roaming), and project-local fallback
    roaming = os.path.join(_appdata_dir(), FILENAME)
    local = os.path.join(os.getcwd(), FILENAME)
    return roaming, local

DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 1,
    "general": {
        "default_policy": "Standard",
        "nullable_default": "No",                 # "Yes" | "No"
        "analysis_date_mode": "Auto Today",       # "Auto Today" | "Manual"
        "profile_sample_rows": 10000              # reserved for future auto-profile feature
    },
    "presets": {
        "regex": {
            "Email": r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
            "Phone Number": r"^\+?[0-9 ()\-]{7,}$",
            "Zip": r"^\d{5}(?:-\d{4})?$"
        },
        "data_types": {
            "Email": "VARCHAR(255)",
            "Phone Number": "VARCHAR(25)",
            "Address": "VARCHAR(255)",
            "First Name": "VARCHAR(50)",
            "Last Name": "VARCHAR(50)",
            "Middle Name": "VARCHAR(50)",
            "Loan Amount": "DECIMAL(10,2)"
        }
    },
    "ai": {
        # knobs the dialog can expose later; not used to call OpenAI directly
        "enforce_json_only": True,
        "temperature": 0.2,
        "max_tokens": 800
    }
}

@dataclass
class CatalogConfig:
    data: Dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_CONFIG)))

    @staticmethod
    def load() -> "CatalogConfig":
        roaming, local = config_path_candidates()
        for p in (roaming, local):
            try:
                if os.path.isfile(p):
                    with open(p, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                    # shallow merge with defaults in case of upgrades
                    merged = json.loads(json.dumps(DEFAULT_CONFIG))
                    _deep_merge(merged, raw)
                    return CatalogConfig(merged)
            except Exception:
                # fall through to defaults if corrupt
                pass
        return CatalogConfig()

    def save(self) -> str:
        roaming, local = config_path_candidates()
        path = roaming  # prefer roaming location
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        return path

    # ---------- convenience getters ----------
    def general(self) -> Dict[str, Any]:
        return self.data["general"]

    def regex_presets(self) -> Dict[str, str]:
        return self.data["presets"]["regex"]

    def dtype_presets(self) -> Dict[str, str]:
        return self.data["presets"]["data_types"]

    # ---------- validation ----------
    def validate(self) -> Tuple[bool, str]:
        # validate general
        gen = self.data.get("general", {})
        if gen.get("nullable_default") not in ("Yes", "No"):
            return False, "Nullable Default must be 'Yes' or 'No'."

        if gen.get("analysis_date_mode") not in ("Auto Today", "Manual"):
            return False, "Analysis Date Mode must be 'Auto Today' or 'Manual'."

        # validate regex
        for k, pattern in self.regex_presets().items():
            try:
                re.compile(pattern)
            except re.error as ex:
                return False, f"Invalid regex for '{k}': {ex}"

        # basic dtype non-empty
        for k, dtype in self.dtype_presets().items():
            if not str(dtype).strip():
                return False, f"Data Type preset for '{k}' cannot be empty."

        return True, "OK"

# --------- helpers ----------
def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
