# =====================================================================
# Fabric Connector — Microsoft Fabric (Lakehouse + Warehouse)
# =====================================================================

import wx
import pandas as pd
import requests

CATALOG_COLS = [
    "Field", "Friendly Name", "Description", "Data Type", "Nullable",
    "Example", "Analysis Date", "Attestation", "Policy", "Regex Pattern",
    "PII Type", "Profile: Distinct", "Profile: Null %"
]


class FabricConnector:

    def __init__(self):
        pass

    # -----------------------------------------------------------------
    def _prompt_credentials(self):
        dlg = wx.TextEntryDialog(
            None,
            "Enter Fabric Workspace URL:\n(e.g. https://api.fabric.microsoft.com/v1/workspaces/xxxxx)",
            "Fabric Workspace URL"
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None, None
        url = dlg.GetValue()
        dlg.Destroy()

        dlg2 = wx.TextEntryDialog(
            None,
            "Enter Fabric API Bearer Token:",
            "Fabric Token"
        )
        if dlg2.ShowModal() != wx.ID_OK:
            dlg2.Destroy()
            return None, None
        token = dlg2.GetValue()
        dlg2.Destroy()

        return url, token

    # -----------------------------------------------------------------
    def import_schema(self):
        """Main entry for schema import."""
        url, token = self._prompt_credentials()
        if not url or not token:
            wx.MessageBox("Fabric connection canceled.")
            return None

        try:
            headers = {"Authorization": f"Bearer {token}"}

            # Get list of items in workspace
            r = requests.get(f"{url}/items", headers=headers, timeout=30)
            r.raise_for_status()
            items = r.json().get("value", [])

            # Filter only Lakehouses or Warehouses
            tables = []
            for item in items:
                if item.get("type") in ("Warehouse", "Lakehouse"):
                    tables.append(item)

            if not tables:
                wx.MessageBox("No Lakehouse or Warehouse found in workspace.")
                return None

            # For demo: use the first item
            item = tables[0]
            item_id = item["id"]

            # Get schema (OneLake API)
            schema_url = f"{url}/items/{item_id}/schema"
            s = requests.get(schema_url, headers=headers, timeout=30)
            s.raise_for_status()

            fields = s.json().get("fields", [])

            rows = []
            for f in fields:
                rows.append({
                    "Field": f.get("name", ""),
                    "Friendly Name": "",
                    "Description": f.get("description", ""),
                    "Data Type": f.get("type", ""),
                    "Nullable": "Yes" if f.get("isNullable", True) else "No",
                    "Example": "",
                    "Analysis Date": "",
                    "Attestation": "Imported from Fabric",
                    "Policy": "",
                    "Regex Pattern": "",
                    "PII Type": "",
                    "Profile: Distinct": "",
                    "Profile: Null %": ""
                })

            return pd.DataFrame(rows, columns=CATALOG_COLS)

        except Exception as e:
            wx.MessageBox(f"Fabric import failed:\n{e}")
            return None
