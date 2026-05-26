import boto3
import requests
import io
import csv
import os
import json
import urllib3
from datetime import datetime
from botocore import UNSIGNED
from botocore.config import Config

# Disable SSL warnings (useful for internal/self-signed endpoints)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Settings helpers – keep AWS keys in the existing Settings JSON
# ---------------------------------------------------------------------------

APPDATA_DIR = os.path.join(os.path.expanduser("~"), ".catalogiq")
SETTINGS_PATHS = [
    os.path.join(os.getcwd(), "settings.json"),
    os.path.join(APPDATA_DIR, "settings.json"),
]


def _load_settings() -> dict:
    """
    Load the same settings JSON that the Settings dialog uses.

    We intentionally duplicate this light-weight loader here so the S3
    utilities work both:
      • when running `python -m app.main`
      • when running the frozen CatalogIQ.exe
    """
    data: dict = {}
    for p in SETTINGS_PATHS:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                break
            except Exception:
                continue
    return data


def _make_s3_client(anonymous: bool = False):
    """Return a boto3 S3 client, using Settings-based credentials when available.

    If no keys are set in Settings, boto3 falls back to its normal credential
    chain (env vars, shared credentials file, etc.). An anonymous client is
    used for public buckets when requested.
    """
    if anonymous:
        return boto3.client("s3", config=Config(signature_version=UNSIGNED))

    cfg = _load_settings()
    access_key = cfg.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = cfg.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
    session_token = cfg.get("aws_session_token") or os.getenv("AWS_SESSION_TOKEN")
    region = (
        cfg.get("aws_s3_region")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "us-east-1"
    )

    session = boto3.Session(
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
        aws_session_token=session_token or None,
        region_name=region or None,
    )
    return session.client("s3")


# ---------------------------------------------------------------------------
# Public helpers used by the rest of the app
# ---------------------------------------------------------------------------

def download_text_from_uri(uri: str) -> str:
    """Download and return the contents of a text file from S3 or HTTP(S) URI."""
    cfg = _load_settings()
    if uri.startswith("s3://"):
        _, rest = uri.split("s3://", 1)
        bucket, key = rest.split("/", 1)

        # Try with credentials from Settings first, then anonymous access.
        for anonymous in (False, True):
            try:
                client = _make_s3_client(anonymous=anonymous)
                obj = client.get_object(Bucket=bucket, Key=key)
                return obj["Body"].read().decode()
            except Exception:
                if anonymous:
                    # Last resort: direct HTTPS URL to the bucket/region.
                    region = cfg.get("aws_s3_region", "us-east-1")
                    url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
                    r = requests.get(url, verify=False, timeout=60)
                    r.raise_for_status()
                    return r.text
                # otherwise loop and try anonymous=True
                continue

    # Non-S3 (generic HTTP/S) handling
    r = requests.get(uri, verify=False, timeout=60)
    r.raise_for_status()
    return r.text


def upload_to_s3(process: str, headers, data) -> str:
    """Upload a CSV to the appropriate S3 bucket for the given process.

    The bucket name is still read from the existing Settings keys
    `aws_<process>_bucket`, so nothing changes in how you configure it.
    """
    cfg = _load_settings()
    bucket = (cfg.get(f"aws_{process.lower()}_bucket") or "").strip()
    if not bucket:
        return f"No bucket configured for {process}"

    buf = io.StringIO()
    csv.writer(buf).writerows([headers, *data])
    key = f"{process}_{datetime.now():%Y%m%d_%H%M%S}.csv"

    try:
        _make_s3_client().put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
        return f"Uploaded to s3://{bucket}/{key}"
    except Exception as e:
        return f"S3 upload failed: {e}"
