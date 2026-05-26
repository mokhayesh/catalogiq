import os
import re
import json
import datetime
import requests


# ============================================================
# AI Engine for CatalogIQ
# Centralized logic for:
# - Prompt building
# - Calling OpenAI
# - Parsing results
#
# Keeps main_window.py clean and stable.
# ============================================================


class AIAssistantEngine:

    def __init__(self, model="gpt-4o-mini"):
        self.model = model
        self.url = "https://api.openai.com/v1/chat/completions"

        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY environment variable is missing.")

    # ============================================================
    # Build prompt
    # ============================================================
    def build_prompt(self, field_name: str, target_column: str, context: str):
        """
        Create a deterministic structured prompt
        to reduce hallucinations and enforce JSON output.
        """

        return f"""
You are a senior enterprise data governance expert.

Return ONLY valid JSON:

{{
    "value": "<answer>"
}}

ABSOLUTELY NO:
- Markdown
- Code blocks
- Explanations
- Extra text
- Commentary

FIELD: {field_name}
COLUMN TO GENERATE: {target_column}

CONTEXT:
{context}

RULES:
- Friendly Name → title case, short
- Description → <25 words, accurate definition
- Data Type → one of: string, integer, number, boolean, date, datetime
- Nullable → Yes or No
- Example → short realistic sample
- Regex Pattern → valid regex only (NO English)
- Policy → small governance rule
- Analysis Date → YYYY-MM-DD (today)
"""

    # ============================================================
    # Call OpenAI (safe)
    # ============================================================
    def ask_model(self, prompt: str):
        """
        Calls the OpenAI API safely.
        Avoids raising exceptions on failure.
        """

        try:
            r = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=45,
                verify=False
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

        except Exception:
            return ""

    # ============================================================
    # Parse {"value": "..."} from AI output
    # Robust and forgiving.
    # ============================================================
    def extract_value(self, raw: str) -> str:
        if not raw:
            return ""

        # Strip markdown or fence blocks if any
        cleaned = raw.replace("```json", "").replace("```", "").strip()

        # Extract JSON
        match = re.search(r'"value"\s*:\s*"([^"]*)"', cleaned)
        if match:
            return match.group(1).strip()

        # Fallback: return text
        return cleaned.strip()

    # ============================================================
    # Column specific cleanup rules
    # ============================================================
    def cleanup(self, column: str, value: str):
        if not value:
            return ""

        col = column.lower().strip()

        if col == "friendly name":
            return value.title()

        if col == "description":
            # Clip to safe length
            return value[:180]

        if col == "nullable":
            return "Yes" if value.lower().startswith("y") else "No"

        if col == "analysis date":
            try:
                datetime.datetime.fromisoformat(value)
            except:
                return datetime.date.today().isoformat()
            return value

        if col == "regex pattern":
            # If the model returned English words → reject
            if not any(x in value for x in "^$[]()+*?|."):
                return ".*"  # safe fallback regex

            return value

        return value

    # ============================================================
    # Build structured context from a DataFrame row
    # ============================================================
    def build_context(self, row):
        ctx = ""
        for col, val in row.items():
            if str(val).strip():
                ctx += f"- {col}: {val}\n"
        return ctx.strip()
