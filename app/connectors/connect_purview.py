# =====================================================================
# Purview Connector — Microsoft Purview (Data Map Import)
# =====================================================================

import wx
import pandas as pd
import requests

CATALOG_COLS = [
    "Field", "Friendly Name", "Description", "Data Type", "Nullable",
    "Example", "Analysis Date", "Attestation", "Policy", "Regex Pattern",
    "PII Type", "Profile: Distinct", "Profile: Null %"
]


class PurviewConnector:

    def __init__(self):
        pass

    # -----------------------------------------------------------------
    def _prompt_credentials(self):
        dlg = wx.TextEntryDialog(
            None,
            "Enter Purview Account Name:\n(e.g. mypurview)",
            "Purview Account"
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None, None
        account = dlg.GetValue()
        dlg.Destroy()

        dlg2 = wx.TextEntryDialog(
            None,
            "Enter Azure Access Token (Bearer):",
            "Purview Access Token"
        )
        if dlg2.ShowModal() != wx.ID_OK:
            dlg2.Destroy()
            return None, None
        token = dlg2.GetValue()
        dlg2.Destroy()

        return account, token

    # -----------------------------------------------------------------
    def import_assets(self):
        account, token = self._prompt_credentials()
        if not account or not token:
            wx.MessageBox("Purview import canceled.")
            return None

        headers = {"Authorization": f"Bearer {token}"}

        try:
            # Search query (Purview Data Map)
            url = f"https://{account}.purview.azure.com/catalog/api/search/query?api-version=2022-03-01-preview"
            payload = {
                "keywords": "*",
                "limit": 20
            }

            r = requests.post(url, headers=headers, json=payload, timeout=30)
            r.raise_for_status()

            results = r.json().get("value", [])
            if not results:
                wx.MessageBox("No assets found in Purview.")
                return None

            # For simplicity: use first asset with schema
            asset = None
            for a in results:
                if "attributes" in a and "fields" in a["attributes"]:
                    asset = a
                    break

            if not asset:
                wx.MessageBox("No schema assets found in Purview.")
                return None

            fields = asset["attributes"]["fields"]

            rows = []
            for f in fields:
                pii = self._extract_pii_from_classifications(f)

                rows.append({
                    "Field": f.get("name", ""),
                    "Friendly Name": f.get("name", ""),
                    "Description": f.get("description", ""),
                    "Data Type": f.get("dataType", ""),
                    "Nullable": "Yes" if f.get("isNullable", True) else "No",
                    "Example": "",
                    "Analysis Date": "",
                    "Attestation": "Imported from Purview",
                    "Policy": pii.get("policy", ""),
                    "Regex Pattern": pii.get("regex", ""),
                    "PII Type": pii.get("type", ""),
                    "Profile: Distinct": "",
                    "Profile: Null %": ""
                })

            return pd.DataFrame(rows, columns=CATALOG_COLS)

        except Exception as e:
            wx.MessageBox(f"Purview import failed:\n{e}")
            return None


    # -----------------------------------------------------------------
    def _extract_pii_from_classifications(self, field):
        """Map Purview Classification → CatalogIQ PII fields."""

        classes = field.get("classifications", [])
        if not classes:
            return {}

        cls = classes[0].get("typeName", "").lower()

        if "pii" in cls:
            return {
                "type": "PII",
                "regex": "",
                "policy": "PII Protected"
            }
        if "confidential" in cls:
            return {
                "type": "Confidential",
                "regex": "",
                "policy": "Confidential Information"
            }

        return {}
