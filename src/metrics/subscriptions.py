import pandas as pd
import numpy as np

def cohort_retention(subs: pd.DataFrame, date_index: pd.DatetimeIndex) -> pd.DataFrame:
    """
    Return a retention matrix: 
    rows = cohort (start of month)
    cols = months since start (M+0, M+1, ...)
    values = retention %
    """
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
            # This logic assumes 'm' is the beginning of the month
            active = s.loc[cohort_mask & (s["StartMonth"] <= m) & (s["EndMonth"].isna() | (s["EndMonth"] >= m))]
            retained = len(active)
            row.append(retained / cohort_size if cohort_size > 0 else np.nan)
        data[cohort] = row
        
    ret = pd.DataFrame(data, index=months).T
    
    # Convert columns to "M+0, M+1, ..." offset labels
    if ret.shape[1] > 0:
        ret.columns = [f"M+{i}" for i in range(len(ret.columns))]
    return ret
