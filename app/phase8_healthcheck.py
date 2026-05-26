from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check_import(module: str) -> bool:
    try:
        importlib.import_module(module)
        print(f"OK   {module}")
        return True
    except Exception as exc:
        print(f"FAIL {module}: {exc}")
        return False


def main() -> int:
    print("CatalogIQ Phase 8 Healthcheck")
    print("=" * 40)

    required = [
        "wx",
        "pandas",
        "openpyxl",
        "requests",
        "yaml",
        "boto3",
        "snowflake.connector",
        "app.connector_profiles",
        "app.enterprise_connectors",
        "app.agentic_catalog_dialog",
        "app.catalogiq_command_center",
    ]

    ok = True
    for module in required:
        ok = check_import(module) and ok

    print()
    print("Repository checks")
    print("=" * 40)

    for path in [".env.example", ".gitignore", "app/connector_profiles.py"]:
        exists = (ROOT / path).exists()
        print(("OK   " if exists else "FAIL ") + path)
        ok = exists and ok

    from app.connector_profiles import save_profile, list_profiles, profile_store_path

    save_profile(
        name="sample_snowflake_env_profile",
        connector_type="snowflake",
        config={
            "account": "YOUR_ACCOUNT",
            "user": "YOUR_USER",
            "warehouse": "YOUR_WAREHOUSE",
            "database": "YOUR_DATABASE",
            "schema": "YOUR_SCHEMA",
            "password_env": "SNOWFLAKE_PASSWORD",
        },
    )

    print()
    print("Connector profile store")
    print("=" * 40)
    print(profile_store_path())
    print(f"profiles: {len(list_profiles())}")

    print()
    if ok:
        print("PHASE 8 HEALTHCHECK PASSED")
        return 0

    print("PHASE 8 HEALTHCHECK FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
