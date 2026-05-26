# =====================================================================
# profiling_utils.py — Advanced P3 Profiling Engine for CatalogIQ
# =====================================================================

from __future__ import annotations
import re
import numpy as np
import pandas as pd
from typing import List, Dict


CATALOG_COLS = [
    "Field", "Friendly Name", "Description", "Data Type",
    "Nullable", "Example", "Analysis Date",
    "Attestation", "Policy", "Regex Pattern"
]


def _guess_regex(series: pd.Series) -> str:
    """Basic regex pattern synthesis."""
    try:
        vals = series.dropna().astype(str).head(100).tolist()
        if not vals:
            return ""

        if all(v.isdigit() for v in vals):
            return r"^\d+$"

        if any("@" in v for v in vals):
            return r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if any("-" in v for v in vals):
            return r"^[A-Za-z0-9\-_.]+$"

        return r"^.*$"
    except:
        return ""


def _dtype(series: pd.Series) -> str:
    dt = str(series.dtype)
    if dt.startswith("int") or dt.startswith("float"):
        return dt
    if pd.to_datetime(series, errors="ignore") is not None:
        return dt
    return dt


def profile_dataframe_to_catalog(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict] = []

    for col in df.columns:
        s = df[col]

        dtype = _dtype(s)
        nullable = "Yes" if s.isna().any() else "No"
        example = s.dropna().iloc[0] if s.dropna().size > 0 else ""

        uniq = s.nunique(dropna=True)
        null_pct = round(float(s.isna().mean()) * 100, 2)

        desc = f"Unique={uniq}, Null%={null_pct}"

        regex = _guess_regex(s)

        rows.append({
            "Field": col,
            "Friendly Name": col.replace("_", " ").title(),
            "Description": desc,
            "Data Type": dtype,
            "Nullable": nullable,
            "Example": str(example),
            "Analysis Date": "",
            "Attestation": "",
            "Policy": "",
            "Regex Pattern": regex
        })

    return pd.DataFrame(rows, columns=CATALOG_COLS)
