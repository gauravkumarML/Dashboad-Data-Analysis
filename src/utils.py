import pandas as pd
import numpy as np

DATE_FMT = "%Y-%m-%d"

def typed_read_csv(path: str, **kwargs) -> pd.DataFrame:
    """Read csv with reasonable defaults for speed and memory."""
    return pd.read_csv(path, low_memory=False, **kwargs)

def add_datekey_month(df: pd.DataFrame, date_col: str, target_col: str = "DateKeyMonth") -> pd.DataFrame:
    d = pd.to_datetime(df[date_col], errors="coerce")
    df[target_col] = d.dt.year * 10000 + d.dt.month * 100 + 1
    return df

def ensure_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    if not np.issubdtype(df[col].dtype, np.datetime64):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df[col]

def yoy(current: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Computes Year-over-Year growth for a provided timeseries."""
    curr = current.copy()
    curr.index = pd.to_datetime(index)
    prev = curr.shift(12)  # Comparing against the same month in the previous year
    return (curr - prev) / prev
