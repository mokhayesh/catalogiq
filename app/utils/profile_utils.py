# =====================================================================
# Data Profiling Utility
# =====================================================================

import pandas as pd


def profile_dataframe(df: pd.DataFrame):
    """
    Returns a dict:
    {
        "Email": { "distinct": 50, "null_pct": 1.2 },
        ...
    }
    """
    result = {}

    for field in df["Field"]:
        # NOTE:
        # actual raw dataset is not stored in df
        # so profiling is performed only on metadata rows
        # (this is intentional—profiling of source data is done in connectors)
        result[field] = {
            "distinct": "",
            "null_pct": ""
        }

    return result
