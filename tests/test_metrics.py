import pytest
import pandas as pd
import numpy as np
from src.metrics import revenue_from_sales, cost_from_sales, cohort_retention

def test_revenue_from_sales():
    data = {
        "Qty": [10, 5],
        "UnitPrice": [100.0, 50.0],
        "Discount": [0.1, 0.0]
    }
    df = pd.DataFrame(data)
    expected = pd.Series([900.0, 250.0])
    result = revenue_from_sales(df)
    pd.testing.assert_series_equal(result, expected, check_names=False)

def test_cost_from_sales():
    data = {
        "Qty": [10, 5],
        "Cost": [60.0, 30.0]
    }
    df = pd.DataFrame(data)
    expected = pd.Series([600.0, 150.0])
    result = cost_from_sales(df)
    pd.testing.assert_series_equal(result, expected, check_names=False)

def test_cohort_retention_structure():
    # Mock subscription data
    data = {
        "CustomerID": [1, 2, 3],
        "StartDate": ["2024-01-01", "2024-01-15", "2024-02-01"],
        "EndDate": [None, "2024-02-01", None] # Customer 2 churns after 1 month (Feb 1st)
    }
    df = pd.DataFrame(data)
    # Using a 3-month range
    date_index = pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"])
    
    retention = cohort_retention(df, date_index)
    
    # Check shape: 2 cohorts (Jan, Feb based on StartDate)
    assert retention.shape[0] == 2
    
    # Jan Cohort (IDs 1 & 2):
    # M+0 (Jan): Both active -> 1.0
    # M+1 (Feb): Both active (Cust 2 ends Feb 1st) -> 1.0
    # M+2 (Mar): Only Cust 1 active -> 0.5
    assert retention.loc["2024-01-01", "M+0"] == 1.0
    assert retention.loc["2024-01-01", "M+1"] == 1.0
    assert retention.loc["2024-01-01", "M+2"] == 0.5

def test_empty_cohort_retention():
    df = pd.DataFrame(columns=["CustomerID", "StartDate", "EndDate"])
    date_index = pd.to_datetime(["2024-01-01"])
    retention = cohort_retention(df, date_index)
    assert retention.empty
