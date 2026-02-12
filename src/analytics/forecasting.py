import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta

def prepare_time_series_data(df_sales: pd.DataFrame):
    """
    Transforms raw sales records into a monthly time series with engineered trend and seasonal features.
    """
    # Summing revenue at a monthly grain
    ts = df_sales.groupby(pd.Grouper(key='Date', freq='ME')).agg(revenue=('Revenue', 'sum')).reset_index()
    
    # Trend feature: sequential month numbering
    ts['month_num'] = np.arange(len(ts))
    
    # Seasonal feature: month of the year (1-12)
    ts['month_of_year'] = ts['Date'].dt.month
    
    # Historical lags for context
    ts['lag_1'] = ts['revenue'].shift(1)
    ts['lag_12'] = ts['revenue'].shift(12)
    
    return ts.dropna()

def train_forecast_model(ts_data: pd.DataFrame):
    """
    Trains a Linear Regression model using trend and seasonal components.
    """
    X = ts_data[['month_num', 'month_of_year']]
    y = ts_data['revenue']
    
    model = LinearRegression()
    model.fit(X, y)
    return model

def generate_forecast(df_sales: pd.DataFrame, months_to_forecast: int = 12):
    """
    High-level orchestration to train the model and generate a projected revenue dataframe.
    """
    # 1. Historical Data Alignment
    ts = df_sales.groupby(pd.Grouper(key='Date', freq='ME')).agg(revenue=('Revenue', 'sum')).reset_index()
    ts['month_num'] = np.arange(len(ts))
    ts['month_of_year'] = ts['Date'].dt.month
    
    # 2. Model Training
    model = train_forecast_model(ts)
    
    # 3. Future Period Generation
    last_date = ts['Date'].max()
    last_month_num = ts['month_num'].max()
    
    future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, months_to_forecast + 1)]
    future_df = pd.DataFrame({
        'Date': future_dates,
        'month_num': np.arange(last_month_num + 1, last_month_num + 1 + months_to_forecast),
        'month_of_year': [d.month for d in future_dates]
    })
    
    # 4. Future Revenue Prediction
    future_df['revenue'] = model.predict(future_df[['month_num', 'month_of_year']])
    
    # Combine historical and future
    ts['type'] = 'Historical'
    future_df['type'] = 'Forecast'
    
    combined = pd.concat([ts, future_df], ignore_index=True)
    return combined
