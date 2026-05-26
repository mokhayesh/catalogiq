from __future__ import annotations

"""CatalogIQ enterprise connector adapters.

Active starter connectors:
- AWS S3 object ingestion for CSV/TXT/Excel
- Snowflake table/query ingestion

Credentials are used only in memory for the active session and are not saved.
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ConnectorResult:
    dataframe: pd.DataFrame
    dataset_name: str
    source_label: str
    cached_file: str = ""


def safe_dataset_name(value: str, fallback: str = "dataset") -> str:
    text = str(value or fallback).strip()
    text = re.sub(r"[^a-zA-Z0-9_\-]+", "_", text)
    text = text.strip("_")
    return text or fallback


def _read_local_file(path: str) -> pd.DataFrame:
    suffix = Path(path).suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    if suffix in {".csv", ".txt"}:
        try:
            return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=["", "NULL", "null", "None"])
        except UnicodeDecodeError:
            return pd.read_csv(path, dtype=str, encoding="latin-1", keep_default_na=False, na_values=["", "NULL", "null", "None"])
    raise ValueError(f"Unsupported file type for connector read: {suffix}")


def read_s3_dataset(
    *,
    bucket: str,
    key: str,
    region: str = "",
    profile_name: str = "",
    access_key_id: str = "",
    secret_access_key: str = "",
    session_token: str = "",
    endpoint_url: str = "",
) -> ConnectorResult:
    try:
        import boto3  # type: ignore
    except Exception as exc:
        raise ImportError("AWS S3 connector requires boto3. Install with: python -m pip install boto3") from exc

    bucket = bucket.strip()
    key = key.strip().lstrip("/")
    if not bucket or not key:
        raise ValueError("Bucket and key are required for the S3 connector.")

    session_kwargs = {}
    if profile_name.strip():
        session_kwargs["profile_name"] = profile_name.strip()
    if region.strip():
        session_kwargs["region_name"] = region.strip()
    if access_key_id.strip() and secret_access_key.strip():
        session_kwargs["aws_access_key_id"] = access_key_id.strip()
        session_kwargs["aws_secret_access_key"] = secret_access_key.strip()
        if session_token.strip():
            session_kwargs["aws_session_token"] = session_token.strip()

    session = boto3.Session(**session_kwargs)
    client_kwargs = {}
    if endpoint_url.strip():
        client_kwargs["endpoint_url"] = endpoint_url.strip()
    s3 = session.client("s3", **client_kwargs)

    suffix = Path(key).suffix.lower() or ".csv"
    cache_root = Path(os.getcwd()) / ".catalogiq_connector_cache" / "s3"
    cache_root.mkdir(parents=True, exist_ok=True)
    local_name = safe_dataset_name(f"{bucket}_{key.replace('/', '_')}") + suffix
    local_path = cache_root / local_name

    s3.download_file(bucket, key, str(local_path))
    df = _read_local_file(str(local_path))
    dataset_name = safe_dataset_name(Path(key).stem, fallback=safe_dataset_name(bucket))
    return ConnectorResult(df, dataset_name, f"s3://{bucket}/{key}", str(local_path))


def read_snowflake_dataset(
    *,
    account: str,
    user: str,
    password: str,
    warehouse: str,
    database: str,
    schema: str,
    role: str = "",
    table: str = "",
    sql: str = "",
    row_limit: int = 10000,
) -> ConnectorResult:
    try:
        import snowflake.connector  # type: ignore
    except Exception as exc:
        raise ImportError("Snowflake connector requires snowflake-connector-python. Install with: python -m pip install snowflake-connector-python") from exc

    account = account.strip()
    user = user.strip()
    warehouse = warehouse.strip()
    database = database.strip()
    schema = schema.strip()
    table = table.strip()
    sql = sql.strip().rstrip(";")
    if not all([account, user, password, warehouse, database, schema]):
        raise ValueError("Account, user, password, warehouse, database, and schema are required for Snowflake.")
    if not table and not sql:
        raise ValueError("Enter either a table name or a SQL query.")

    limit = max(1, int(row_limit or 10000))
    if sql:
        final_sql = f"SELECT * FROM ({sql}) AS CATALOGIQ_SRC LIMIT {limit}"
        dataset_name = safe_dataset_name("snowflake_query")
    else:
        final_sql = f"SELECT * FROM {table} LIMIT {limit}"
        dataset_name = safe_dataset_name(table.split(".")[-1].replace('"', ""))

    conn_kwargs = {
        "account": account,
        "user": user,
        "password": password,
        "warehouse": warehouse,
        "database": database,
        "schema": schema,
    }
    if role.strip():
        conn_kwargs["role"] = role.strip()

    conn = snowflake.connector.connect(**conn_kwargs)
    try:
        cur = conn.cursor()
        try:
            cur.execute(final_sql)
            df = cur.fetch_pandas_all()
        finally:
            cur.close()
    finally:
        conn.close()

    source_label = f"snowflake://{account}/{database}/{schema}/{table or 'query'}"
    return ConnectorResult(df, dataset_name, source_label)
