import os
import json
import csv
import yaml


# =====================================================================
# CONFIGURATION — Knowledge folder
# =====================================================================

def _knowledge_folder():
    """
    Returns the absolute path of the knowledge folder.
    If not present, it is created.
    """
    base = os.path.join(os.path.dirname(__file__), "knowledge_store")
    os.makedirs(base, exist_ok=True)
    return base


# =====================================================================
# LIST KNOWLEDGE FILES
# =====================================================================

def list_knowledge_files():
    """
    Returns the FULL PATH of every knowledge file.
    Accepts:
        *.txt, *.md, *.csv, *.json, *.yaml, *.yml
    """
    folder = _knowledge_folder()
    allowed = (".txt", ".md", ".csv", ".json", ".yaml", ".yml")

    return [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(allowed)
    ]


# =====================================================================
# LOAD KNOWLEDGE FILE (Convert to TEXT)
# =====================================================================

def load_knowledge_file(path):
    """
    Reads a file and returns its textual form.
    Supports:
      - TXT, MD
      - JSON (pretty string)
      - YAML
      - CSV (joined rows)
    """

    if not os.path.exists(path):
        return f"[File not found: {path}]"

    ext = os.path.splitext(path)[1].lower()

    # --------------------------------------------------------------
    # Text files
    # --------------------------------------------------------------
    if ext in (".txt", ".md"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except:
            try:
                with open(path, "r", encoding="latin1") as f:
                    return f.read()
            except Exception as e:
                return f"[Unable to read text file: {e}]"

    # --------------------------------------------------------------
    # JSON
    # --------------------------------------------------------------
    if ext == ".json":
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return json.dumps(data, indent=2)
        except Exception as e:
            return f"[Invalid JSON: {e}]"

    # --------------------------------------------------------------
    # YAML / YML
    # --------------------------------------------------------------
    if ext in (".yaml", ".yml"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return yaml.dump(data, sort_keys=False)
        except Exception as e:
            return f"[Invalid YAML: {e}]"

    # --------------------------------------------------------------
    # CSV
    # --------------------------------------------------------------
    if ext == ".csv":
        try:
            rows = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append(", ".join(row))
            return "\n".join(rows)
        except Exception as e:
            return f"[Invalid CSV: {e}]"

    return "[Unsupported file format]"
