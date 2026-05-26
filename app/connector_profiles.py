from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


APP_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = APP_ROOT / ".catalogiq_local"
PROFILE_PATH = LOCAL_DIR / "connector_profiles.json"


@dataclass
class ConnectorProfile:
    name: str
    connector_type: str
    config: Dict[str, Any]
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_store() -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        PROFILE_PATH.write_text(json.dumps({"profiles": []}, indent=2), encoding="utf-8")


def _read_store() -> Dict[str, Any]:
    _ensure_store()
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": []}


def _write_store(data: Dict[str, Any]) -> None:
    _ensure_store()
    PROFILE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_profiles(connector_type: Optional[str] = None) -> List[Dict[str, Any]]:
    data = _read_store()
    profiles = data.get("profiles", [])
    if connector_type:
        profiles = [p for p in profiles if p.get("connector_type") == connector_type]
    return profiles


def get_profile(name: str) -> Optional[Dict[str, Any]]:
    for profile in list_profiles():
        if profile.get("name") == name:
            return profile
    return None


def save_profile(name: str, connector_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Saves reusable connector metadata.

    Do not store raw passwords, API keys, or access keys here.
    Store env var names instead, such as:
      SNOWFLAKE_PASSWORD_ENV = "SNOWFLAKE_PASSWORD"
      AWS_PROFILE = "default"
    """
    data = _read_store()
    profiles = data.get("profiles", [])
    existing = next((p for p in profiles if p.get("name") == name), None)

    cleaned = sanitize_config(config)

    if existing:
        existing["connector_type"] = connector_type
        existing["config"] = cleaned
        existing["updated_at"] = _now()
        result = existing
    else:
        result = asdict(
            ConnectorProfile(
                name=name,
                connector_type=connector_type,
                config=cleaned,
                created_at=_now(),
                updated_at=_now(),
            )
        )
        profiles.append(result)

    data["profiles"] = profiles
    _write_store(data)
    return result


def delete_profile(name: str) -> bool:
    data = _read_store()
    profiles = data.get("profiles", [])
    new_profiles = [p for p in profiles if p.get("name") != name]
    if len(new_profiles) == len(profiles):
        return False
    data["profiles"] = new_profiles
    _write_store(data)
    return True


def sanitize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    blocked_terms = ["password", "secret", "token", "api_key", "access_key", "private_key"]
    cleaned: Dict[str, Any] = {}

    for key, value in config.items():
        lower = key.lower()
        if any(term in lower for term in blocked_terms):
            if str(key).endswith("_env") or str(key).endswith("_profile"):
                cleaned[key] = value
            else:
                cleaned[key] = "DO_NOT_STORE_SECRET_USE_ENV_VAR"
        else:
            cleaned[key] = value

    return cleaned


def masked_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    copy = json.loads(json.dumps(profile))
    config = copy.get("config", {})
    for key in list(config.keys()):
        lower = key.lower()
        if any(term in lower for term in ["password", "secret", "token", "api_key", "access_key"]):
            config[key] = "***"
    return copy


def profile_store_path() -> str:
    _ensure_store()
    return str(PROFILE_PATH)
