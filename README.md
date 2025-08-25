# Analytics App — E‑commerce + Subscriptions

End‑to‑end analytics app (Power BI style) built with **Streamlit + Plotly**. It consumes the CSV dataset we generated earlier and reproduces KPIs like MRR/ARR, churn, revenue vs. budget, CAC/ROAS, and cohort retention.
![Screenshot 2025-08-25 at 17.48.48.png](data/Screenshot%202025-08-25%20at%2017.48.48.png)
![Screenshot 2025-08-25 at 17.49.15.png](data/Screenshot%202025-08-25%20at%2017.49.15.png)
##  Project Structure
```
streamlit_power_analytics_app/
├─ streamlit_app.py
├─ requirements.txt
├─ .streamlit/config.toml
├─ src/utils.py
└─ data/                 
```

##  Run locally
```bash
pip install -r requirements.txt
# Option A: CSVs in ./data
streamlit run streamlit_app.py

```

##  Features
- Global filters: date range, channels, countries, segments
- KPIs: Revenue, Gross Margin %, MRR, ARR, Active Subs, Churn %
- Trends with YoY, variance vs budget
- Marketing funnel: Sessions, Conversions, Spend, CAC, ROAS
- Cohort retention heatmap
- What‑If discount slider
- Data Quality page (row counts, nulls, last refresh)

##  Expected CSV files
`DimDate.csv, DimGeo.csv, DimChannel.csv, DimProduct.csv, DimCustomer.csv, FactSubscriptions.csv, FactSales.csv, FactWeb.csv, FactBudget.csv`

