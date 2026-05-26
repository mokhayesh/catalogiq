"""CatalogIQ Platform Core v1.

Non-invasive service layer for Phase 1: dataset profiling, metadata generation,
governance detection, DQ rule suggestions, and exportable catalog packages.
This module has no wx dependency so it can be reused by the desktop UI, CLI,
and future API service.
"""
from __future__ import annotations

import csv
import datetime as _dt
import json
import math
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

PII_NAME_PATTERNS = {
    "Email": re.compile(r"(^|_)(email|e_mail|mail)(_|$)", re.I),
    "Phone": re.compile(r"(^|_)(phone|mobile|cell|tel|telephone)(_|$)", re.I),
    "SSN": re.compile(r"(^|_)(ssn|social_security)(_|$)", re.I),
    "Person Name": re.compile(r"(^|_)(name|first_name|last_name|full_name|customer_name|employee_name)(_|$)", re.I),
    "Address": re.compile(r"(^|_)(address|street|city|state|zip|postal)(_|$)", re.I),
    "Date of Birth": re.compile(r"(^|_)(dob|birth|birth_date|date_of_birth)(_|$)", re.I),
    "Account Identifier": re.compile(r"(^|_)(account|acct|customer_id|client_id|member_id|user_id)(_|$)", re.I),
    "Financial": re.compile(r"(^|_)(amount|balance|salary|revenue|cost|price|payment|card|credit)(_|$)", re.I),
}

PII_VALUE_PATTERNS = {
    "Email": re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.I),
    "Phone": re.compile(r"^(\+?1[\s\-.]?)?(\(?\d{3}\)?[\s\-.]?)\d{3}[\s\-.]?\d{4}$"),
    "SSN": re.compile(r"^\d{3}-?\d{2}-?\d{4}$"),
    "Credit Card-like": re.compile(r"^(?:\d[ -]*?){13,19}$"),
}

BUSINESS_WORDS = {
    "id": "identifier",
    "qty": "quantity",
    "num": "number",
    "amt": "amount",
    "dt": "date",
    "ts": "timestamp",
    "addr": "address",
    "desc": "description",
    "cust": "customer",
    "acct": "account",
}

@dataclass
class FieldProfile:
    name: str
    inferred_type: str
    pandas_type: str
    nullable: str
    null_count: int
    null_pct: float
    unique_count: int
    unique_pct: float
    sample_values: List[str]
    min_value: str = ""
    max_value: str = ""
    avg_length: float = 0.0
    pii_flag: str = "No"
    pii_category: str = ""
    sensitivity: str = "Internal"
    quality_notes: str = ""
    description: str = ""
    dq_rules: List[str] = None  # type: ignore[assignment]

    def to_row(self) -> Dict[str, Any]:
        d = asdict(self)
        d["sample_values"] = "; ".join(self.sample_values)
        d["dq_rules"] = "\n".join(self.dq_rules or [])
        d["null_pct"] = round(self.null_pct, 2)
        d["unique_pct"] = round(self.unique_pct, 2)
        d["avg_length"] = round(self.avg_length, 2)
        return d

@dataclass
class DatasetProfile:
    dataset_name: str
    source_path: str
    profiled_at: str
    row_count: int
    column_count: int
    duplicate_rows: int
    fields: List[FieldProfile]
    governance_findings: List[str]
    quality_score: int
    executive_summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "source_path": self.source_path,
            "profiled_at": self.profiled_at,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "duplicate_rows": self.duplicate_rows,
            "quality_score": self.quality_score,
            "executive_summary": self.executive_summary,
            "governance_findings": self.governance_findings,
            "fields": [f.to_row() for f in self.fields],
        }


def read_dataset(path: str) -> pd.DataFrame:
    """Read CSV, XLS, or XLSX into a dataframe using safe defaults."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    suffix = p.suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(p)
    if suffix in {".csv", ".txt"}:
        # Let pandas sniff common CSV variants while keeping strings stable.
        try:
            return pd.read_csv(p, dtype=str, keep_default_na=False, na_values=["", "NULL", "null", "None"])
        except UnicodeDecodeError:
            return pd.read_csv(p, dtype=str, encoding="latin-1", keep_default_na=False, na_values=["", "NULL", "null", "None"])
    raise ValueError(f"Unsupported dataset type: {suffix}. Use CSV, XLS, or XLSX.")


def _clean_name(name: Any) -> str:
    text = str(name).strip()
    return text or "Unnamed Field"


def _friendly_label(col: str) -> str:
    text = re.sub(r"[_\-]+", " ", str(col)).strip()
    words = []
    for w in text.split():
        words.append(BUSINESS_WORDS.get(w.lower(), w))
    return " ".join(words).title()


def _infer_type(series: pd.Series) -> str:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return "Unknown"
    numeric = pd.to_numeric(s.str.replace(",", "", regex=False).str.replace("$", "", regex=False), errors="coerce")
    if numeric.notna().mean() >= 0.90:
        if (numeric.dropna() % 1 == 0).mean() >= 0.95:
            return "Integer"
        return "Decimal"
    dates = pd.to_datetime(s, errors="coerce")
    if dates.notna().mean() >= 0.85:
        return "Date/Time"
    vals = {x.lower() for x in s.head(200).unique()}
    if vals and vals.issubset({"true", "false", "yes", "no", "y", "n", "0", "1"}):
        return "Boolean"
    return "Text"


def _safe_min_max(series: pd.Series, inferred_type: str) -> Tuple[str, str]:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return "", ""
    try:
        if inferred_type in {"Integer", "Decimal"}:
            numeric = pd.to_numeric(s.str.replace(",", "", regex=False).str.replace("$", "", regex=False), errors="coerce").dropna()
            if numeric.empty:
                return "", ""
            return str(numeric.min()), str(numeric.max())
        if inferred_type == "Date/Time":
            dates = pd.to_datetime(s, errors="coerce").dropna()
            if dates.empty:
                return "", ""
            return str(dates.min()), str(dates.max())
    except Exception:
        pass
    return str(s.min())[:80], str(s.max())[:80]


def _detect_pii(col: str, series: pd.Series) -> Tuple[str, str, str]:
    normalized_col = re.sub(r"[^a-zA-Z0-9]+", "_", col).strip("_")
    categories: List[str] = []
    for cat, rx in PII_NAME_PATTERNS.items():
        if rx.search(normalized_col):
            categories.append(cat)
    samples = [str(x).strip() for x in series.dropna().head(250).tolist() if str(x).strip()]
    for cat, rx in PII_VALUE_PATTERNS.items():
        if samples:
            matches = sum(1 for x in samples if rx.search(x))
            if matches / max(1, len(samples)) >= 0.15:
                categories.append(cat)
    categories = sorted(set(categories))
    if not categories:
        return "No", "", "Internal"
    if any(c in categories for c in ["SSN", "Credit Card-like", "Date of Birth"]):
        return "Yes", ", ".join(categories), "Restricted"
    return "Yes", ", ".join(categories), "Confidential"


def _description_for(col: str, inferred_type: str, pii_category: str) -> str:
    label = _friendly_label(col)
    base = f"{label} stores {inferred_type.lower()} values used to describe, filter, analyze, or join this dataset."
    if pii_category:
        base += f" Potential sensitive category: {pii_category}."
    return base


def _dq_rules_for(col: str, inferred_type: str, null_pct: float, unique_pct: float, pii_flag: str) -> List[str]:
    safe_col = str(col).replace('"', '""')
    rules = []
    if null_pct == 0:
        rules.append(f'NOT_NULL("{safe_col}")')
    elif null_pct > 30:
        rules.append(f'NULL_RATE("{safe_col}") <= {math.ceil(null_pct + 5)}')
    if unique_pct >= 95:
        rules.append(f'UNIQUENESS("{safe_col}") >= 0.95')
    if inferred_type in {"Integer", "Decimal"}:
        rules.append(f'IS_NUMERIC("{safe_col}")')
    if inferred_type == "Date/Time":
        rules.append(f'IS_DATE("{safe_col}")')
    if pii_flag == "Yes":
        rules.append(f'REQUIRES_POLICY_TAG("{safe_col}")')
    return rules


def profile_dataframe(df: pd.DataFrame, dataset_name: str = "Dataset", source_path: str = "") -> DatasetProfile:
    df = df.copy()
    df.columns = [_clean_name(c) for c in df.columns]
    row_count = int(len(df))
    duplicate_rows = int(df.duplicated().sum()) if row_count else 0
    fields: List[FieldProfile] = []
    findings: List[str] = []

    for col in df.columns:
        s = df[col]
        null_mask = s.isna() | (s.astype(str).str.strip() == "")
        null_count = int(null_mask.sum())
        null_pct = (null_count / row_count * 100.0) if row_count else 0.0
        unique_count = int(s.dropna().astype(str).nunique())
        unique_pct = (unique_count / row_count * 100.0) if row_count else 0.0
        inferred_type = _infer_type(s)
        samples = [str(x)[:80] for x in s.dropna().astype(str).str.strip().unique().tolist() if str(x).strip()][:5]
        min_v, max_v = _safe_min_max(s, inferred_type)
        non_blank = s.dropna().astype(str).str.strip()
        non_blank = non_blank[non_blank != ""]
        avg_len = float(non_blank.str.len().mean()) if not non_blank.empty else 0.0
        pii_flag, pii_category, sensitivity = _detect_pii(col, s)
        quality_notes = []
        if null_pct > 30:
            quality_notes.append("High null rate")
        if unique_pct == 100 and row_count > 1:
            quality_notes.append("Candidate key")
        if pii_flag == "Yes":
            quality_notes.append("Sensitive data review required")
            findings.append(f"{col}: potential {pii_category}")
        desc = _description_for(col, inferred_type, pii_category)
        dq_rules = _dq_rules_for(col, inferred_type, null_pct, unique_pct, pii_flag)
        fields.append(FieldProfile(
            name=col,
            inferred_type=inferred_type,
            pandas_type=str(s.dtype),
            nullable="Yes" if null_count else "No",
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            unique_pct=unique_pct,
            sample_values=samples,
            min_value=min_v,
            max_value=max_v,
            avg_length=avg_len,
            pii_flag=pii_flag,
            pii_category=pii_category,
            sensitivity=sensitivity,
            quality_notes="; ".join(quality_notes),
            description=desc,
            dq_rules=dq_rules,
        ))

    if duplicate_rows:
        findings.append(f"Dataset contains {duplicate_rows} duplicate row(s).")
    missing_desc = sum(1 for f in fields if not f.description)
    restricted = sum(1 for f in fields if f.sensitivity == "Restricted")
    confidential = sum(1 for f in fields if f.sensitivity == "Confidential")
    avg_null = sum(f.null_pct for f in fields) / max(1, len(fields))
    score = 100
    score -= min(30, int(avg_null / 2))
    score -= min(20, duplicate_rows * 2)
    score -= min(20, restricted * 5 + confidential * 2)
    score = max(0, min(100, score))
    executive_summary = (
        f"{dataset_name} contains {row_count:,} row(s) and {len(fields):,} field(s). "
        f"CatalogIQ detected {confidential + restricted} sensitive field(s), "
        f"{duplicate_rows} duplicate row(s), and assigned a readiness score of {score}/100."
    )
    return DatasetProfile(
        dataset_name=dataset_name,
        source_path=source_path,
        profiled_at=_dt.datetime.now().isoformat(timespec="seconds"),
        row_count=row_count,
        column_count=len(fields),
        duplicate_rows=duplicate_rows,
        fields=fields,
        governance_findings=findings,
        quality_score=score,
        executive_summary=executive_summary,
    )


def profile_dataset(path: str) -> Tuple[pd.DataFrame, DatasetProfile]:
    df = read_dataset(path)
    dataset_name = Path(path).stem
    return df, profile_dataframe(df, dataset_name=dataset_name, source_path=str(path))


def profile_to_catalog_df(profile: DatasetProfile) -> pd.DataFrame:
    rows = []
    for f in profile.fields:
        rows.append({
            "Field": f.name,
            "Friendly Name": _friendly_label(f.name),
            "Description": f.description,
            "Data Type": f.inferred_type,
            "Nullable": f.nullable,
            "Example": "; ".join(f.sample_values),
            "Analysis Date": profile.profiled_at[:10],
            "Policy": f.sensitivity,
            "Regex Pattern": "",
            "PII Flag": f.pii_flag,
            "PII Category": f.pii_category,
            "Null %": round(f.null_pct, 2),
            "Unique %": round(f.unique_pct, 2),
            "Quality Notes": f.quality_notes,
        })
    return pd.DataFrame(rows)


def profile_to_glossary_df(profile: DatasetProfile) -> pd.DataFrame:
    rows = []
    for f in profile.fields:
        rows.append({
            "Term Name": _friendly_label(f.name),
            "Definition": f.description,
            "Business Context": f"Used in the {profile.dataset_name} data product.",
            "Synonyms/Aliases": f.name,
            "Owner/Steward": "TBD",
            "Approval Status": "Draft",
            "Related Terms": "",
            "Data Sensitivity": f.sensitivity,
            "Source System": Path(profile.source_path).name or "TBD",
            "Last Reviewed Date": profile.profiled_at[:10],
        })
    return pd.DataFrame(rows)


def profile_to_dictionary_df(profile: DatasetProfile) -> pd.DataFrame:
    rows = []
    for f in profile.fields:
        rows.append({
            "Table Name": profile.dataset_name,
            "Column Name": f.name,
            "Data Type": f.inferred_type,
            "Length/Precision": str(round(f.avg_length, 2)) if f.inferred_type == "Text" else "",
            "Nullable": f.nullable,
            "Default Value": "",
            "Primary Key": "Yes" if f.unique_pct >= 95 and f.null_pct == 0 else "No",
            "Foreign Key": "TBD",
            "Business Term Link": _friendly_label(f.name),
            "Data Sensitivity": f.sensitivity,
            "Source System": Path(profile.source_path).name or "TBD",
            "Last Modified Date": profile.profiled_at[:10],
            "Owner/Steward": "TBD",
        })
    return pd.DataFrame(rows)


def quality_rules_sql(profile: DatasetProfile, table_name: Optional[str] = None) -> str:
    table = table_name or profile.dataset_name
    safe_table = re.sub(r"[^a-zA-Z0-9_]+", "_", table).strip("_") or "catalogiq_dataset"
    lines = [
        "-- CatalogIQ generated data quality starter rules",
        f"-- Dataset: {profile.dataset_name}",
        f"-- Generated: {profile.profiled_at}",
        "",
    ]
    for f in profile.fields:
        col = f.name.replace('"', '""')
        for rule in f.dq_rules or []:
            if rule.startswith("NOT_NULL"):
                lines.append(f'SELECT COUNT(*) AS failed_rows FROM {safe_table} WHERE "{col}" IS NULL;')
            elif rule.startswith("IS_NUMERIC"):
                lines.append(f'-- Validate numeric format for "{col}" in {safe_table}')
            elif rule.startswith("IS_DATE"):
                lines.append(f'-- Validate date format for "{col}" in {safe_table}')
            elif rule.startswith("UNIQUENESS"):
                lines.append(f'SELECT "{col}", COUNT(*) AS n FROM {safe_table} GROUP BY "{col}" HAVING COUNT(*) > 1;')
            elif rule.startswith("REQUIRES_POLICY_TAG"):
                lines.append(f'-- Governance check: "{col}" requires a sensitivity policy tag.')
    return "\n".join(lines) + "\n"


def metadata_payload_yaml(profile: DatasetProfile) -> str:
    def q(v: Any) -> str:
        return json.dumps("" if v is None else str(v))
    lines = [
        "catalogiq_metadata:",
        f"  dataset_name: {q(profile.dataset_name)}",
        f"  source_path: {q(profile.source_path)}",
        f"  profiled_at: {q(profile.profiled_at)}",
        f"  row_count: {profile.row_count}",
        f"  column_count: {profile.column_count}",
        f"  quality_score: {profile.quality_score}",
        "  fields:",
    ]
    for f in profile.fields:
        lines.extend([
            f"    - name: {q(f.name)}",
            f"      friendly_name: {q(_friendly_label(f.name))}",
            f"      data_type: {q(f.inferred_type)}",
            f"      nullable: {q(f.nullable)}",
            f"      sensitivity: {q(f.sensitivity)}",
            f"      pii_flag: {q(f.pii_flag)}",
            f"      pii_category: {q(f.pii_category)}",
            f"      description: {q(f.description)}",
        ])
    return "\n".join(lines) + "\n"


def governance_report_md(profile: DatasetProfile) -> str:
    lines = [
        f"# CatalogIQ Governance Report — {profile.dataset_name}",
        "",
        f"Generated: {profile.profiled_at}",
        "",
        "## Executive Summary",
        "",
        profile.executive_summary,
        "",
        "## Governance Findings",
        "",
    ]
    if profile.governance_findings:
        lines += [f"- {x}" for x in profile.governance_findings]
    else:
        lines.append("- No sensitive data or major governance issues detected by the starter scan.")
    lines += ["", "## Field Inventory", ""]
    for f in profile.fields:
        lines.append(f"### {f.name}")
        lines.append(f"- Type: {f.inferred_type}")
        lines.append(f"- Sensitivity: {f.sensitivity}")
        lines.append(f"- PII: {f.pii_flag} {f.pii_category}".strip())
        lines.append(f"- Null %: {round(f.null_pct, 2)}")
        lines.append(f"- Description: {f.description}")
        lines.append("")
    return "\n".join(lines)


def export_catalog_package(profile: DatasetProfile, output_dir: str) -> Path:
    root = Path(output_dir)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    package_dir = root / f"CatalogIQ_{profile.dataset_name}_{stamp}"
    package_dir.mkdir(parents=True, exist_ok=True)

    (package_dir / "catalog.json").write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
    (package_dir / "metadata_payload.yaml").write_text(metadata_payload_yaml(profile), encoding="utf-8")
    (package_dir / "quality_rules.sql").write_text(quality_rules_sql(profile), encoding="utf-8")
    (package_dir / "governance_report.md").write_text(governance_report_md(profile), encoding="utf-8")

    catalog_df = profile_to_catalog_df(profile)
    glossary_df = profile_to_glossary_df(profile)
    dictionary_df = profile_to_dictionary_df(profile)
    catalog_df.to_csv(package_dir / "catalog_fields.csv", index=False)
    glossary_df.to_csv(package_dir / "business_glossary.csv", index=False)
    dictionary_df.to_csv(package_dir / "data_dictionary.csv", index=False)

    try:
        with pd.ExcelWriter(package_dir / "catalogiq_data_product.xlsx") as writer:
            catalog_df.to_excel(writer, sheet_name="Catalog", index=False)
            glossary_df.to_excel(writer, sheet_name="Glossary", index=False)
            dictionary_df.to_excel(writer, sheet_name="Dictionary", index=False)
    except Exception:
        # CSV files are already exported; Excel is best-effort.
        pass

    return package_dir

# ============================================================
# CatalogIQ Phase 2 helpers: premium data product package
# ============================================================

def risk_level(profile: DatasetProfile) -> str:
    restricted = sum(1 for f in profile.fields if f.sensitivity == "Restricted")
    confidential = sum(1 for f in profile.fields if f.sensitivity == "Confidential")
    high_null = sum(1 for f in profile.fields if f.null_pct > 30)
    if restricted or profile.quality_score < 70:
        return "High"
    if confidential or high_null or profile.quality_score < 85:
        return "Medium"
    return "Low"


def data_product_summary_md(profile: DatasetProfile) -> str:
    sensitive = [f for f in profile.fields if f.pii_flag == "Yes"]
    keys = [f for f in profile.fields if f.unique_pct >= 95 and f.null_pct == 0]
    high_null = [f for f in profile.fields if f.null_pct > 30]
    lines = [
        f"# Data Product Summary — {profile.dataset_name}",
        "",
        "## Product Readiness",
        "",
        f"- Readiness score: {profile.quality_score}/100",
        f"- Risk level: {risk_level(profile)}",
        f"- Rows profiled: {profile.row_count:,}",
        f"- Fields profiled: {profile.column_count:,}",
        f"- Duplicate rows: {profile.duplicate_rows:,}",
        f"- Sensitive fields detected: {len(sensitive):,}",
        "",
        "## Executive Narrative",
        "",
        profile.executive_summary,
        "",
        "CatalogIQ recommends reviewing stewardship, sensitivity labels, and quality rules before this dataset is promoted as a governed data product.",
        "",
        "## Candidate Key Fields",
        "",
    ]
    if keys:
        lines += [f"- {f.name} ({f.inferred_type}, unique {round(f.unique_pct, 2)}%)" for f in keys]
    else:
        lines.append("- No strong key candidates detected by the starter profiler.")
    lines += ["", "## Sensitive Fields", ""]
    if sensitive:
        lines += [f"- {f.name}: {f.pii_category} ({f.sensitivity})" for f in sensitive]
    else:
        lines.append("- No sensitive fields detected by starter scan.")
    lines += ["", "## Quality Risks", ""]
    if profile.duplicate_rows:
        lines.append(f"- Dataset contains {profile.duplicate_rows:,} duplicate row(s).")
    if high_null:
        lines += [f"- {f.name}: high null rate ({round(f.null_pct, 2)}%)." for f in high_null]
    if not profile.duplicate_rows and not high_null:
        lines.append("- No major starter quality risks detected.")
    lines += [
        "",
        "## Recommended Next Actions",
        "",
        "1. Assign a business owner and technical steward.",
        "2. Confirm generated field descriptions with a domain expert.",
        "3. Approve sensitivity labels and policy tags.",
        "4. Implement the generated data quality checks in the target platform.",
        "5. Publish the final catalog package to the enterprise metadata workspace.",
        "",
    ]
    return "\n".join(lines)


def collibra_atlan_payload_json(profile: DatasetProfile) -> str:
    """Generic metadata payload shaped for future Collibra/Atlan-style publishing."""
    payload = {
        "asset_type": "Data Product",
        "name": profile.dataset_name,
        "source": profile.source_path,
        "readiness_score": profile.quality_score,
        "risk_level": risk_level(profile),
        "description": profile.executive_summary,
        "tags": sorted(set([f.sensitivity for f in profile.fields] + ["CatalogIQ", "AI-Generated", "Draft"])),
        "owners": {"business_owner": "TBD", "technical_steward": "TBD"},
        "schema": [
            {
                "name": f.name,
                "business_name": _friendly_label(f.name),
                "description": f.description,
                "data_type": f.inferred_type,
                "nullable": f.nullable,
                "sensitivity": f.sensitivity,
                "pii_flag": f.pii_flag,
                "pii_category": f.pii_category,
                "quality_notes": f.quality_notes,
                "dq_rules": f.dq_rules or [],
            }
            for f in profile.fields
        ],
        "governance_findings": profile.governance_findings,
    }
    return json.dumps(payload, indent=2)


def package_manifest(profile: DatasetProfile, files: List[str]) -> str:
    manifest = {
        "package_name": f"CatalogIQ_{profile.dataset_name}",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "dataset_name": profile.dataset_name,
        "source_path": profile.source_path,
        "readiness_score": profile.quality_score,
        "risk_level": risk_level(profile),
        "files": files,
        "recommended_workflow": [
            "Review catalogiq_data_product.xlsx",
            "Review data_product_summary.md with business owner",
            "Approve sensitivity and policy tags",
            "Implement quality_rules.sql or convert to dbt/Snowflake rules",
            "Use catalog_publish_payload.json for future enterprise catalog publishing",
        ],
    }
    return json.dumps(manifest, indent=2)


def package_index_html(profile: DatasetProfile, file_names: List[str]) -> str:
    sensitive = sum(1 for f in profile.fields if f.pii_flag == "Yes")
    findings = "".join(f"<li>{x}</li>" for x in (profile.governance_findings or ["No major governance findings detected."]))
    files = "".join(f"<li><code>{x}</code></li>" for x in file_names)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<title>CatalogIQ Data Product — {profile.dataset_name}</title>
<style>
body {{ margin:0; font-family: Segoe UI, Arial, sans-serif; background:#f8fafc; color:#0f172a; }}
.hero {{ background:#0f172a; color:white; padding:28px 34px; }}
.hero h1 {{ margin:0 0 8px; font-size:30px; }}
.hero p {{ color:#cbd5e1; margin:0; }}
.wrap {{ padding:24px 34px; }}
.cards {{ display:grid; grid-template-columns: repeat(4, minmax(150px,1fr)); gap:14px; margin-bottom:22px; }}
.card {{ background:white; border:1px solid #e2e8f0; border-radius:16px; padding:18px; box-shadow:0 8px 24px rgba(15,23,42,.06); }}
.k {{ color:#64748b; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
.v {{ font-size:28px; font-weight:800; margin-top:6px; }}
section {{ background:white; border:1px solid #e2e8f0; border-radius:16px; padding:20px; margin:16px 0; }}
code {{ background:#f1f5f9; padding:2px 6px; border-radius:6px; }}
</style>
</head>
<body>
<div class=\"hero\"><h1>CatalogIQ Data Product Package</h1><p>{profile.executive_summary}</p></div>
<div class=\"wrap\">
<div class=\"cards\">
<div class=\"card\"><div class=\"k\">Readiness</div><div class=\"v\">{profile.quality_score}/100</div></div>
<div class=\"card\"><div class=\"k\">Risk</div><div class=\"v\">{risk_level(profile)}</div></div>
<div class=\"card\"><div class=\"k\">Fields</div><div class=\"v\">{profile.column_count}</div></div>
<div class=\"card\"><div class=\"k\">Sensitive</div><div class=\"v\">{sensitive}</div></div>
</div>
<section><h2>Governance Findings</h2><ul>{findings}</ul></section>
<section><h2>Package Files</h2><ul>{files}</ul></section>
<section><h2>Recommended Workflow</h2><ol><li>Open <code>catalogiq_data_product.xlsx</code>.</li><li>Review the generated descriptions, glossary, and data dictionary.</li><li>Approve sensitivity labels.</li><li>Implement quality rules.</li><li>Use the publish payload for future Collibra/Atlan-style integration.</li></ol></section>
</div>
</body>
</html>"""


def publish_to_local_workspace(profile: DatasetProfile, workspace_dir: str = "catalogiq_workspace") -> Path:
    root = Path(workspace_dir)
    root.mkdir(parents=True, exist_ok=True)
    assets_dir = root / "assets"
    assets_dir.mkdir(exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]+", "_", profile.dataset_name).strip("_") or "dataset"
    asset_path = assets_dir / f"{safe_name}.json"
    asset_path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    index_path = root / "workspace_index.json"
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            index = {"assets": []}
    else:
        index = {"assets": []}
    index["assets"] = [a for a in index.get("assets", []) if a.get("dataset_name") != profile.dataset_name]
    index["assets"].append({
        "dataset_name": profile.dataset_name,
        "asset_file": str(asset_path),
        "source_path": profile.source_path,
        "published_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "readiness_score": profile.quality_score,
        "risk_level": risk_level(profile),
        "field_count": profile.column_count,
        "row_count": profile.row_count,
    })
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return asset_path


# Keep the original export function name, but upgrade the package contents.
_export_catalog_package_v1 = export_catalog_package

def export_catalog_package(profile: DatasetProfile, output_dir: str) -> Path:  # type: ignore[override]
    package_dir = _export_catalog_package_v1(profile, output_dir)
    extra_files = []
    extras = {
        "data_product_summary.md": data_product_summary_md(profile),
        "catalog_publish_payload.json": collibra_atlan_payload_json(profile),
    }
    for name, content in extras.items():
        (package_dir / name).write_text(content, encoding="utf-8")
        extra_files.append(name)

    file_names = sorted([p.name for p in package_dir.iterdir() if p.is_file()])
    (package_dir / "package_manifest.json").write_text(package_manifest(profile, file_names), encoding="utf-8")
    file_names = sorted([p.name for p in package_dir.iterdir() if p.is_file()])
    (package_dir / "index.html").write_text(package_index_html(profile, file_names), encoding="utf-8")
    return package_dir

# ============================================================
# CatalogIQ Phase 3 helpers: workspace explorer and agent actions
# ============================================================

def dataset_profile_from_dict(data: Dict[str, Any]) -> DatasetProfile:
    """Rehydrate a DatasetProfile from catalog.json/workspace asset JSON."""
    fields: List[FieldProfile] = []
    for row in data.get("fields", []):
        dq_raw = row.get("dq_rules", [])
        if isinstance(dq_raw, str):
            dq_rules = [x for x in dq_raw.splitlines() if x.strip()]
        else:
            dq_rules = list(dq_raw or [])
        sample_raw = row.get("sample_values", [])
        if isinstance(sample_raw, str):
            samples = [x.strip() for x in sample_raw.split(";") if x.strip()]
        else:
            samples = [str(x) for x in (sample_raw or [])]
        fields.append(FieldProfile(
            name=str(row.get("name") or row.get("Field") or ""),
            inferred_type=str(row.get("inferred_type") or row.get("Data Type") or "Unknown"),
            pandas_type=str(row.get("pandas_type") or ""),
            nullable=str(row.get("nullable") or row.get("Nullable") or ""),
            null_count=int(float(row.get("null_count") or 0)),
            null_pct=float(row.get("null_pct") or row.get("Null %") or 0),
            unique_count=int(float(row.get("unique_count") or 0)),
            unique_pct=float(row.get("unique_pct") or row.get("Unique %") or 0),
            sample_values=samples,
            min_value=str(row.get("min_value") or ""),
            max_value=str(row.get("max_value") or ""),
            avg_length=float(row.get("avg_length") or 0),
            pii_flag=str(row.get("pii_flag") or row.get("PII Flag") or "No"),
            pii_category=str(row.get("pii_category") or row.get("PII Category") or ""),
            sensitivity=str(row.get("sensitivity") or row.get("Policy") or "Internal"),
            quality_notes=str(row.get("quality_notes") or row.get("Quality Notes") or ""),
            description=str(row.get("description") or row.get("Description") or ""),
            dq_rules=dq_rules,
        ))
    return DatasetProfile(
        dataset_name=str(data.get("dataset_name") or "Dataset"),
        source_path=str(data.get("source_path") or ""),
        profiled_at=str(data.get("profiled_at") or _dt.datetime.now().isoformat(timespec="seconds")),
        row_count=int(float(data.get("row_count") or 0)),
        column_count=int(float(data.get("column_count") or len(fields))),
        duplicate_rows=int(float(data.get("duplicate_rows") or 0)),
        fields=fields,
        governance_findings=list(data.get("governance_findings") or []),
        quality_score=int(float(data.get("quality_score") or 0)),
        executive_summary=str(data.get("executive_summary") or ""),
    )


def load_workspace_index(workspace_dir: str = "catalogiq_workspace") -> Dict[str, Any]:
    index_path = Path(workspace_dir) / "workspace_index.json"
    if not index_path.exists():
        return {"assets": []}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {"assets": []}


def load_workspace_asset(asset_file: str) -> DatasetProfile:
    data = json.loads(Path(asset_file).read_text(encoding="utf-8"))
    return dataset_profile_from_dict(data)


def workspace_assets_df(workspace_dir: str = "catalogiq_workspace") -> pd.DataFrame:
    assets = load_workspace_index(workspace_dir).get("assets", [])
    if not assets:
        return pd.DataFrame(columns=["Dataset", "Risk", "Readiness", "Fields", "Rows", "Published", "Asset File"])
    rows = []
    for a in assets:
        rows.append({
            "Dataset": a.get("dataset_name", ""),
            "Risk": a.get("risk_level", ""),
            "Readiness": a.get("readiness_score", ""),
            "Fields": a.get("field_count", ""),
            "Rows": a.get("row_count", ""),
            "Published": a.get("published_at", ""),
            "Asset File": a.get("asset_file", ""),
        })
    return pd.DataFrame(rows)


def profile_scorecard_df(profile: DatasetProfile) -> pd.DataFrame:
    sensitive = sum(1 for f in profile.fields if f.pii_flag == "Yes")
    restricted = sum(1 for f in profile.fields if f.sensitivity == "Restricted")
    high_null = sum(1 for f in profile.fields if f.null_pct > 30)
    keys = sum(1 for f in profile.fields if f.unique_pct >= 95 and f.null_pct == 0)
    descriptions = sum(1 for f in profile.fields if f.description)
    return pd.DataFrame([
        {"Metric": "Readiness Score", "Value": f"{profile.quality_score}/100", "Interpretation": "Overall starter readiness based on quality, duplicates, and sensitivity."},
        {"Metric": "Risk Level", "Value": risk_level(profile), "Interpretation": "Governance risk based on PII, restricted data, and quality concerns."},
        {"Metric": "Sensitive Fields", "Value": sensitive, "Interpretation": "Fields requiring policy/stewardship review."},
        {"Metric": "Restricted Fields", "Value": restricted, "Interpretation": "Highest sensitivity fields, such as SSN, DOB, or card-like values."},
        {"Metric": "High Null Fields", "Value": high_null, "Interpretation": "Fields with more than 30% missing values."},
        {"Metric": "Candidate Keys", "Value": keys, "Interpretation": "Fields with high uniqueness and no nulls."},
        {"Metric": "Documentation Coverage", "Value": f"{descriptions}/{profile.column_count}", "Interpretation": "Fields with generated starter descriptions."},
    ])


def agent_recommendations(profile: DatasetProfile) -> List[str]:
    recs: List[str] = []
    sensitive = [f for f in profile.fields if f.pii_flag == "Yes"]
    restricted = [f for f in profile.fields if f.sensitivity == "Restricted"]
    high_null = [f for f in profile.fields if f.null_pct > 30]
    keys = [f for f in profile.fields if f.unique_pct >= 95 and f.null_pct == 0]
    if restricted:
        recs.append("Approve Restricted policy tags for: " + ", ".join(f.name for f in restricted[:8]))
    if sensitive:
        recs.append("Assign a data steward to validate sensitive fields: " + ", ".join(f.name for f in sensitive[:8]))
    if high_null:
        recs.append("Review high-null fields before publishing: " + ", ".join(f.name for f in high_null[:8]))
    if keys:
        recs.append("Confirm candidate key fields: " + ", ".join(f.name for f in keys[:8]))
    if profile.duplicate_rows:
        recs.append(f"Investigate {profile.duplicate_rows:,} duplicate row(s) and decide whether deduplication is required.")
    recs.append("Review generated business glossary terms with the business owner.")
    recs.append("Implement generated quality rules in Snowflake/dbt/SQL Server after reviewing syntax for the target platform.")
    recs.append("Use catalog_publish_payload.json as the starter payload for future Collibra/Atlan-style publishing.")
    return recs


def answer_agent_question(profile: DatasetProfile, question: str) -> str:
    q = (question or "").strip().lower()
    sensitive = [f for f in profile.fields if f.pii_flag == "Yes"]
    restricted = [f for f in profile.fields if f.sensitivity == "Restricted"]
    high_null = [f for f in profile.fields if f.null_pct > 30]
    keys = [f for f in profile.fields if f.unique_pct >= 95 and f.null_pct == 0]
    if not q:
        return "Ask something like: find sensitive fields, explain risk, suggest DQ rules, summarize dataset, or show candidate keys."
    if any(w in q for w in ["sensitive", "pii", "restricted", "privacy"]):
        if not sensitive:
            return "No sensitive fields were detected by the starter scan. A human steward should still verify the result."
        return "Sensitive fields detected:\n" + "\n".join(f"- {f.name}: {f.pii_category} ({f.sensitivity})" for f in sensitive)
    if any(w in q for w in ["risk", "governance", "finding"]):
        findings = profile.governance_findings or ["No major governance findings detected by the starter scan."]
        return f"Risk level: {risk_level(profile)}\nReadiness: {profile.quality_score}/100\n\nFindings:\n" + "\n".join(f"- {x}" for x in findings)
    if any(w in q for w in ["quality", "dq", "rule", "rules"]):
        lines = []
        for f in profile.fields:
            for rule in f.dq_rules or []:
                lines.append(f"- {f.name}: {rule}")
        return "Suggested quality rules:\n" + ("\n".join(lines) if lines else "No starter DQ rules were generated.")
    if any(w in q for w in ["key", "unique", "primary"]):
        return "Candidate key fields:\n" + ("\n".join(f"- {f.name}: unique {round(f.unique_pct, 2)}%, null {round(f.null_pct, 2)}%" for f in keys) if keys else "No strong candidate keys detected.")
    if any(w in q for w in ["null", "missing", "blank"]):
        return "High-null fields:\n" + ("\n".join(f"- {f.name}: {round(f.null_pct, 2)}% null" for f in high_null) if high_null else "No fields exceed the 30% high-null threshold.")
    if any(w in q for w in ["summary", "summarize", "explain", "overview"]):
        return profile.executive_summary + "\n\nRecommended next actions:\n" + "\n".join(f"- {x}" for x in agent_recommendations(profile)[:5])
    return "CatalogIQ Agent response:\n" + profile.executive_summary + "\n\nTop recommendations:\n" + "\n".join(f"- {x}" for x in agent_recommendations(profile)[:5])
