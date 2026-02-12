import pandas as pd

def revenue_from_sales(df_sales: pd.DataFrame) -> pd.Series:
    """Calculates revenue per line item."""
    return (df_sales["Qty"] * df_sales["UnitPrice"] * (1 - df_sales["Discount"]))

def cost_from_sales(df_sales: pd.DataFrame) -> pd.Series:
    """Calculates cost per line item."""
    return (df_sales["Qty"] * df_sales["Cost"])
