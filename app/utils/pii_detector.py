# =====================================================================
# PII Detector Utility
# =====================================================================

import re

# Predefined PII signatures
PII_PATTERNS = [
    {
        "type": "Email",
        "match": r"email|e-mail",
        "regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
        "policy": "Must be a valid email address"
    },
    {
        "type": "Phone Number",
        "match": r"phone|mobile|cell",
        "regex": r"^\+?\d[\d \-]{7,}$",
        "policy": "Must be a valid phone number"
    },
    {
        "type": "Person Name",
        "match": r"name|first|last|middle",
        "regex": r"^[A-Za-z][A-Za-z\-\s']+$",
        "policy": "Must be a valid personal name"
    },
    {
        "type": "Address",
        "match": r"address|street|road|rd|apt|unit",
        "regex": r"^[0-9A-Za-z #,\.\-]+$",
        "policy": "Must be a valid street address"
    },
    {
        "type": "SSN",
        "match": r"ssn|social",
        "regex": r"^\d{3}\-\d{2}\-\d{4}$",
        "policy": "U.S. SSN format required"
    },
    {
        "type": "Credit Card",
        "match": r"card|cc|credit",
        "regex": r"^[0-9]{13,19}$",
        "policy": "Valid credit card number required"
    },
    {
        "type": "Bank Account",
        "match": r"account|routing|aba",
        "regex": r"^\d{6,17}$",
        "policy": "Valid bank account format required"
    },
    {
        "type": "Date of Birth",
        "match": r"birth|dob|date",
        "regex": r"^\d{4}\-\d{2}\-\d{2}$",
        "policy": "YYYY-MM-DD required"
    },
    {
        "type": "IP Address",
        "match": r"ip|ipv4|ipv6",
        "regex": r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
        "policy": "Valid IP format"
    }
]


def detect_pii_for_field(field_name: str):
    """Return PII metadata if field indicates sensitive information."""
    field_lower = field_name.lower()

    for item in PII_PATTERNS:
        if re.search(item["match"], field_lower):
            return {
                "type": item["type"],
                "regex": item["regex"],
                "policy": item["policy"]
            }

    return None
