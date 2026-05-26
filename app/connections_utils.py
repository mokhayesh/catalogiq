# =====================================================================
# connections_utils.py — Lightweight connectors for S3, SQL, API, Fabric
# =====================================================================

from __future__ import annotations
from typing import Dict, Any, Tuple, List
import pandas as pd

# optional imports
try:
    import boto3
except:
    boto3 = None

try:
    import requests
except:
    requests = None

try:
    import sqlalchemy as sa
except:
    sa = None

# --------------------------
# S3
# --------------------------
def test_s3(creds: Dict[str, Any]) -> Tuple[bool, str]:
    if boto3 is None:
        return False, "boto3 not installed"
    try:
        client = boto3.client(
            "s3",
            aws_access_key_id=creds.get("Access Key"),
            aws_secret_access_key=creds.get("Secret Key"),
        )
        client.list_objects_v2(Bucket=creds.get("Bucket"), MaxKeys=1)
        return True, "Connected"
    except Exception as e:
        return False, str(e)


def list_s3_objects(creds: Dict[str, Any]) -> List[Dict]:
    if boto3 is None:
        return []
    try:
        client = boto3.client(
            "s3",
            aws_access_key_id=creds.get("Access Key"),
            aws_secret_access_key=creds.get("Secret Key"),
        )
        resp = client.list_objects_v2(Bucket=creds.get("Bucket"), MaxKeys=50)
        return [{"name": obj["Key"], "type": "file"} for obj in resp.get("Contents", [])]
    except:
        return []


def load_s3_sample(creds, key) -> pd.DataFrame:
    if boto3 is None:
        return pd.DataFrame()
    import io
    s3 = boto3.client(
        "s3",
        aws_access_key_id=creds.get("Access Key"),
        aws_secret_access_key=creds.get("Secret Key"),
    )
    obj = s3.get_object(Bucket=creds.get("Bucket"), Key=key)
    data = obj["Body"].read()
    try:
        return pd.read_csv(io.BytesIO(data))
    except:
        try:
            return pd.read_json(io.BytesIO(data))
        except:
            return pd.DataFrame()


# --------------------------
# SQL Server
# --------------------------
def _engine(creds):
    if sa is None:
        return None
    user = creds.get("Username")
    pwd = creds.get("Password")
    server = creds.get("Server")
    db = creds.get("Database")
    driver = creds.get("Driver (optional)") or "ODBC Driver 17 for SQL Server"
    conn = f"mssql+pyodbc://{user}:{pwd}@{server}/{db}?driver={driver.replace(' ','+')}"
    try:
        return sa.create_engine(conn)
    except:
        return None


def test_sql(creds) -> Tuple[bool, str]:
    eng = _engine(creds)
    if eng is None:
        return False, "No engine"
    try:
        with eng.connect() as c:
            c.execute(sa.text("SELECT 1"))
        return True, "Connected"
    except Exception as e:
        return False, str(e)


def list_sql_tables(creds) -> List[Dict[str,str]]:
    eng = _engine(creds)
    if eng is None:
        return []
    try:
        with eng.connect() as c:
            rows = c.execute(sa.text("SELECT TABLE_SCHEMA+'.'+TABLE_NAME FROM INFORMATION_SCHEMA.TABLES")).fetchall()
        return [{"name": r[0], "type": "table"} for r in rows]
    except:
        return []


def load_sql_table_sample(creds, table) -> pd.DataFrame:
    eng = _engine(creds)
    if eng is None:
        return pd.DataFrame()
    try:
        return pd.read_sql(f"SELECT TOP 50 * FROM {table}", eng)
    except:
        return pd.DataFrame()


# --------------------------
# REST API
# --------------------------
def test_api(creds) -> Tuple[bool,str]:
    if requests is None:
        return False, "requests missing"
    url = creds.get("Base URL", "") + creds.get("Endpoint", "")
    try:
        r = requests.get(url, timeout=5)
        return (r.ok, f"HTTP {r.status_code}")
    except Exception as e:
        return False, str(e)


def load_api_sample(creds) -> pd.DataFrame:
    if requests is None:
        return pd.DataFrame()
    url = creds.get("Base URL", "") + creds.get("Endpoint", "")
    try:
        r = requests.get(url, timeout=10)
        js = r.json()
        if isinstance(js, list):
            return pd.DataFrame(js)
        if isinstance(js, dict):
            return pd.json_normalize(js)
    except:
        pass
    return pd.DataFrame()


# --------------------------
# Fabric / Purview (placeholders)
# --------------------------
def test_fabric(creds):
    return True, "Token accepted"

def list_fabric_tables(creds):
    return [{"name": "Sales", "type": "table"}, {"name": "Customers", "type": "table"}]

def load_fabric_table_sample(creds, name):
    if name.lower() == "sales":
        return pd.DataFrame({"order": [1, 2], "amount": [33, 55]})
    return pd.DataFrame({"customer": [1, 2], "email": ["a@x.com","b@y.com"]})


def test_purview(creds):
    return True, "Credentials ok"

def list_purview_assets(creds):
    return [{"name":"asset1","type":"asset"},{"name":"asset2","type":"asset"}]

def load_purview_asset_sample(creds, name):
    return pd.DataFrame({"asset":[name], "ok":[True]})
