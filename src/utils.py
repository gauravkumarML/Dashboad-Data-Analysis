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

def revenue_from_sales(df_sales: pd.DataFrame) -> pd.Series:
    return (df_sales["Qty"] * df_sales["UnitPrice"] * (1 - df_sales["Discount"]))

def cost_from_sales(df_sales: pd.DataFrame) -> pd.Series:
    return (df_sales["Qty"] * df_sales["Cost"])

def ensure_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    if not np.issubdtype(df[col].dtype, np.datetime64):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df[col]

def cohort_retention(subs: pd.DataFrame, date_index: pd.DatetimeIndex) -> pd.DataFrame:
    """Return a retention matrix: rows=cohort (start of month), cols=months since start, values=retention%"""
    s = subs.copy()
    s["StartMonth"] = pd.to_datetime(s["StartDate"]).values.astype('datetime64[M]')
    s["EndMonth"] = pd.to_datetime(s["EndDate"]).values.astype('datetime64[M]')
    s["EndMonth"] = s["EndMonth"].fillna(pd.NaT)
    cohorts = s["StartMonth"].dropna().sort_values().unique()

    # Build month buckets across the overall range
    min_m = pd.Timestamp(min(date_index)).to_period("M").to_timestamp()
    max_m = pd.Timestamp(max(date_index)).to_period("M").to_timestamp()
    months = pd.period_range(min_m, max_m, freq="M").to_timestamp()

    data = {}
    for cohort in cohorts:
        cohort_mask = s["StartMonth"] == cohort
        cohort_size = int(cohort_mask.sum())
        if cohort_size == 0:
            continue
        row = []
        for m in months:
            # active if started <= m and (no end or end >= m)
            active = s.loc[cohort_mask & (s["StartMonth"] <= m) & (s["EndMonth"].isna() | (s["EndMonth"] >= m))]
            retained = len(active)
            row.append(retained / cohort_size if cohort_size > 0 else np.nan)
        data[cohort] = row
    ret = pd.DataFrame(data, index=months).T
    # Convert columns to "M+0, M+1, ..." offset labels
    if ret.shape[1] > 0:
        base = ret.columns[0]
        ret.columns = [f"M+{i}" for i in range(len(ret.columns))]
    return ret

def yoy(current: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Compute YoY growth for a timeseries indexed by datetime (monthly or daily)."""
    curr = current.copy()
    curr.index = pd.to_datetime(index)
    prev = curr.shift(12)  # assumes monthly; for daily we could shift 365
    return (curr - prev) / prev

